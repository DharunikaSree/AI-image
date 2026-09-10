"""
Build and save a FAISS vector index for DeepFashion CLIP embeddings.
Uses IndexFlatIP (Inner Product / Cosine Similarity on normalized vectors).
"""
import os
import json
import time
import numpy as np
import faiss

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EMBEDDINGS_PATH = os.path.join(DATA_DIR, "clip_embeddings.npy")
PRODUCT_IDS_PATH = os.path.join(DATA_DIR, "clip_product_ids.json")
ID_TO_INDEX_PATH = os.path.join(DATA_DIR, "clip_id_to_index.json")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "clip_faiss.index")
FAISS_SUMMARY_PATH = os.path.join(DATA_DIR, "faiss_index_summary.json")

def build_faiss_index():
    print("=" * 60)
    print("      Lumière AI - DeepFashion FAISS Index Builder")
    print("=" * 60)

    start_time = time.time()

    # 1. Load CLIP embeddings and IDs
    print(f"[*] Loading embeddings from: {EMBEDDINGS_PATH}")
    embeds = np.load(EMBEDDINGS_PATH)
    if embeds.dtype != np.float32:
        embeds = embeds.astype(np.float32)

    num_items, dim = embeds.shape
    print(f"    Loaded matrix: {num_items} vectors of dimension {dim}")

    print(f"[*] Loading product IDs from: {PRODUCT_IDS_PATH}")
    with open(PRODUCT_IDS_PATH, "r", encoding="utf-8") as f:
        pids = json.load(f)

    assert len(pids) == num_items, f"Mismatch: {len(pids)} IDs vs {num_items} embeddings"

    # 2. Verify unit norm (for exact Cosine Similarity)
    norms = np.linalg.norm(embeds, axis=-1)
    if not np.allclose(norms, 1.0, atol=1e-3):
        print("[!] Re-normalizing vectors to ensure exact unit norm...")
        faiss.normalize_L2(embeds)
    else:
        print("[+] Embeddings are verified unit-normalized (Cosine Similarity = Inner Product).")

    # 3. Create IndexFlatIP
    print(f"[*] Creating FAISS IndexFlatIP(dim={dim})...")
    index = faiss.IndexFlatIP(dim)

    # 4. Add vectors to index
    add_start = time.time()
    index.add(embeds)
    add_time = time.time() - add_start
    print(f"[+] Added {index.ntotal} vectors to FAISS index in {add_time:.4f} seconds.")

    # 5. Save FAISS index
    print(f"[*] Saving FAISS index to: {FAISS_INDEX_PATH}")
    faiss.write_index(index, FAISS_INDEX_PATH)
    index_size_mb = os.path.getsize(FAISS_INDEX_PATH) / (1024 * 1024)
    print(f"[+] Saved index ({index_size_mb:.2f} MB)")

    total_time = time.time() - start_time

    # 6. Save summary JSON
    summary = {
        "index_type": "IndexFlatIP",
        "metric": "Cosine Similarity / Inner Product",
        "dimension": dim,
        "total_vectors": index.ntotal,
        "index_file": os.path.relpath(FAISS_INDEX_PATH, os.path.dirname(DATA_DIR)),
        "index_file_size_mb": round(index_size_mb, 2),
        "build_time_seconds": round(total_time, 4),
        "product_ids_file": os.path.relpath(PRODUCT_IDS_PATH, os.path.dirname(DATA_DIR)),
        "id_to_index_file": os.path.relpath(ID_TO_INDEX_PATH, os.path.dirname(DATA_DIR)),
        "status": "FAISS Index Built Successfully"
    }

    with open(FAISS_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"[+] Saved summary to: {FAISS_SUMMARY_PATH}")

    print("=" * 60)
    print(f"[OK] FAISS Indexing Complete in {total_time:.2f}s!")
    print(f"    Total vectors: {index.ntotal}")
    print(f"    File size:     {index_size_mb:.2f} MB")
    print("=" * 60)

    return index, pids

if __name__ == "__main__":
    build_faiss_index()
