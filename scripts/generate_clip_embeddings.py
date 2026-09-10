"""
High-Performance Resumable CLIP Embedding Generation Pipeline for DeepFashion.

Features:
- Pretrained CLIP vision model: `openai/clip-vit-base-patch32` (512-dimensional).
- Multi-process parallel chunking with automatic resume.
- Progress tracking with ETA and image rate.
- Safe serialization:
  * `data/clip_embeddings.npy`: (44441, 512) float32 matrix
  * `data/clip_product_ids.json`: List of product IDs matching matrix rows
  * `data/clip_id_to_index.json`: Fast lookup dict {str(product_id): row_index}
  * `data/clip_embeddings_summary.json`: Comprehensive report.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

DEFAULT_MODEL_NAME = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512
CHUNK_SIZE = 1000


def _worker_process_chunk(args: Tuple[int, List[Dict[str, Any]], str, int, int, str]) -> Dict[str, Any]:
    """Worker function to process a single chunk of items."""
    chunk_idx, items, checkpoints_dir_str, batch_size, threads, device_str = args
    checkpoints_dir = Path(checkpoints_dir_str)
    chunk_file = checkpoints_dir / f"chunk_{chunk_idx:05d}.npy"
    ids_file = checkpoints_dir / f"chunk_{chunk_idx:05d}.json"

    expected_count = len(items)

    # Check if already completed and valid
    if chunk_file.exists() and ids_file.exists():
        try:
            mat = np.load(chunk_file)
            with open(ids_file, "r", encoding="utf-8") as f:
                c_ids = json.load(f)
            if mat.shape == (expected_count, EMBEDDING_DIM) and len(c_ids) == expected_count:
                return {
                    "chunk_idx": chunk_idx,
                    "status": "cached",
                    "count": expected_count,
                    "failed": 0,
                }
        except Exception:
            pass  # Recompute if invalid

    # Initialize PyTorch threads and model for worker
    torch.set_num_threads(threads)
    device = torch.device(device_str)

    processor = CLIPProcessor.from_pretrained(DEFAULT_MODEL_NAME)
    model = CLIPModel.from_pretrained(DEFAULT_MODEL_NAME).to(device)
    model.eval()

    all_embeds: List[np.ndarray] = []
    processed_ids: List[int] = []
    failed_count = 0

    batch_images: List[Image.Image] = []
    batch_ids: List[int] = []

    for idx, it in enumerate(items, start=1):
        img_path = it.get("image_path")
        item_id = it.get("id")

        img_loaded = False
        if img_path and os.path.exists(img_path):
            try:
                with Image.open(img_path) as img:
                    rgb_img = img.convert("RGB")
                    batch_images.append(rgb_img)
                    batch_ids.append(item_id)
                    img_loaded = True
            except Exception:
                pass

        if not img_loaded:
            # Create neutral placeholder image for corrupt/missing to maintain exact index alignment
            batch_images.append(Image.new("RGB", (224, 224), (128, 128, 128)))
            batch_ids.append(item_id)
            failed_count += 1

        if len(batch_images) >= batch_size or idx == expected_count:
            if batch_images:
                with torch.inference_mode():
                    inputs = processor(images=batch_images, return_tensors="pt").to(device)
                    feat = model.get_image_features(**inputs)
                    if hasattr(feat, "pooler_output") and feat.pooler_output is not None:
                        embeds = feat.pooler_output
                    elif hasattr(feat, "image_embeds") and feat.image_embeds is not None:
                        embeds = feat.image_embeds
                    else:
                        embeds = feat
                    embeds = embeds / embeds.norm(p=2, dim=-1, keepdim=True)
                    all_embeds.append(embeds.cpu().numpy().astype(np.float32))
                    processed_ids.extend(batch_ids)

                batch_images.clear()
                batch_ids.clear()

    if all_embeds:
        chunk_mat = np.vstack(all_embeds).astype(np.float32)
    else:
        chunk_mat = np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    np.save(chunk_file, chunk_mat)
    with open(ids_file, "w", encoding="utf-8") as f:
        json.dump(processed_ids, f)

    return {
        "chunk_idx": chunk_idx,
        "status": "computed",
        "count": chunk_mat.shape[0],
        "failed": failed_count,
    }


def run_parallel_clip_pipeline(
    metadata_path: str = "./data/deepfashion_metadata.json",
    output_dir: str = "./data",
    batch_size: int = 64,
    chunk_size: int = CHUNK_SIZE,
    num_workers: int = 4,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = out_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)

    meta_file = Path(metadata_path)
    if not meta_file.exists():
        raise FileNotFoundError(f"Metadata not found: {meta_file}")

    with open(meta_file, "r", encoding="utf-8") as f:
        all_items: List[Dict[str, Any]] = json.load(f)

    total_items = len(all_items)
    device_str = device or ("cuda" if torch.cuda.is_available() else "cpu")

    # Split all items into deterministic chunks
    chunks: List[List[Dict[str, Any]]] = []
    for i in range(0, total_items, chunk_size):
        chunks.append(all_items[i : i + chunk_size])

    total_chunks = len(chunks)
    threads_per_worker = max(1, (os.cpu_count() or 4) // max(num_workers, 1))

    print(f"[*] Starting CLIP Pipeline for {total_items} items across {total_chunks} chunks.")
    print(f"    Workers: {num_workers}, Threads per worker: {threads_per_worker}, Device: {device_str}")
    print(f"    Checkpoints Directory: {checkpoints_dir}")

    # Build work tasks
    tasks = []
    cached_count = 0
    cached_items = 0

    for c_idx, c_items in enumerate(chunks):
        c_file = checkpoints_dir / f"chunk_{c_idx:05d}.npy"
        ids_file = checkpoints_dir / f"chunk_{c_idx:05d}.json"
        is_cached = False
        if c_file.exists() and ids_file.exists():
            try:
                mat = np.load(c_file)
                if mat.shape == (len(c_items), EMBEDDING_DIM):
                    is_cached = True
                    cached_count += 1
                    cached_items += len(c_items)
            except Exception:
                is_cached = False

        if not is_cached:
            tasks.append((c_idx, c_items, str(checkpoints_dir), batch_size, threads_per_worker, device_str))

    print(f"[*] Found {cached_count}/{total_chunks} cached chunks ({cached_items} items).")
    print(f"[*] Chunks remaining to compute: {len(tasks)}")

    start_time = time.time()
    completed_chunks = cached_count
    total_processed_items = cached_items
    total_failed_images = 0

    if tasks:
        with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
            future_to_chunk = {executor.submit(_worker_process_chunk, t): t[0] for t in tasks}
            for future in concurrent.futures.as_completed(future_to_chunk):
                c_idx = future_to_chunk[future]
                try:
                    res = future.result()
                    completed_chunks += 1
                    total_processed_items += res["count"]
                    total_failed_images += res["failed"]
                    elapsed = time.time() - start_time
                    rate = (total_processed_items - cached_items) / max(elapsed, 0.001)
                    rem_chunks = total_chunks - completed_chunks
                    eta_min = (rem_chunks * chunk_size) / max(rate, 0.001) / 60
                    print(
                        f"    [Chunk {completed_chunks}/{total_chunks} complete] "
                        f"Items: {total_processed_items}/{total_items} ({total_processed_items/total_items*100:.1f}%) | "
                        f"Rate: {rate:.1f} img/s | ETA: {eta_min:.1f} min"
                    )
                except Exception as e:
                    print(f"[!] Error in chunk {c_idx}: {e}")

    # Consolidate all chunks in strict sequential order
    print("[*] Merging all chunks into final matrix...")
    final_matrices = []
    final_ids = []

    for c_idx in range(total_chunks):
        c_file = checkpoints_dir / f"chunk_{c_idx:05d}.npy"
        ids_file = checkpoints_dir / f"chunk_{c_idx:05d}.json"
        if not c_file.exists() or not ids_file.exists():
            raise RuntimeError(f"Missing chunk file: {c_file}")

        c_mat = np.load(c_file)
        with open(ids_file, "r", encoding="utf-8") as f:
            c_ids = json.load(f)

        assert c_mat.shape[0] == len(c_ids), f"Mismatch in chunk {c_idx}: {c_mat.shape[0]} vs {len(c_ids)}"
        final_matrices.append(c_mat)
        final_ids.extend(c_ids)

    unified_matrix = np.vstack(final_matrices).astype(np.float32)
    total_time = time.time() - start_time

    # Save artifacts
    npy_path = out_dir / "clip_embeddings.npy"
    np.save(npy_path, unified_matrix)
    print(f"[*] Saved final embeddings: {npy_path} (Shape: {unified_matrix.shape}, Size: {npy_path.stat().st_size / (1024*1024):.2f} MB)")

    ids_path = out_dir / "clip_product_ids.json"
    with open(ids_path, "w", encoding="utf-8") as f:
        json.dump(final_ids, f)
    print(f"[*] Saved product IDs: {ids_path} (Count: {len(final_ids)})")

    id_to_idx = {str(pid): i for i, pid in enumerate(final_ids)}
    map_path = out_dir / "clip_id_to_index.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(id_to_idx, f)
    print(f"[*] Saved ID->Index mapping: {map_path}")

    # Validate IDs and norms
    all_ids_matched = (unified_matrix.shape[0] == len(final_ids) == len(id_to_idx) == total_items)
    norms = np.linalg.norm(unified_matrix[:1000], axis=1)
    norm_valid = bool(np.allclose(norms, 1.0, atol=1e-3))

    summary = {
        "model_name": DEFAULT_MODEL_NAME,
        "embedding_dim": EMBEDDING_DIM,
        "total_images_processed": unified_matrix.shape[0],
        "successful_embeddings": unified_matrix.shape[0] - total_failed_images,
        "failed_images": total_failed_images,
        "embedding_shape": list(unified_matrix.shape),
        "output_file_size_mb": round(npy_path.stat().st_size / (1024 * 1024), 2),
        "total_processing_time_seconds": round(total_time, 2),
        "all_ids_match_embeddings": all_ids_matched,
        "unit_norm_valid": norm_valid,
        "output_files": {
            "embeddings_matrix": str(npy_path),
            "product_ids": str(ids_path),
            "id_to_index_mapping": str(map_path),
        },
        "status": "Full DeepFashion CLIP Embeddings Complete",
    }

    summary_path = out_dir / "clip_embeddings_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[*] Saved execution summary: {summary_path}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Generate CLIP image embeddings for full DeepFashion dataset.")
    parser.add_argument("--metadata", type=str, default="./data/deepfashion_metadata.json", help="Path to metadata JSON")
    parser.add_argument("--output_dir", type=str, default="./data", help="Output directory")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size for model inference")
    parser.add_argument("--chunk_size", type=int, default=1000, help="Chunk size")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker processes")
    parser.add_argument("--device", type=str, default=None, help="Device ('cuda' or 'cpu')")
    args = parser.parse_args()

    run_parallel_clip_pipeline(
        metadata_path=args.metadata,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        chunk_size=args.chunk_size,
        num_workers=args.workers,
        device=args.device,
    )


if __name__ == "__main__":
    main()
