"""
Visual embedding + FAISS similarity search service.
Generates 512-dimensional normalized embeddings using pretrained CLIP (openai/clip-vit-base-patch32)
and performs sub-millisecond similarity queries over the DeepFashion FAISS index.
"""
from __future__ import annotations

import os
import json
import time
from pathlib import Path
from typing import List, Tuple, Dict, Any

import numpy as np
import faiss
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FAISS_INDEX_PATH = DATA_DIR / "clip_faiss.index"
PRODUCT_IDS_PATH = DATA_DIR / "clip_product_ids.json"

MODEL_NAME = "openai/clip-vit-base-patch32"
EMBEDDING_DIM = 512


class EmbeddingService:
    """Singleton service for CLIP visual feature extraction and FAISS similarity retrieval."""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.processor = None
        self.faiss_index = None
        self.product_ids: list[int] = []
        self.loaded = False

    def load(self):
        if self.loaded:
            return

        print(f"[*] Initializing CLIP & FAISS Search Service (Device: {self.device})...")
        try:
            # 1. Load CLIP Model & Processor
            self.model = CLIPModel.from_pretrained(MODEL_NAME).to(self.device)
            self.model.eval()
            self.processor = CLIPProcessor.from_pretrained(MODEL_NAME)

            # 2. Load FAISS index
            if FAISS_INDEX_PATH.exists():
                self.faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
                print(f"    Loaded FAISS index: {self.faiss_index.ntotal} vectors (dim={self.faiss_index.d})")
            else:
                print(f"[!] FAISS index not found at {FAISS_INDEX_PATH}")

            # 3. Load product IDs
            if PRODUCT_IDS_PATH.exists():
                with open(PRODUCT_IDS_PATH, "r", encoding="utf-8") as f:
                    self.product_ids = json.load(f)
                print(f"    Loaded {len(self.product_ids)} synchronized product IDs")

            self.loaded = True
            print("[*] CLIP + FAISS Search Engine is ready.")
        except Exception as e:
            print(f"[!] Error loading CLIP / FAISS: {e}")
            self.loaded = False

    def warmup(self):
        """Pre-warms the CLIP vision model and tests FAISS query."""
        self.load()
        if not self.loaded or self.model is None:
            return
        try:
            dummy_pixels = torch.zeros((1, 3, 224, 224), dtype=torch.float32, device=self.device)
            with torch.no_grad():
                outputs = self.model.get_image_features(pixel_values=dummy_pixels)
                embeds = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
                _ = embeds / embeds.norm(p=2, dim=-1, keepdim=True)
            if self.faiss_index is not None:
                dummy_vec = np.zeros((1, EMBEDDING_DIM), dtype=np.float32)
                self.faiss_index.search(dummy_vec, 1)
        except Exception as e:
            print(f"[!] Embedding service warmup warning: {e}")

    def generate_embedding(self, image_path: str) -> np.ndarray:
        """Extract a 512-dim L2-normalized CLIP embedding from an image file."""
        self.load()
        if not self.loaded or self.model is None:
            # Fallback to 512-dim zeros if model failed
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

        try:
            img = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=img, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model.get_image_features(**inputs)
                embeds = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
                embeds = embeds / embeds.norm(p=2, dim=-1, keepdim=True)
                vec = embeds.cpu().numpy().astype(np.float32)[0]
            return vec
        except Exception as e:
            print(f"[!] CLIP embedding extraction failed: {e}")
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    def search_faiss(self, query_vec: np.ndarray, top_k: int = 60) -> List[Tuple[int, float]]:
        """
        Queries the FAISS index with the normalized 512-dim query vector.
        Returns a list of (product_id, similarity_score) tuples.
        """
        self.load()
        if self.faiss_index is None or not self.product_ids:
            return []

        try:
            if query_vec.ndim == 1:
                query_vec = np.expand_dims(query_vec, axis=0)

            if query_vec.dtype != np.float32:
                query_vec = query_vec.astype(np.float32)

            scores, indices = self.faiss_index.search(query_vec, top_k)

            results: List[Tuple[int, float]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self.product_ids):
                    continue
                pid = self.product_ids[idx]
                results.append((pid, float(score)))

            return results
        except Exception as e:
            print(f"[!] FAISS search error: {e}")
            return []

    def to_string(self, vec: np.ndarray) -> str:
        return ",".join(f"{x:.6f}" for x in vec)

    def from_string(self, s: str) -> np.ndarray:
        if not s:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)
        try:
            return np.array([float(x) for x in s.split(",")], dtype=np.float32)
        except Exception:
            return np.zeros(EMBEDDING_DIM, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


embedding_service = EmbeddingService()
