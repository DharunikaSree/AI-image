"""
Standalone Evaluation Script for Vision Transformer (ViT) Fashion Classifier.
Calculates rigorous, reproducible experimental performance metrics for academic project/conference report.

Tasks:
1. Loads trained ViT model weights and class mappings (read-only; no retraining or overwriting).
2. Establishes the isolated labelled test dataset.
3. Evaluates real model inference across all test images.
4. Computes Accuracy, Macro Precision, Macro Recall, and Macro F1-score via scikit-learn.
5. Generates per-class classification report (precision, recall, F1, support).
6. Plots and saves Confusion Matrix image.
7. Saves results to CSV files and JSON report, and prints terminal summary.
"""
from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from PIL import Image
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    classification_report,
    confusion_matrix,
    ConfusionMatrixDisplay
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from transformers import AutoImageProcessor, ViTModel

# Define paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" / "vit_fashion_classifier"
REPORTS_DIR = PROJECT_ROOT / "data"

METADATA_PATH = DATA_DIR / "deepfashion_metadata.json"
CHECKPOINT_PATH = MODELS_DIR / "vit_fashion_classifier.pt"
CLASS_MAPPING_PATH = MODELS_DIR / "class_mapping.json"
TEST_DATASET_JSON_PATH = DATA_DIR / "vit_test_dataset.json"
TEST_DATASET_CSV_PATH = DATA_DIR / "vit_test_dataset.csv"

CONFUSION_MATRIX_IMG_PATH = DATA_DIR / "vit_confusion_matrix.png"
METRICS_CSV_PATH = DATA_DIR / "vit_evaluation_metrics.csv"
PER_CLASS_CSV_PATH = DATA_DIR / "vit_per_class_metrics.csv"
PREDICTIONS_CSV_PATH = DATA_DIR / "vit_test_predictions.csv"
FULL_REPORT_JSON_PATH = DATA_DIR / "vit_evaluation_report.json"

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

CATEGORY_STANDARDIZATION = {
    # Footwear
    "Shoes": "Shoes", "Sneakers": "Shoes", "Casual Shoes": "Shoes", "Sports Shoes": "Shoes",
    "Formal Shoes": "Shoes", "Heels": "Shoes", "Sandals": "Shoes", "Flip Flops": "Shoes",
    # Tops / Shirts
    "Shirt": "Shirt", "Shirts": "Shirt", "T-Shirt": "T-Shirt", "Tshirts": "T-Shirt",
    "Tops": "Shirt", "Tunics": "Shirt",
    # Traditional
    "Kurta": "Kurta", "Kurtas": "Kurta", "Kurtis": "Kurta", "Saree": "Saree", "Sarees": "Saree",
    # Dresses
    "Dress": "Dress", "Dresses": "Dress",
    # Bottoms
    "Jeans": "Jeans", "Trousers": "Trousers", "Track Pants": "Trousers", "Shorts": "Shorts",
    "Skirts": "Skirts", "Skirt": "Skirts",
    # Outerwear
    "Jacket": "Jacket", "Jackets": "Jacket", "Sweater": "Sweater", "Sweaters": "Sweater",
    "Hoodie": "Hoodie", "Sweatshirts": "Hoodie",
    # Accessories
    "Watches": "Watches", "Handbags": "Handbags", "Clutches": "Handbags", "Backpacks": "Handbags",
}


def load_model_and_mappings(device: torch.device):
    """Loads ViT backbone and trained classifier head in evaluation mode."""
    print(f"[*] Loading class mapping from: {CLASS_MAPPING_PATH}")
    with open(CLASS_MAPPING_PATH, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    id2label = {int(k): v for k, v in mapping["id2label"].items()}
    label2id = mapping["label2id"]
    target_classes = mapping["target_classes"]
    base_model = mapping.get("base_model", "google/vit-base-patch16-224")

    print(f"[*] Loading ViT image processor and backbone ({base_model})...")
    processor = AutoImageProcessor.from_pretrained(base_model)
    vit_backbone = ViTModel.from_pretrained(base_model).to(device)
    vit_backbone.eval()

    print(f"[*] Loading trained classifier head checkpoint from: {CHECKPOINT_PATH}")
    ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)

    classifier_head = nn.Sequential(
        nn.Dropout(0.3),
        nn.Linear(768, 256),
        nn.GELU(),
        nn.LayerNorm(256),
        nn.Dropout(0.2),
        nn.Linear(256, len(target_classes))
    ).to(device)

    classifier_head.load_state_dict(ckpt["classifier_head_state_dict"])
    classifier_head.eval()

    return processor, vit_backbone, classifier_head, target_classes, label2id, id2label, ckpt


