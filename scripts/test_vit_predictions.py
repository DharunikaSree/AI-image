import os
import json
import torch
from PIL import Image
from transformers import AutoImageProcessor, ViTModel, ViTForImageClassification

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "vit_fashion_classifier")

METADATA_PATH = os.path.join(DATA_DIR, "deepfashion_metadata.json")
CHECKPOINT_PATH = os.path.join(MODELS_DIR, "vit_fashion_classifier.pt")
CLASS_MAPPING_PATH = os.path.join(MODELS_DIR, "class_mapping.json")

def test_inference():
    print("=" * 70)
    print("   Testing ViT Fashion Classifier Inference with Proper Pooling")
    print("=" * 70)

    device = torch.device("cpu")
    torch.set_num_threads(8)

    # Load mapping
    with open(CLASS_MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)
    id2label = {int(k): v for k, v in mapping["id2label"].items()}
    label2id = mapping["label2id"]
    target_classes = mapping["target_classes"]

    # Load ViT backbone and processor
    processor = AutoImageProcessor.from_pretrained(mapping["base_model"])
    vit_backbone = ViTModel.from_pretrained(mapping["base_model"]).to(device)
    vit_backbone.eval()

    # Load trained classifier head
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

    # Load metadata to find test images for shoes, shirts, dresses, sarees, etc.
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    test_queries = [
        ("Shoes", ["Casual Shoes", "Sports Shoes", "Heels", "Sneakers"]),
        ("Shirt", ["Shirts", "Tops"]),
        ("T-Shirt", ["Tshirts"]),
        ("Dress", ["Dresses"]),
        ("Saree", ["Sarees"]),
        ("Kurta", ["Kurtas"]),
        ("Watches", ["Watches"]),
        ("Handbags", ["Handbags"]),
        ("Jeans", ["Jeans"]),
        ("Shorts", ["Shorts"]),
    ]

    sample_results = []
    print("\n--- ViT Predictions on Real DeepFashion Dataset Images ---")

    for main_cat, art_types in test_queries:
        # Find matching items
        matching = [m for m in metadata if m.get("article_type") in art_types and os.path.exists(m.get("image_path", ""))][:3]
        for item in matching:
            img = Image.open(item["image_path"]).convert("RGB")
            inputs = processor(images=img, return_tensors="pt")["pixel_values"].to(device)

            with torch.no_grad():
                out = vit_backbone(pixel_values=inputs)
                if hasattr(out, "pooler_output") and out.pooler_output is not None:
                    feat = out.pooler_output
                else:
                    feat = out.last_hidden_state[:, 0, :]
                logits = classifier_head(feat)
                probs = torch.softmax(logits, dim=-1)[0]
                conf, pred_id = probs.max(dim=-1)
                pred_class = id2label[pred_id.item()]
                conf_pct = conf.item() * 100.0

            is_correct = (pred_class == main_cat)
            status = "[CORRECT]" if is_correct else "[MISMATCH]"
            print(f"  {status} Ground Truth: {main_cat:10s} | Predicted: {pred_class:10s} ({conf_pct:.1f}%) | Product: {item['name']}")

            sample_results.append({
                "product_id": item["id"],
                "product_name": item["name"],
                "ground_truth": main_cat,
                "predicted_class": pred_class,
                "confidence_percent": round(conf_pct, 2),
                "is_correct": is_correct,
                "image_path": item["image_path"]
            })

    # Save to report
    report_path = os.path.join(DATA_DIR, "vit_classification_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        rep = json.load(f)
    rep["sample_predictions"] = sample_results
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2)
    print(f"\n[+] Updated report saved to: {report_path}")

if __name__ == "__main__":
    test_inference()
