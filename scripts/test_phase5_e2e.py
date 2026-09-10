import os
import sys
import json
import time
import torch
import faiss
import numpy as np
from PIL import Image
from transformers import CLIPProcessor, CLIPModel, AutoImageProcessor, ViTModel

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" / "vit_fashion_classifier"

FAISS_INDEX_PATH = str(DATA_DIR / "clip_faiss.index")
PRODUCT_IDS_PATH = str(DATA_DIR / "clip_product_ids.json")
METADATA_PATH = str(DATA_DIR / "deepfashion_metadata.json")
CHECKPOINT_PATH = str(MODELS_DIR / "vit_fashion_classifier.pt")
CLASS_MAPPING_PATH = str(MODELS_DIR / "class_mapping.json")

def test_pipeline():
    print("=" * 70)
    print("   Testing Phase 5 Pipeline End-to-End")
    print("=" * 70)

    device = torch.device("cpu")
    torch.set_num_threads(8)

    # 1. Load ViT Classifier
    print("[1] Loading ViT Fashion Classifier...")
    with open(CLASS_MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    id2label = {int(k): v for k, v in mapping["id2label"].items()}
    target_classes = mapping["target_classes"]

    vit_processor = AutoImageProcessor.from_pretrained(mapping["base_model"])
    vit_backbone = ViTModel.from_pretrained(mapping["base_model"]).to(device)
    vit_backbone.eval()

    ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
    classifier_head = torch.nn.Sequential(
        torch.nn.Dropout(0.3),
        torch.nn.Linear(768, 256),
        torch.nn.GELU(),
        torch.nn.LayerNorm(256),
        torch.nn.Dropout(0.2),
        torch.nn.Linear(256, len(target_classes))
    ).to(device)
    classifier_head.load_state_dict(ckpt["classifier_head_state_dict"])
    classifier_head.eval()

    # 2. Load CLIP Model
    print("[2] Loading CLIP Model...")
    clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
    clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    clip_model.eval()

    # 3. Load FAISS Index
    print("[3] Loading FAISS Index...")
    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(PRODUCT_IDS_PATH, "r", encoding="utf-8") as f:
        product_ids = json.load(f)
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    id_to_meta = {m["id"]: m for m in metadata}

    test_categories = ["Shoes", "Shirt", "Dress", "Saree"]

    def find_image_path(item: dict) -> str | None:
        p = item.get("image_path")
        if p and os.path.exists(p):
            return p
        filename = f"{item['id']}.jpg"
        for cdir in [
            Path(r"D:\kagglehub_cache\datasets\paramaggarwal\fashion-product-images-dataset\versions\1\fashion-dataset\images"),
            Path(r"D:\kagglehub_cache\datasets\paramaggarwal\fashion-product-images-dataset\versions\1\images"),
            Path(r"C:\Users\dharu\.cache\kagglehub\datasets\paramaggarwal\fashion-product-images-dataset\versions\1\images"),
            Path(r"C:\Users\dharu\.cache\kagglehub\datasets\paramaggarwal\fashion-product-images-small\versions\1\images"),
            PROJECT_ROOT / "data" / "images",
        ]:
            cand = cdir / filename
            if cand.exists():
                return str(cand)
        return None

    for cat in test_categories:
        # Pick a test image
        matching = []
        for m in metadata:
            if m.get("category") == cat:
                img_p = find_image_path(m)
                if img_p:
                    matching.append((m, img_p))
                    break
        if not matching:
            continue
        test_item, test_img_path = matching[0]
        img = Image.open(test_img_path).convert("RGB")

        # Step A: ViT Classification
        t0 = time.time()
        vit_inputs = vit_processor(images=img, return_tensors="pt")["pixel_values"].to(device)
        with torch.no_grad():
            vit_out = vit_backbone(pixel_values=vit_inputs)
            feat = vit_out.last_hidden_state[:, 0, :]
            logits = classifier_head(feat)
            probs = torch.softmax(logits, dim=-1)[0]
            conf, pred_id = probs.max(dim=-1)
            pred_class = id2label[pred_id.item()]
            conf_pct = conf.item() * 100.0
        vit_time = (time.time() - t0) * 1000

        # Step B: CLIP Embedding
        t1 = time.time()
        clip_inputs = clip_processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = clip_model.get_image_features(**clip_inputs)
            embeds = outputs.pooler_output if hasattr(outputs, "pooler_output") else outputs
            norm_feat = (embeds / embeds.norm(p=2, dim=-1, keepdim=True)).cpu().numpy().astype("float32")
        clip_time = (time.time() - t1) * 1000

        # Step C: FAISS Search
        t2 = time.time()
        scores, indices = index.search(norm_feat, 5)
        faiss_time = (time.time() - t2) * 1000

        retrieved_items = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0]), start=1):
            pid = product_ids[idx]
            p_meta = id_to_meta.get(pid, {})
            retrieved_items.append((pid, p_meta.get("name", "Unknown"), p_meta.get("category", "Unknown"), float(score)))

        print(f"\n--- Query: {cat} ({test_item['name']}) ---")
        print(f"  ViT Classification: [{pred_class}] ({conf_pct:.1f}%) in {vit_time:.1f}ms")
        print(f"  CLIP Embedding: {norm_feat.shape} in {clip_time:.1f}ms")
        print(f"  FAISS Search: {len(retrieved_items)} results in {faiss_time:.2f}ms")
        print("  Top-3 Retrieved DeepFashion Products:")
        for pid, name, pcat, score in retrieved_items[:3]:
            print(f"    - ID {pid}: {name} (Category: {pcat}, Similarity: {score:.4f})")

if __name__ == "__main__":
    test_pipeline()