def get_or_create_test_dataset(label2id: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    Checks if a separate test dataset file already exists;
    if not, isolates the held-out test split (15% split, random_state=42) from metadata
    and saves it to disk for permanent reproducibility.
    """
    if TEST_DATASET_JSON_PATH.exists():
        print(f"[+] Found existing test dataset file at: {TEST_DATASET_JSON_PATH}")
        with open(TEST_DATASET_JSON_PATH, "r", encoding="utf-8") as f:
            test_samples = json.load(f)
        # Verify images exist
        valid_samples = [s for s in test_samples if os.path.exists(s.get("image_path", ""))]
        print(f"    Loaded {len(valid_samples)} valid test image records from test dataset file.")
        return valid_samples

    print(f"[*] No standalone test dataset file found. Isolating test split from: {METADATA_PATH}")
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    class_buckets: Dict[str, List[Dict]] = {cls_name: [] for cls_name in TARGET_CLASSES}
    for item in metadata:
        raw_cat = item.get("category", "")
        raw_art = item.get("article_type", "")

        mapped_cat = None
        if raw_art in CATEGORY_STANDARDIZATION:
            mapped_cat = CATEGORY_STANDARDIZATION[raw_art]
        elif raw_cat in CATEGORY_STANDARDIZATION:
            mapped_cat = CATEGORY_STANDARDIZATION[raw_cat]

        img_path = item.get("image_path", "")
        if mapped_cat in class_buckets and os.path.exists(img_path):
            class_buckets[mapped_cat].append({
                "id": item["id"],
                "name": item["name"],
                "image_path": img_path,
                "category": mapped_cat,
                "label": label2id[mapped_cat]
            })

    # Balanced pool (150 samples per class matching training protocol)
    balanced_samples = []
    for cls_name in TARGET_CLASSES:
        items = class_buckets[cls_name]
        selected = items[:150]
        balanced_samples.extend(selected)

    labels = [s["label"] for s in balanced_samples]

    # Stratified Train (70%), Temp (30%)
    train_samples, temp_samples, _, temp_labels = train_test_split(
        balanced_samples, labels, test_size=0.30, stratify=labels, random_state=42
    )

    # Stratified Val (15%), Test (15%)
    val_samples, test_samples = train_test_split(
        temp_samples, test_size=0.50, stratify=temp_labels, random_state=42
    )

    print(f"[+] Isolated {len(test_samples)} test samples (15% held-out test split, stratified).")

    # Save to disk as dedicated test dataset files
    with open(TEST_DATASET_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(test_samples, f, indent=2)

    df_test = pd.DataFrame(test_samples)
    df_test.to_csv(TEST_DATASET_CSV_PATH, index=False)

    print(f"[+] Saved dedicated test dataset to:")
    print(f"    - JSON: {TEST_DATASET_JSON_PATH}")
    print(f"    - CSV:  {TEST_DATASET_CSV_PATH}")

    return test_samples


def extract_vit_features_batched(
    samples: List[Dict[str, Any]],
    vit_backbone: ViTModel,
    processor: AutoImageProcessor,
    device: torch.device,
    batch_size: int = 32
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Extracts [CLS] token representations for the test images in batches."""
    all_features = []
    all_labels = []
    total = len(samples)

    print(f"[*] Running ViT feature extraction on {total} test images (batch_size={batch_size})...")
    start_time = time.time()

    for idx in range(0, total, batch_size):
        batch_samples = samples[idx: idx + batch_size]
        batch_imgs = []
        batch_targets = []

        for item in batch_samples:
            img_path = item["image_path"]
            try:
                img = Image.open(img_path).convert("RGB")
            except Exception:
                img = Image.new("RGB", (224, 224), color=(0, 0, 0))
            batch_imgs.append(img)
            batch_targets.append(item["label"])

        processed = processor(images=batch_imgs, return_tensors="pt")
        pixel_values = processed["pixel_values"].to(device)

        with torch.no_grad():
            outputs = vit_backbone(pixel_values=pixel_values)
            cls_features = outputs.last_hidden_state[:, 0, :]

        all_features.append(cls_features.cpu())
        all_labels.extend(batch_targets)

        done = min(idx + batch_size, total)
        print(f"    Processed {done:3d}/{total} images ({(done/total)*100:.1f}%)", end="\r", flush=True)

    elapsed = time.time() - start_time
    print(f"\n[+] Feature extraction complete in {elapsed:.2f}s ({elapsed/total*1000:.1f} ms/image)")

    return torch.cat(all_features, dim=0), torch.tensor(all_labels, dtype=torch.long)


def evaluate_classifier(
    classifier_head: nn.Module,
    features: torch.Tensor,
    labels: torch.Tensor,
    test_samples: List[Dict[str, Any]],
    target_classes: List[str],
    id2label: Dict[int, str],
    device: torch.device
):
    """Computes exact metrics, confusion matrix, classification report, and CSV logs."""
    print("\n" + "=" * 75)
    print("   RUNNING RIGOROUS SCIENTIFIC EVALUATION")
    print("=" * 75)

    with torch.no_grad():
        logits = classifier_head(features.to(device))
        probs = torch.softmax(logits, dim=-1)
        confs, preds = probs.max(dim=-1)

    y_true = labels.numpy()
    y_pred = preds.cpu().numpy()
    y_conf = confs.cpu().numpy()

    # 1. Overall Metrics
    overall_acc = accuracy_score(y_true, y_pred) * 100.0
    prec_macro, rec_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    prec_weighted, rec_weighted, f1_weighted, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    macro_precision_pct = prec_macro * 100.0
    macro_recall_pct = rec_macro * 100.0
    macro_f1_pct = f1_macro * 100.0
    weighted_f1_pct = f1_weighted * 100.0

    # 2. Classification Report
    cls_report_dict = classification_report(
        y_true, y_pred, target_names=target_classes, output_dict=True, zero_division=0
    )
    cls_report_str = classification_report(
        y_true, y_pred, target_names=target_classes, digits=4, zero_division=0
    )

    # 3. Confusion Matrix
    cm = confusion_matrix(y_true, y_pred)

    # Plot Confusion Matrix
    fig, ax = plt.subplots(figsize=(12, 10))
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=target_classes)
    disp.plot(ax=ax, cmap="Blues", values_format="d", colorbar=True, xticks_rotation=45)
    ax.set_title("Vision Transformer (ViT-Base/16) Fashion Classification\nConfusion Matrix on Unseen Test Dataset", fontsize=14, pad=15)
    plt.tight_layout()
    fig.savefig(CONFUSION_MATRIX_IMG_PATH, dpi=300)
    plt.close(fig)
    print(f"\n[+] Saved Confusion Matrix visualization to: {CONFUSION_MATRIX_IMG_PATH}")

    # 4. Save Overall Metrics CSV
    metrics_summary_data = [
        {"Metric": "Accuracy", "Value (%)": round(overall_acc, 2), "Raw Value": round(overall_acc / 100.0, 4)},
        {"Metric": "Macro Precision", "Value (%)": round(macro_precision_pct, 2), "Raw Value": round(prec_macro, 4)},
        {"Metric": "Macro Recall", "Value (%)": round(macro_recall_pct, 2), "Raw Value": round(rec_macro, 4)},
        {"Metric": "Macro F1-Score", "Value (%)": round(macro_f1_pct, 2), "Raw Value": round(f1_macro, 4)},
        {"Metric": "Weighted Precision", "Value (%)": round(prec_weighted * 100.0, 2), "Raw Value": round(prec_weighted, 4)},
        {"Metric": "Weighted Recall", "Value (%)": round(rec_weighted * 100.0, 2), "Raw Value": round(rec_weighted, 4)},
        {"Metric": "Weighted F1-Score", "Value (%)": round(weighted_f1_pct, 2), "Raw Value": round(f1_weighted, 4)},
        {"Metric": "Total Test Samples", "Value (%)": len(y_true), "Raw Value": len(y_true)},
        {"Metric": "Number of Classes", "Value (%)": len(target_classes), "Raw Value": len(target_classes)},
    ]
    df_metrics = pd.DataFrame(metrics_summary_data)
    df_metrics.to_csv(METRICS_CSV_PATH, index=False)
    print(f"[+] Saved Overall Metrics to: {METRICS_CSV_PATH}")

    # 5. Save Per-Class Classification Report CSV
    per_class_rows = []
    for cls_name in target_classes:
        row = cls_report_dict[cls_name]
        per_class_rows.append({
            "Clothing Category": cls_name,
            "Precision": round(row["precision"], 4),
            "Recall": round(row["recall"], 4),
            "F1-Score": round(row["f1-score"], 4),
            "Sample Count (Support)": int(row["support"])
        })
    # Add Macro and Weighted Averages
    per_class_rows.append({
        "Clothing Category": "Macro Average",
        "Precision": round(cls_report_dict["macro avg"]["precision"], 4),
        "Recall": round(cls_report_dict["macro avg"]["recall"], 4),
        "F1-Score": round(cls_report_dict["macro avg"]["f1-score"], 4),
        "Sample Count (Support)": int(cls_report_dict["macro avg"]["support"])
    })
    per_class_rows.append({
        "Clothing Category": "Weighted Average",
        "Precision": round(cls_report_dict["weighted avg"]["precision"], 4),
        "Recall": round(cls_report_dict["weighted avg"]["recall"], 4),
        "F1-Score": round(cls_report_dict["weighted avg"]["f1-score"], 4),
        "Sample Count (Support)": int(cls_report_dict["weighted avg"]["support"])
    })
    df_per_class = pd.DataFrame(per_class_rows)
    df_per_class.to_csv(PER_CLASS_CSV_PATH, index=False)
    print(f"[+] Saved Per-Class Report to: {PER_CLASS_CSV_PATH}")

    # 6. Save Detailed Predictions CSV
    detailed_predictions = []
    for idx, sample in enumerate(test_samples):
        pred_label_id = int(y_pred[idx])
        pred_label_name = id2label[pred_label_id]
        true_label_name = sample["category"]
        conf_pct = float(y_conf[idx] * 100.0)
        is_corr = (pred_label_name == true_label_name)

        detailed_predictions.append({
            "product_id": sample["id"],
            "product_name": sample["name"],
            "ground_truth": true_label_name,
            "predicted_category": pred_label_name,
            "confidence_percent": round(conf_pct, 2),
            "is_correct": is_corr,
            "image_path": sample["image_path"]
        })
    df_preds = pd.DataFrame(detailed_predictions)
    df_preds.to_csv(PREDICTIONS_CSV_PATH, index=False)
    print(f"[+] Saved Per-Sample Predictions to: {PREDICTIONS_CSV_PATH}")

    # 7. Save Comprehensive JSON Report
    full_report = {
        "model_architecture": "Vision Transformer (ViT-Base/16)",
        "base_pretrained_weights": "google/vit-base-patch16-224",
        "input_resolution": "224x224",
        "num_classes": len(target_classes),
        "target_classes": target_classes,
        "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "test_dataset_size": len(y_true),
        "test_metrics": {
            "accuracy_percent": round(overall_acc, 2),
            "macro_precision_percent": round(macro_precision_pct, 2),
            "macro_recall_percent": round(macro_recall_pct, 2),
            "macro_f1_percent": round(macro_f1_pct, 2),
            "weighted_f1_percent": round(weighted_f1_pct, 2)
        },
        "per_class_metrics": cls_report_dict,
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_image": str(CONFUSION_MATRIX_IMG_PATH),
        "metrics_csv": str(METRICS_CSV_PATH),
        "per_class_csv": str(PER_CLASS_CSV_PATH),
        "predictions_csv": str(PREDICTIONS_CSV_PATH)
    }
    with open(FULL_REPORT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"[+] Saved JSON Evaluation Summary to: {FULL_REPORT_JSON_PATH}")

    # 8. Print Terminal Summary
    print("\n" + "=" * 75)
    print("                     EVALUATION RESULTS SUMMARY")
    print("=" * 75)
    print(f" Model Architecture   : Vision Transformer (ViT-Base/16)")
    print(f" Backbone Pretrained  : google/vit-base-patch16-224")
    print(f" Number of Classes    : {len(target_classes)}")
    print(f" Evaluated Test Images: {len(y_true)} (Unseen held-out split)")
    print("-" * 75)
    print(f"  * Overall Accuracy   : {overall_acc:.2f}%")
    print(f"  * Macro Precision    : {macro_precision_pct:.2f}%")
    print(f"  * Macro Recall       : {macro_recall_pct:.2f}%")
    print(f"  * Macro F1-Score     : {macro_f1_pct:.2f}%")
    print(f"  * Weighted F1-Score  : {weighted_f1_pct:.2f}%")
    print("-" * 75)
    print("\n--- PER-CLASS PERFORMANCE TABLE ---")
    print(cls_report_str)
    print("=" * 75)

    return overall_acc, macro_precision_pct, macro_recall_pct, macro_f1_pct, df_per_class


def main():
    device = torch.device("cpu")
    torch.set_num_threads(8)
    print(f"[*] Evaluation Device: {device} (Thread count: {torch.get_num_threads()})")

    # 1. Load Model & Mapping (Read-Only)
    processor, vit_backbone, classifier_head, target_classes, label2id, id2label, ckpt = load_model_and_mappings(device)

    # 2. Get / Isolate Test Dataset
    test_samples = get_or_create_test_dataset(label2id)

    # 3. Extract Features for Test Images
    features, labels = extract_vit_features_batched(test_samples, vit_backbone, processor, device, batch_size=32)

    # 4. Evaluate and generate all metrics, confusion matrix, CSVs
    evaluate_classifier(classifier_head, features, labels, test_samples, target_classes, id2label, device)


if __name__ == "__main__":
    main()
