"""
Vision Transformer (ViT) Fashion Image Classification Pipeline.
Phase 4: Train, Evaluate, and Test ViT on DeepFashion fashion categories.

Metrics:
- Accuracy, Precision (Macro & Weighted), Recall (Macro & Weighted), F1-Score (Macro & Weighted)
- Per-class classification report
- Sample predictions on real images (Shoes, Shirts, Dresses, Sarees, etc.)
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
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
from transformers import AutoImageProcessor, ViTForImageClassification

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


class FashionDataset(Dataset):
    def __init__(self, samples: List[Dict[str, Any]], image_processor):
        self.samples = samples
        self.processor = image_processor

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        item = self.samples[idx]
        img_path = item["image_path"]
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception:
            img = Image.new("RGB", (224, 224), color=(0, 0, 0))

        processed = self.processor(images=img, return_tensors="pt")
        pixel_values = processed["pixel_values"].squeeze(0)
        label = item["label"]

        return pixel_values, label, item["id"], img_path


def prepare_data(max_samples_per_class: int = 250) -> Tuple[List[Dict], List[Dict], List[Dict], Dict[str, int], Dict[int, str]]:
    print(f"[*] Loading dataset from: {METADATA_PATH}")
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
        selected = items[:max_samples_per_class] if max_samples_per_class > 0 else items
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


def train_and_evaluate():
    print("=" * 70)
    print("   Lumiere AI - Vision Transformer (ViT) Fashion Classifier")
    print("=" * 70)

    # Set threads for CPU performance
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"[*] Compute Device: GPU ({torch.cuda.get_device_name(0)})")
    else:
        device = torch.device("cpu")
        torch.set_num_threads(8)
        print(f"[*] Compute Device: CPU (Optimized with {torch.get_num_threads()} threads)")

    # 1. Data Preparation
    train_samples, val_samples, test_samples, label2id, id2label = prepare_data(max_samples_per_class=250)

    # 2. Image Processor & Model
    print(f"\n[*] Loading ViT Image Processor and Pretrained Model: {BASE_VIT_MODEL}")
    processor = AutoImageProcessor.from_pretrained(BASE_VIT_MODEL)
    model = ViTForImageClassification.from_pretrained(
        BASE_VIT_MODEL,
        num_labels=len(TARGET_CLASSES),
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True
    )
    model.to(device)

    # Freeze ViT transformer layers and fine-tune classifier + pooling
    for param in model.vit.parameters():
        param.requires_grad = False

    # Unfreeze top encoder block if desired, or train classifier head
    if hasattr(model.vit, "encoder") and hasattr(model.vit.encoder, "layer"):
        for param in model.vit.encoder.layer[-1].parameters():
            param.requires_grad = True

    # 3. DataLoaders
    batch_size = 32 if device.type == "cuda" else 16
    train_dataset = FashionDataset(train_samples, processor)
    val_dataset = FashionDataset(val_samples, processor)
    test_dataset = FashionDataset(test_samples, processor)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    # 4. Optimizer & Scheduler
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=5e-4, weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=4)
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)

    epochs = 4
    print(f"\n[*] Training for {epochs} epochs (Trainable parameters: {sum(p.numel() for p in trainable_params):,})...")

    train_start_time = time.time()
    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for batch_idx, (pixel_vals, targets, _, _) in enumerate(train_loader):
            pixel_vals, targets = pixel_vals.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(pixel_values=pixel_vals)
            logits = outputs.logits
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * targets.size(0)
            preds = logits.argmax(dim=1)
            correct += (preds == targets).sum().item()
            total += targets.size(0)

        scheduler.step()
        train_loss = running_loss / total
        train_acc = (correct / total) * 100.0

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for pixel_vals, targets, _, _ in val_loader:
                pixel_vals, targets = pixel_vals.to(device), targets.to(device)
                outputs = model(pixel_values=pixel_vals)
                logits = outputs.logits
                loss = criterion(logits, targets)
                val_loss += loss.item() * targets.size(0)
                preds = logits.argmax(dim=1)
                val_correct += (preds == targets).sum().item()
                val_total += targets.size(0)

        val_loss = val_loss / val_total
        val_acc = (val_correct / val_total) * 100.0
        epoch_dur = time.time() - epoch_start

        print(f"  Epoch [{epoch}/{epochs}] ({epoch_dur:.1f}s) | Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | Val Loss: {val_loss:.4f} Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            model.save_pretrained(MODELS_DIR)
            processor.save_pretrained(MODELS_DIR)

    train_total_time = time.time() - train_start_time
    print(f"\n[+] Training complete in {train_total_time:.2f}s! Best Validation Accuracy: {best_val_acc:.2f}%")

    # 5. Test Evaluation
    print("\n" + "=" * 70)
    print(">>> Final Evaluation on Unseen Test Dataset (15% Split):")
    print("=" * 70)

    best_model = ViTForImageClassification.from_pretrained(MODELS_DIR).to(device)
    best_model.eval()

    all_preds = []
    all_targets = []
    all_confidences = []

    with torch.no_grad():
        for pixel_vals, targets, _, _ in test_loader:
            pixel_vals = pixel_vals.to(device)
            outputs = best_model(pixel_values=pixel_vals)
            probs = torch.softmax(outputs.logits, dim=-1)
            confs, preds = probs.max(dim=-1)

            all_preds.extend(preds.cpu().numpy().tolist())
            all_targets.extend(targets.numpy().tolist())
            all_confidences.extend(confs.cpu().numpy().tolist())

    y_true = np.array(all_targets)
    y_pred = np.array(all_preds)

    overall_acc = accuracy_score(y_true, y_pred) * 100.0
    prec_macro, rec_macro, f1_macro, _ = precision_recall_fscore_support(y_true, y_pred, average="macro")
    prec_weighted, rec_weighted, f1_weighted, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted")

    print(f"\n[*] Test Metrics ({len(y_true)} test images):")
    print(f"    - Accuracy:           {overall_acc:.2f}%")
    print(f"    - Precision (Macro):  {prec_macro * 100:.2f}%")
    print(f"    - Recall (Macro):     {rec_macro * 100:.2f}%")
    print(f"    - F1-Score (Macro):   {f1_macro * 100:.2f}%")
    print(f"    - F1-Score (Weighted):{f1_weighted * 100:.2f}%")

    print("\n--- Per-Class Classification Report ---")
    cls_report_dict = classification_report(y_true, y_pred, target_names=TARGET_CLASSES, output_dict=True)
    print(classification_report(y_true, y_pred, target_names=TARGET_CLASSES, digits=4))

    # 6. Sample Predictions on Key Required Categories (Shoes, Shirts, Dresses, Sarees)
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
                outputs = best_model(pixel_values=inp)
                probs = torch.softmax(outputs.logits, dim=-1)[0]
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

    # Save Class Mapping and Evaluation Summary
    with open(CLASS_MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "target_classes": TARGET_CLASSES,
            "label2id": label2id,
            "id2label": id2label,
            "base_model": BASE_VIT_MODEL
        }, f, indent=2)

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
        "training_time_seconds": round(train_total_time, 2),
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
    train_and_evaluate()
