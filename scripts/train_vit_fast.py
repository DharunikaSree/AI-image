"""
Fast & High-Accuracy Vision Transformer (ViT) Fashion Classifier Pipeline.
Extracts ViT 768-dim features across train/val/test splits, trains an optimized
classifier head with label smoothing & cosine learning rate scheduling, evaluates
accuracy/precision/recall/F1, tests sample predictions, and saves full ViT model.
"""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from transformers import AutoImageProcessor, ViTModel, ViTForImageClassification

# Setup directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
MODELS_DIR = os.path.join(PROJECT_ROOT, "models", "vit_fashion_classifier")
os.makedirs(MODELS_DIR, exist_ok=True)

METADATA_PATH = os.path.join(DATA_DIR, "deepfashion_metadata.json")
EVAL_REPORT_PATH = os.path.join(DATA_DIR, "vit_classification_report.json")
CLASS_MAPPING_PATH = os.path.join(MODELS_DIR, "class_mapping.json")

BASE_VIT_MODEL = "google/vit-base-patch16-224"

# Standardized fashion categories mapping
CATEGORY_STANDARDIZATION = {
    # Footwear
    "Shoes": "Shoes",
    "Sneakers": "Shoes",
    "Casual Shoes": "Shoes",
    "Sports Shoes": "Shoes",
    "Formal Shoes": "Shoes",
    "Heels": "Shoes",
    "Sandals": "Shoes",
    "Flip Flops": "Shoes",
    # Tops / Shirts
    "Shirt": "Shirt",
    "Shirts": "Shirt",
    "T-Shirt": "T-Shirt",
    "Tshirts": "T-Shirt",
    "Tops": "Shirt",
    "Tunics": "Shirt",
    # Traditional
    "Kurta": "Kurta",
    "Kurtas": "Kurta",
    "Kurtis": "Kurta",
    "Saree": "Saree",
    "Sarees": "Saree",
    # Dresses
    "Dress": "Dress",
    "Dresses": "Dress",
    # Bottoms
    "Jeans": "Jeans",
    "Trousers": "Trousers",
    "Track Pants": "Trousers",
    "Shorts": "Shorts",
    "Skirts": "Skirts",
    "Skirt": "Skirts",
    # Outerwear
    "Jacket": "Jacket",
    "Jackets": "Jacket",
    "Sweater": "Sweater",
    "Sweaters": "Sweater",
    "Hoodie": "Hoodie",
    "Sweatshirts": "Hoodie",
    # Accessories
    "Watches": "Watches",
    "Handbags": "Handbags",
    "Clutches": "Handbags",
    "Backpacks": "Handbags",
}

# Target classes for the ViT classifier
TARGET_CLASSES = [
    "Shoes",
    "Shirt",
    "T-Shirt",
    "Kurta",
    "Dress",
    "Saree",
    "Jeans",
    "Trousers",
    "Shorts",
    "Jacket",
    "Sweater",
    "Hoodie",
    "Watches",
    "Handbags"
]


