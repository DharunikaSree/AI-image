"""
Visual embedding + similarity search abstraction.

generate_embedding() turns an image into a fixed-length numeric vector
(color histogram in HSV space + coarse texture signature). This is a real,
deterministic feature extraction — not a placeholder. It is intentionally
lightweight (no GPU/model download required) so the project runs anywhere,
while the interface below is exactly what you'd swap a real CNN embedding
model into later (see EmbeddingService docstring).

Embeddings are stored as comma-separated floats on Product.embedding_reference
so the project needs no external vector database to run out of the box.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

EMBEDDING_DIM = 32  # 24 HSV histogram bins + 8 texture bins


class EmbeddingService:
    """
    Swap point for a real model: replace the body of `generate_embedding`
    with e.g. a PyTorch EfficientNet forward pass that returns a fixed-length
    vector. Every caller (search, admin embedding generation, seeding) goes
    through this single class, so nothing else needs to change.
    """

    def generate_embedding(self, image_path: str) -> np.ndarray:
        img = Image.open(image_path).convert("RGB").resize((128, 128))
        hsv = np.asarray(img.convert("HSV"), dtype=float)

        h_hist, _ = np.histogram(hsv[:, :, 0], bins=12, range=(0, 255))
        s_hist, _ = np.histogram(hsv[:, :, 1], bins=8, range=(0, 255))
        v_hist, _ = np.histogram(hsv[:, :, 2], bins=4, range=(0, 255))

        gray = np.asarray(img.convert("L"), dtype=float)
        gx = np.abs(np.diff(gray, axis=1)).flatten()
        tex_hist, _ = np.histogram(gx, bins=8, range=(0, 255))

        vec = np.concatenate([h_hist, s_hist, v_hist, tex_hist]).astype(float)
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec

    def to_string(self, vec: np.ndarray) -> str:
        return ",".join(f"{x:.6f}" for x in vec)

    def from_string(self, s: str) -> np.ndarray:
        if not s:
            return np.zeros(EMBEDDING_DIM)
        return np.array([float(x) for x in s.split(",")])


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


embedding_service = EmbeddingService()
