"""
Verify alignment between clip_embeddings.npy, clip_product_ids.json, and deepfashion_catalog.csv
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def check_alignment():
    emb_path = PROJECT_ROOT / "data" / "clip_embeddings.npy"
    ids_path = PROJECT_ROOT / "data" / "clip_product_ids.json"
    csv_path = PROJECT_ROOT / "data" / "deepfashion_catalog.csv"

    embeddings = np.load(emb_path)
    with open(ids_path, "r", encoding="utf-8") as f:
        product_ids = json.load(f)
    df = pd.read_csv(csv_path)

    print(f"Embeddings shape: {embeddings.shape}")
    print(f"Product IDs count: {len(product_ids)}")
    print(f"CSV rows: {len(df)}")
    assert len(embeddings) == len(product_ids) == len(df), "Lengths must match exactly!"

    # Check ID alignment
    df_ids = df["id"].tolist()
    match = df_ids == product_ids
    print(f"Exact row-by-row ID synchronization: {match}")

if __name__ == "__main__":
    check_alignment()