def prepare_dataset_splits(samples_per_class: int = 150) -> Tuple[List[Dict], List[Dict], List[Dict], Dict[str, int], Dict[int, str]]:
    print(f"[*] Loading DeepFashion metadata from: {METADATA_PATH}")
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    label2id = {cls_name: i for i, cls_name in enumerate(TARGET_CLASSES)}
    id2label = {i: cls_name for i, cls_name in enumerate(TARGET_CLASSES)}

    class_buckets: Dict[str, List[Dict]] = {cls_name: [] for cls_name in TARGET_CLASSES}
    for item in metadata:
        raw_cat = item.get("category", "")
        raw_art = item.get("article_type", "")

        mapped_cat = None
        if raw_art in CATEGORY_STANDARDIZATION:
            mapped_cat = CATEGORY_STANDARDIZATION[raw_art]
        elif raw_cat in CATEGORY_STANDARDIZATION:
            mapped_cat = CATEGORY_STANDARDIZATION[raw_cat]

        if mapped_cat in class_buckets and os.path.exists(item.get("image_path", "")):
            class_buckets[mapped_cat].append({
                "id": item["id"],
                "name": item["name"],
                "image_path": item["image_path"],
                "category": mapped_cat,
                "label": label2id[mapped_cat]
            })

    balanced_samples = []
    print("\n--- Dataset Class Distribution ---")
    for cls_name, items in class_buckets.items():
        count = len(items)
        selected = items[:samples_per_class] if samples_per_class > 0 else items
        balanced_samples.extend(selected)
        print(f"  Class [{cls_name:10s}]: {count:5d} available -> {len(selected):4d} in training pool")

    print(f"\n[*] Total samples selected: {len(balanced_samples)}")

    labels = [s["label"] for s in balanced_samples]

    # Stratified Train (70%), Temp (30%)
    train_samples, temp_samples, _, temp_labels = train_test_split(
        balanced_samples, labels, test_size=0.30, stratify=labels, random_state=42
    )

    # Stratified Val (15%), Test (15%)
    val_samples, test_samples = train_test_split(
        temp_samples, test_size=0.50, stratify=temp_labels, random_state=42
    )

    print(f"[+] Dataset Splits: Train={len(train_samples)} (70%), Val={len(val_samples)} (15%), Test={len(test_samples)} (15%)")
    return train_samples, val_samples, test_samples, label2id, id2label


def extract_vit_features(samples: List[Dict], vit_model: ViTModel, processor, device: torch.device, batch_size: int = 32) -> Tuple[torch.Tensor, torch.Tensor]:
    """
    Extracts 768-dim [CLS] token feature vectors in batches for maximum speed.
    """
    all_features = []
    all_labels = []
    total = len(samples)
    vit_model.eval()

    start_t = time.time()
    for i in range(0, total, batch_size):
        batch = samples[i:i + batch_size]
        images = []
        for s in batch:
            try:
                img = Image.open(s["image_path"]).convert("RGB")
            except Exception:
                img = Image.new("RGB", (224, 224), color=(0, 0, 0))
            images.append(img)

        inputs = processor(images=images, return_tensors="pt")
        pixel_values = inputs["pixel_values"].to(device)

        with torch.no_grad():
            outputs = vit_model(pixel_values=pixel_values)
            # Use deterministic [CLS] token representation from transformer encoder
            feat = outputs.last_hidden_state[:, 0, :]

        all_features.append(feat.cpu())
        all_labels.extend([s["label"] for s in batch])

        if (i + batch_size) % 320 == 0 or (i + batch_size) >= total:
            elapsed = time.time() - start_t
            rate = len(all_labels) / max(elapsed, 0.001)
            print(f"    Extracted: {min(i + batch_size, total)}/{total} samples ({rate:.1f} img/s)", flush=True)

    features_tensor = torch.cat(all_features, dim=0)
    labels_tensor = torch.tensor(all_labels, dtype=torch.long)
    return features_tensor, labels_tensor


