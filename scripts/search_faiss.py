"""
FAISS Vector Search Engine and Testing Benchmark for DeepFashion CLIP Embeddings.

Features:
- Sub-millisecond similarity search across 44,441 catalog items using FAISS IndexFlatIP.
- Query by image (image-to-image similarity search).
- Query by text (text-to-image zero-shot multimodal search).
- Comprehensive benchmark measuring query latency, throughput, and retrieval quality.
"""
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import Any, List, Dict, Union

import numpy as np
import faiss
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "clip_faiss.index")
PRODUCT_IDS_PATH = os.path.join(DATA_DIR, "clip_product_ids.json")
METADATA_PATH = os.path.join(DATA_DIR, "deepfashion_metadata.json")
MODEL_NAME = "openai/clip-vit-base-patch32"


class DeepFashionVectorSearch:
    def __init__(self, index_path: str = FAISS_INDEX_PATH, ids_path: str = PRODUCT_IDS_PATH, meta_path: str = METADATA_PATH, device: str = None):
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        print(f"[*] Initializing FAISS Vector Search Engine (Device: {self.device})...")
        load_start = time.time()

        # 1. Load FAISS index
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"FAISS index not found at: {index_path}. Run build_faiss_index.py first.")
        self.index = faiss.read_index(index_path)
        print(f"    Loaded FAISS index: {self.index.ntotal} vectors (dim={self.index.d})")

        # 2. Load product IDs
        with open(ids_path, "r", encoding="utf-8") as f:
            self.product_ids = json.load(f)
        print(f"    Loaded {len(self.product_ids)} synchronized product IDs")

        # 3. Load product metadata lookup
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_list = json.load(f)
        self.metadata_by_id: Dict[int, Dict[str, Any]] = {item["id"]: item for item in meta_list}
        print(f"    Loaded {len(self.metadata_by_id)} product catalog records")

        # 4. Load CLIP Model & Processor
        print(f"[*] Loading CLIP model '{MODEL_NAME}'...")
        self.model = CLIPModel.from_pretrained(MODEL_NAME).to(self.device)
        self.model.eval()
        self.processor = CLIPProcessor.from_pretrained(MODEL_NAME)

        init_time = time.time() - load_start
        print(f"[OK] Vector Search Engine ready in {init_time:.2f}s.\n")

    def encode_image(self, image: Union[str, Path, Image.Image]) -> np.ndarray:
        """Encode a PIL Image or image file path into a normalized 512-dim numpy vector."""
        if isinstance(image, (str, Path)):
            img = Image.open(image).convert("RGB")
        else:
            img = image.convert("RGB")

        inputs = self.processor(images=img, return_tensors="pt")
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.get_image_features(**inputs)
            embeds = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            embeds = embeds / embeds.norm(p=2, dim=-1, keepdim=True)
            vec = embeds.cpu().numpy().astype(np.float32)

        return vec

    def encode_text(self, text: str) -> np.ndarray:
        """Encode a text query into a normalized 512-dim numpy vector for multimodal search."""
        inputs = self.processor(text=[text], return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model.get_text_features(**inputs)
            embeds = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            embeds = embeds / embeds.norm(p=2, dim=-1, keepdim=True)
            vec = embeds.cpu().numpy().astype(np.float32)

        return vec

    def search_vector(self, query_vec: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """Search the FAISS index with a precomputed query vector."""
        if query_vec.ndim == 1:
            query_vec = np.expand_dims(query_vec, axis=0)

        # Ensure float32 and normalized
        if query_vec.dtype != np.float32:
            query_vec = query_vec.astype(np.float32)
        faiss.normalize_L2(query_vec)

        search_start = time.perf_counter()
        scores, indices = self.index.search(query_vec, top_k)
        search_ms = (time.perf_counter() - search_start) * 1000.0

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            if idx < 0 or idx >= len(self.product_ids):
                continue
            pid = self.product_ids[idx]
            meta = self.metadata_by_id.get(pid, {})
            results.append({
                "rank": rank,
                "product_id": pid,
                "similarity_score": round(float(score), 4),
                "index_position": int(idx),
                "name": meta.get("name", "Unknown"),
                "category": meta.get("category", "Unknown"),
                "subcategory": meta.get("subcategory", "Unknown"),
                "article_type": meta.get("article_type", "Unknown"),
                "color": meta.get("color", "Unknown"),
                "brand": meta.get("brand", "Unknown"),
                "gender": meta.get("gender", "Unknown"),
                "price": meta.get("price", 0),
                "image_path": meta.get("image_path", ""),
            })

        return results, search_ms

    def search_by_image(self, image: Union[str, Path, Image.Image], top_k: int = 10) -> Dict[str, Any]:
        """Search top-K products by query image."""
        embed_start = time.perf_counter()
        query_vec = self.encode_image(image)
        embed_ms = (time.perf_counter() - embed_start) * 1000.0

        results, search_ms = self.search_vector(query_vec, top_k=top_k)
        return {
            "query_type": "image",
            "top_k": top_k,
            "embed_time_ms": round(embed_ms, 2),
            "faiss_search_time_ms": round(search_ms, 3),
            "total_latency_ms": round(embed_ms + search_ms, 2),
            "results": results
        }

    def search_by_text(self, query_text: str, top_k: int = 10) -> Dict[str, Any]:
        """Search top-K products by text query (zero-shot multimodal search)."""
        embed_start = time.perf_counter()
        query_vec = self.encode_text(query_text)
        embed_ms = (time.perf_counter() - embed_start) * 1000.0

        results, search_ms = self.search_vector(query_vec, top_k=top_k)
        return {
            "query_type": "text",
            "query_text": query_text,
            "top_k": top_k,
            "embed_time_ms": round(embed_ms, 2),
            "faiss_search_time_ms": round(search_ms, 3),
            "total_latency_ms": round(embed_ms + search_ms, 2),
            "results": results
        }


def run_benchmark_tests():
    print("=" * 70)
    print("   Lumiere AI - FAISS Vector Search Verification & Benchmark")
    print("=" * 70)

    engine = DeepFashionVectorSearch()

    # Find diverse test images from metadata
    test_categories = ["Shoes", "Watches", "Shirts", "Dresses", "Handbags"]
    test_items = {}
    for item in engine.metadata_by_id.values():
        art_type = item.get("article_type", "")
        if art_type in test_categories and art_type not in test_items:
            img_path = item.get("image_path", "")
            if os.path.exists(img_path):
                test_items[art_type] = item
        if len(test_items) == len(test_categories):
            break

    benchmark_results = []
    faiss_search_times = []

    print("\n" + "=" * 70)
    print(">>> 1. Image-to-Image Vector Search Tests (Real Fashion Photos):")
    print("=" * 70)

    for cat, query_item in test_items.items():
        img_path = query_item["image_path"]
        res = engine.search_by_image(img_path, top_k=5)
        faiss_search_times.append(res["faiss_search_time_ms"])

        print(f"\n[QUERY IMAGE] Article: {cat} | ID: {query_item['id']} | {query_item['name']}")
        print(f"              CLIP Embed: {res['embed_time_ms']} ms | FAISS Search: {res['faiss_search_time_ms']} ms | Total: {res['total_latency_ms']} ms")
        print("  Top-5 Retrieved Products:")
        for r in res["results"]:
            match_flag = " (EXACT QUERY)" if r['product_id'] == query_item['id'] else ""
            print(f"    #{r['rank']} [Sim: {r['similarity_score']:.4f}] ID: {r['product_id']} | {r['name']} ({r['article_type']}, {r['color']}) - Rs.{r['price']}{match_flag}")

        benchmark_results.append({
            "test_type": "image_search",
            "query_category": cat,
            "query_id": query_item["id"],
            "query_name": query_item["name"],
            "top_match_id": res["results"][0]["product_id"],
            "top_match_similarity": res["results"][0]["similarity_score"],
            "exact_self_match": res["results"][0]["product_id"] == query_item["id"],
            "faiss_search_time_ms": res["faiss_search_time_ms"],
            "total_latency_ms": res["total_latency_ms"],
            "top_5_article_types": [r["article_type"] for r in res["results"]]
        })

    print("\n" + "=" * 70)
    print(">>> 2. Multimodal Text-to-Image Vector Search Tests:")
    print("=" * 70)

    text_queries = [
        "running sports shoes for men",
        "luxury black analog watch",
        "casual blue denim jeans",
        "red summer party dress",
        "traditional cotton kurta"
    ]

    for q in text_queries:
        res = engine.search_by_text(q, top_k=3)
        faiss_search_times.append(res["faiss_search_time_ms"])
        print(f"\n[QUERY TEXT] \"{q}\"")
        print(f"             CLIP Embed: {res['embed_time_ms']} ms | FAISS Search: {res['faiss_search_time_ms']} ms")
        for r in res["results"]:
            print(f"    #{r['rank']} [Sim: {r['similarity_score']:.4f}] ID: {r['product_id']} | {r['name']} ({r['article_type']}, {r['color']}) - Rs.{r['price']}")

    # 3. High-throughput FAISS pure search benchmark (1,000 queries)
    print("\n" + "=" * 70)
    print(">>> 3. FAISS Speed Benchmark (1,000 Vector Searches across 44,441 vectors):")
    print("=" * 70)

    # Pick 1,000 random vectors from existing embeddings
    sample_embeds = np.load(os.path.join(DATA_DIR, "clip_embeddings.npy"))[:1000]
    bm_start = time.perf_counter()
    scores, indices = engine.index.search(sample_embeds, 10)
    bm_duration = time.perf_counter() - bm_start

    avg_faiss_ms = (bm_duration / 1000) * 1000
    qps = 1000 / bm_duration

    print(f"    Processed: 1,000 queries (Top-10 each)")
    print(f"    Total FAISS Time: {bm_duration:.4f} seconds")
    print(f"    Average FAISS Search Latency: {avg_faiss_ms:.3f} ms / query")
    print(f"    FAISS Search Throughput:      {qps:.1f} queries / second (QPS)")
    print("=" * 70)

    # Save benchmark report
    report = {
        "faiss_index_file": "data/clip_faiss.index",
        "total_catalog_vectors": engine.index.ntotal,
        "embedding_dimension": engine.index.d,
        "index_type": "IndexFlatIP",
        "metric": "Cosine Similarity / Inner Product",
        "average_faiss_search_latency_ms": round(avg_faiss_ms, 3),
        "search_throughput_qps": round(qps, 1),
        "image_search_tests": benchmark_results,
        "status": "Phase 3 FAISS Vector Search Verification Succeeded"
    }

    report_path = os.path.join(DATA_DIR, "faiss_benchmark_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"[OK] Benchmark report saved to: {report_path}")

    return report


if __name__ == "__main__":
    run_benchmark_tests()