def run_pipeline():
    print("=" * 70)
    print("   Lumiere AI - Vision Transformer (ViT) Fashion Classifier")
    print("=" * 70)

    # 1. Device check
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"[*] Compute Device: GPU ({torch.cuda.get_device_name(0)})")
    else:
        device = torch.device("cpu")
        torch.set_num_threads(8)
        print(f"[*] Compute Device: CPU (Optimized with {torch.get_num_threads()} threads)")

    # 2. Data Preparation
    train_samples, val_samples, test_samples, label2id, id2label = prepare_dataset_splits(samples_per_class=150)

    # 3. Load Base ViT Model & Processor
    print(f"\n[*] Loading Pretrained ViT Backbone: {BASE_VIT_MODEL}")
    processor = AutoImageProcessor.from_pretrained(BASE_VIT_MODEL)
    vit_backbone = ViTModel.from_pretrained(BASE_VIT_MODEL).to(device)
    vit_backbone.eval()

    # 4. Fast Feature Extraction
    print(f"\n[*] Extracting ViT 768-dim features for Train Split ({len(train_samples)} samples)...")
    train_features, train_labels = extract_vit_features(train_samples, vit_backbone, processor, device, batch_size=32)

    print(f"[*] Extracting ViT 768-dim features for Val Split ({len(val_samples)} samples)...")
    val_features, val_labels = extract_vit_features(val_samples, vit_backbone, processor, device, batch_size=32)

    print(f"[*] Extracting ViT 768-dim features for Test Split ({len(test_samples)} samples)...")
    test_features, test_labels = extract_vit_features(test_samples, vit_backbone, processor, device, batch_size=32)

    # 5. Train Classifier Head
    num_classes = len(TARGET_CLASSES)
    classifier_head = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(768, 256),
        nn.GELU(),
        nn.LayerNorm(256),
        nn.Dropout(0.2),
        nn.Linear(256, num_classes)
    ).to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    optimizer = torch.optim.AdamW(classifier_head.parameters(), lr=1e-3, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=25)

    epochs = 25
    batch_size = 64
    num_train = len(train_features)
    best_val_acc = 0.0
    best_weights = None

    print(f"\n[*] Training Classifier Head for {epochs} epochs on precomputed ViT representations...")
    train_start = time.time()

    for epoch in range(1, epochs + 1):
        classifier_head.train()
        perm = torch.randperm(num_train)
        running_loss = 0.0
        correct = 0

        for b_start in range(0, num_train, batch_size):
            indices = perm[b_start:b_start + batch_size]
            b_feats = train_features[indices].to(device)
            b_targets = train_labels[indices].to(device)

            optimizer.zero_grad()
            logits = classifier_head(b_feats)
            loss = criterion(logits, b_targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * len(indices)
            preds = logits.argmax(dim=-1)
            correct += (preds == b_targets).sum().item()

        scheduler.step()
        train_loss = running_loss / num_train
        train_acc = (correct / num_train) * 100.0

        # Val check
        classifier_head.eval()
        with torch.no_grad():
            v_logits = classifier_head(val_features.to(device))
            v_loss = criterion(v_logits, val_labels.to(device)).item()
            v_preds = v_logits.argmax(dim=-1)
            val_acc = (v_preds == val_labels.to(device)).float().mean().item() * 100.0

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_weights = classifier_head.state_dict()

        if epoch % 5 == 0 or epoch == epochs or epoch == 1:
            print(f"  Epoch [{epoch:2d}/{epochs:2d}] | Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | Val Loss: {v_loss:.4f} Acc: {val_acc:.2f}% (Best: {best_val_acc:.2f}%)", flush=True)

    training_time = time.time() - train_start
    print(f"\n[+] Classifier Head Training Complete in {training_time:.2f}s! Best Val Accuracy: {best_val_acc:.2f}%")

    # 6. Evaluation on Unseen Test Dataset
    print("\n" + "=" * 70)
    print(">>> Final Evaluation on Unseen Test Dataset (15% Split):")
    print("=" * 70)

    classifier_head.load_state_dict(best_weights)
    classifier_head.eval()

    with torch.no_grad():
        test_logits = classifier_head(test_features.to(device))
        test_probs = torch.softmax(test_logits, dim=-1)
        test_confs, test_preds = test_probs.max(dim=-1)

    y_true = test_labels.numpy()
    y_pred = test_preds.cpu().numpy()

    overall_acc = accuracy_score(y_true, y_pred) * 100.0
    prec_macro, rec_macro, f1_macro, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    prec_weighted, rec_weighted, f1_weighted, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)

    print(f"\n[*] Test Metrics ({len(y_true)} test images):")
    print(f"    - Accuracy:            {overall_acc:.2f}%")
    print(f"    - Precision (Macro):   {prec_macro * 100:.2f}%")
    print(f"    - Recall (Macro):      {rec_macro * 100:.2f}%")
    print(f"    - F1-Score (Macro):    {f1_macro * 100:.2f}%")
    print(f"    - F1-Score (Weighted): {f1_weighted * 100:.2f}%")

    print("\n--- Per-Class Classification Report ---")
    cls_report_str = classification_report(y_true, y_pred, target_names=TARGET_CLASSES, digits=4, zero_division=0)
    cls_report_dict = classification_report(y_true, y_pred, target_names=TARGET_CLASSES, output_dict=True, zero_division=0)
    print(cls_report_str)

    # 7. Assemble and Save Full ViT Model Architecture
    print(f"\n[*] Assembling and saving full ViT Model to: {MODELS_DIR}")
    full_vit_model = ViTForImageClassification.from_pretrained(
        BASE_VIT_MODEL,
        num_labels=num_classes,
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True
    )

    # Convert two-layer head into linear classifier weights approximation or save custom head
    torch.save({
        "classifier_head_state_dict": classifier_head.state_dict(),
        "label2id": label2id,
        "id2label": id2label,
        "target_classes": TARGET_CLASSES,
        "base_model": BASE_VIT_MODEL,
        "test_accuracy": overall_acc,
        "test_f1_macro": f1_macro
    }, os.path.join(MODELS_DIR, "vit_fashion_classifier.pt"))

    processor.save_pretrained(MODELS_DIR)
    full_vit_model.save_pretrained(MODELS_DIR)

    with open(CLASS_MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "target_classes": TARGET_CLASSES,
            "label2id": label2id,
            "id2label": id2label,
            "base_model": BASE_VIT_MODEL
        }, f, indent=2)

    # 8. Sample Predictions on Key Required Categories (Shoes, Shirts, Dresses, Sarees)
    print("=" * 70)
    print(">>> Sample Test Image Predictions (Shoes, Shirts, Dresses, Sarees):")
    print("=" * 70)

    sample_categories = ["Shoes", "Shirt", "Dress", "Saree", "Kurta", "Watches", "Handbags", "Jeans"]
    sample_tests = []

    for target_cat in sample_categories:
        matched = [s for s in test_samples if s["category"] == target_cat][:2]
        for s in matched:
            img = Image.open(s["image_path"]).convert("RGB")
            inp = processor(images=img, return_tensors="pt")["pixel_values"].to(device)
            with torch.no_grad():
                out = vit_backbone(pixel_values=inp)
                feat = out.last_hidden_state[:, 0, :]
                logits = classifier_head(feat)
                probs = torch.softmax(logits, dim=-1)[0]
                conf, pred_id = probs.max(dim=-1)
                predicted_class = id2label[pred_id.item()]
                confidence_pct = conf.item() * 100.0

            is_correct = predicted_class == target_cat
            status_tag = "[CORRECT]" if is_correct else "[MISMATCH]"
            print(f"  {status_tag} Ground Truth: {target_cat:10s} | Predicted: {predicted_class:10s} ({confidence_pct:.1f}%) | Item: {s['name']}")

            sample_tests.append({
                "product_id": s["id"],
                "product_name": s["name"],
                "ground_truth": target_cat,
                "predicted_class": predicted_class,
                "confidence_percent": round(confidence_pct, 2),
                "is_correct": is_correct,
                "image_path": s["image_path"]
            })

    # Save final report
    eval_summary = {
        "model_architecture": "Vision Transformer (ViT-Base/16)",
        "base_pretrained_weights": BASE_VIT_MODEL,
        "input_resolution": "224x224",
        "num_classes": len(TARGET_CLASSES),
        "target_classes": TARGET_CLASSES,
        "device": str(device),
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "test_samples": len(test_samples),
        "test_metrics": {
            "accuracy_percent": round(overall_acc, 2),
            "macro_precision_percent": round(prec_macro * 100, 2),
            "macro_recall_percent": round(rec_macro * 100, 2),
            "macro_f1_percent": round(f1_macro * 100, 2),
            "weighted_f1_percent": round(f1_weighted * 100, 2)
        },
        "per_class_metrics": cls_report_dict,
        "saved_model_path": os.path.relpath(MODELS_DIR, PROJECT_ROOT),
        "sample_predictions": sample_tests,
        "status": "Phase 4 ViT Classification Completed Successfully"
    }

    with open(EVAL_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_summary, f, indent=2)
    print(f"\n[+] Saved evaluation report to: {EVAL_REPORT_PATH}")

    print("\n" + "=" * 70)
    print(f"[OK] ViT Model Training & Evaluation Complete! Test Accuracy: {overall_acc:.2f}% | F1: {f1_macro*100:.2f}%")
    print(f"     Model saved to: {MODELS_DIR}")
    print("=" * 70)

    return eval_summary


if __name__ == "__main__":
    run_pipeline()
