"""
Training & Evaluation Pipeline for Multi-Attribute Fashion Classifier.
Trains multi-task neural network on 512-dim visual embeddings to predict:
- Color (16 classes)
- Style (5 classes)
- Pattern (5 classes)
- Gender (5 classes)
- Season (5 classes)

Features:
- Group-aware train/val/test splitting (GroupShuffleSplit on group_key) to prevent data leakage.
- Multi-task PyTorch architecture with shared representations + dedicated attribute heads.
- Comprehensive scientific evaluation (Accuracy, Precision, Recall, Macro F1, Confusion Matrices).
"""
import os
import json
import random
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report, confusion_matrix
from pathlib import Path

# Deterministic reproducibility
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models" / "multi_attribute_classifier"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Multi-Task PyTorch Model
# ---------------------------------------------------------------------------
class MultiAttributeClassifier(nn.Module):
    def __init__(self, emb_dim: int, num_colors: int, num_styles: int, num_patterns: int, num_genders: int, num_seasons: int):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(emb_dim, 256),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.LayerNorm(256),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.LayerNorm(128),
        )
        self.color_head = nn.Linear(128, num_colors)
        self.style_head = nn.Linear(128, num_styles)
        self.pattern_head = nn.Linear(128, num_patterns)
        self.gender_head = nn.Linear(128, num_genders)
        self.season_head = nn.Linear(128, num_seasons)

    def forward(self, x: torch.Tensor):
        feat = self.shared(x)
        return {
            "color": self.color_head(feat),
            "style": self.style_head(feat),
            "pattern": self.pattern_head(feat),
            "gender": self.gender_head(feat),
            "season": self.season_head(feat),
        }

class EmbeddingDataset(Dataset):
    def __init__(self, embeddings: np.ndarray, color_ids, style_ids, pattern_ids, gender_ids, season_ids):
        self.x = torch.tensor(embeddings, dtype=torch.float32)
        self.color = torch.tensor(color_ids, dtype=torch.long)
        self.style = torch.tensor(style_ids, dtype=torch.long)
        self.pattern = torch.tensor(pattern_ids, dtype=torch.long)
        self.gender = torch.tensor(gender_ids, dtype=torch.long)
        self.season = torch.tensor(season_ids, dtype=torch.long)

    def __len__(self):
        return len(self.x)

    def __getitem__(self, idx):
        return {
            "x": self.x[idx],
            "color": self.color[idx],
            "style": self.style[idx],
            "pattern": self.pattern[idx],
            "gender": self.gender[idx],
            "season": self.season[idx],
        }

def train_and_evaluate():
    print("=" * 75)
    print("   Starting Multi-Attribute Fashion Classifier Training Pipeline")
    print("=" * 75)

    # 1. Load Data
    emb_path = DATA_DIR / "clip_embeddings.npy"
    csv_path = DATA_DIR / "deepfashion_catalog.csv"

    print(f"[*] Loading visual embeddings from {emb_path}...")
    embeddings = np.load(emb_path)
    df = pd.read_csv(csv_path)

    print(f"    Loaded {len(embeddings)} embeddings of dimension {embeddings.shape[1]}")
    print(f"    Loaded {len(df)} catalog records.")

    # 2. Build Category Vocabularies
    # Standardize Top Colors (Keep top 16, map rare to Other)
    top_colors = df["color"].value_counts().head(16).index.tolist()
    df["clean_color"] = df["color"].apply(lambda c: c if c in top_colors else "Other")
    colors = sorted(df["clean_color"].unique().tolist())
    styles = sorted(df["style"].fillna("Casual").unique().tolist())
    patterns = sorted(df["pattern"].fillna("Solid").unique().tolist())
    genders = sorted(df["gender"].fillna("Unisex").unique().tolist())
    seasons = sorted(df["season"].fillna("Summer").unique().tolist())

    color2id = {c: i for i, c in enumerate(colors)}
    style2id = {s: i for i, s in enumerate(styles)}
    pattern2id = {p: i for i, p in enumerate(patterns)}
    gender2id = {g: i for i, g in enumerate(genders)}
    season2id = {se: i for i, se in enumerate(seasons)}

    df["color_id"] = df["clean_color"].map(color2id)
    df["style_id"] = df["style"].fillna("Casual").map(style2id)
    df["pattern_id"] = df["pattern"].fillna("Solid").map(pattern2id)
    df["gender_id"] = df["gender"].fillna("Unisex").map(gender2id)
    df["season_id"] = df["season"].fillna("Summer").map(season2id)

    mappings = {
        "color": {"id2label": {i: c for i, c in enumerate(colors)}, "label2id": color2id},
        "style": {"id2label": {i: s for i, s in enumerate(styles)}, "label2id": style2id},
        "pattern": {"id2label": {i: p for i, p in enumerate(patterns)}, "label2id": pattern2id},
        "gender": {"id2label": {i: g for i, g in enumerate(genders)}, "label2id": gender2id},
        "season": {"id2label": {i: se for i, se in enumerate(seasons)}, "label2id": season2id},
    }

    with open(MODELS_DIR / "attribute_mappings.json", "w", encoding="utf-8") as f:
        json.dump(mappings, f, indent=2)
    print(f"[*] Saved attribute mappings to {MODELS_DIR / 'attribute_mappings.json'}")

    # 3. Group-Aware Train / Val / Test Split (Prevent data leakage)
    groups = df["group_key"].fillna("ungrouped").values
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
    train_idx, temp_idx = next(gss1.split(df, groups=groups))

    df_temp = df.iloc[temp_idx]
    temp_groups = df_temp["group_key"].fillna("ungrouped").values
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=SEED)
    val_rel_idx, test_rel_idx = next(gss2.split(df_temp, groups=temp_groups))

    val_idx = temp_idx[val_rel_idx]
    test_idx = temp_idx[test_rel_idx]

    print(f"\n[*] Dataset Splits (Group-aware by product family):")
    print(f"    Train:      {len(train_idx)} samples ({len(train_idx)/len(df)*100:.1f}%)")
    print(f"    Validation: {len(val_idx)} samples ({len(val_idx)/len(df)*100:.1f}%)")
    print(f"    Test:       {len(test_idx)} samples ({len(test_idx)/len(df)*100:.1f}%)")

    train_ds = EmbeddingDataset(
        embeddings[train_idx],
        df.iloc[train_idx]["color_id"].values,
        df.iloc[train_idx]["style_id"].values,
        df.iloc[train_idx]["pattern_id"].values,
        df.iloc[train_idx]["gender_id"].values,
        df.iloc[train_idx]["season_id"].values,
    )
    val_ds = EmbeddingDataset(
        embeddings[val_idx],
        df.iloc[val_idx]["color_id"].values,
        df.iloc[val_idx]["style_id"].values,
        df.iloc[val_idx]["pattern_id"].values,
        df.iloc[val_idx]["gender_id"].values,
        df.iloc[val_idx]["season_id"].values,
    )
    test_ds = EmbeddingDataset(
        embeddings[test_idx],
        df.iloc[test_idx]["color_id"].values,
        df.iloc[test_idx]["style_id"].values,
        df.iloc[test_idx]["pattern_id"].values,
        df.iloc[test_idx]["gender_id"].values,
        df.iloc[test_idx]["season_id"].values,
    )

    train_loader = DataLoader(train_ds, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False)

    # 4. Initialize Model & Training Setup
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = MultiAttributeClassifier(
        emb_dim=embeddings.shape[1],
        num_colors=len(colors),
        num_styles=len(styles),
        num_patterns=len(patterns),
        num_genders=len(genders),
        num_seasons=len(seasons),
    ).to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=15)

    print(f"\n[*] Training Multi-Attribute Model on device: {device}...")
    best_val_loss = float("inf")
    best_weights = None

    for epoch in range(1, 16):
        model.train()
        train_loss = 0.0
        for batch in train_loader:
            x = batch["x"].to(device)
            c_target = batch["color"].to(device)
            s_target = batch["style"].to(device)
            p_target = batch["pattern"].to(device)
            g_target = batch["gender"].to(device)
            se_target = batch["season"].to(device)

            optimizer.zero_grad()
            out = model(x)
            loss_c = criterion(out["color"], c_target)
            loss_s = criterion(out["style"], s_target)
            loss_p = criterion(out["pattern"], p_target)
            loss_g = criterion(out["gender"], g_target)
            loss_se = criterion(out["season"], se_target)

            loss = loss_c + 1.2 * loss_s + 1.2 * loss_p + loss_g + loss_se
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * len(x)

        scheduler.step()
        train_loss /= len(train_ds)

        # Validation
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for batch in val_loader:
                x = batch["x"].to(device)
                c_target = batch["color"].to(device)
                s_target = batch["style"].to(device)
                p_target = batch["pattern"].to(device)
                g_target = batch["gender"].to(device)
                se_target = batch["season"].to(device)

                out = model(x)
                loss_c = criterion(out["color"], c_target)
                loss_s = criterion(out["style"], s_target)
                loss_p = criterion(out["pattern"], p_target)
                loss_g = criterion(out["gender"], g_target)
                loss_se = criterion(out["season"], se_target)
                v_loss = loss_c + 1.2 * loss_s + 1.2 * loss_p + loss_g + loss_se
                val_loss += v_loss.item() * len(x)

        val_loss /= len(val_ds)
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_weights = model.state_dict()
            print(f"    Epoch {epoch:2d}/15: Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} (Best)")
        else:
            print(f"    Epoch {epoch:2d}/15: Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

    # Load Best Weights
    model.load_state_dict(best_weights)
    torch.save(best_weights, MODELS_DIR / "attribute_classifier.pt")
    print(f"\n[*] Saved trained model checkpoint to {MODELS_DIR / 'attribute_classifier.pt'}")

    # 5. Scientific Evaluation on Held-Out Test Set
    print("\n" + "=" * 75)
    print("   SCIENTIFIC EVALUATION ON HELD-OUT TEST SET (10% Unseen Data)")
    print("=" * 75)

    model.eval()
    all_preds = {"color": [], "style": [], "pattern": [], "gender": [], "season": []}
    all_targets = {"color": [], "style": [], "pattern": [], "gender": [], "season": []}

    with torch.no_grad():
        for batch in test_loader:
            x = batch["x"].to(device)
            out = model(x)
            for attr in ["color", "style", "pattern", "gender", "season"]:
                preds = torch.argmax(out[attr], dim=-1).cpu().numpy()
                targets = batch[attr].numpy()
                all_preds[attr].extend(preds)
                all_targets[attr].extend(targets)

    results = {
        "dataset_name": "DeepFashion (44,441 catalog images)",
        "train_samples": len(train_ds),
        "val_samples": len(val_ds),
        "test_samples": len(test_ds),
        "attributes": {},
    }

    for attr, labels in [
        ("color", colors),
        ("style", styles),
        ("pattern", patterns),
        ("gender", genders),
        ("season", seasons),
    ]:
        y_true = np.array(all_targets[attr])
        y_pred = np.array(all_preds[attr])

        acc = accuracy_score(y_true, y_pred)
        prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
        macro_prec, macro_rec, macro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)

        results["attributes"][attr] = {
            "num_classes": len(labels),
            "classes": labels,
            "accuracy": round(float(acc) * 100, 2),
            "weighted_precision": round(float(prec) * 100, 2),
            "weighted_recall": round(float(rec) * 100, 2),
            "weighted_f1": round(float(f1) * 100, 2),
            "macro_f1": round(float(macro_f1) * 100, 2),
        }

        print(f"\n--- [{attr.upper()}] Evaluation ({len(labels)} Classes) ---")
        print(f"    Accuracy:           {acc * 100:.2f}%")
        print(f"    Weighted Precision: {prec * 100:.2f}%")
        print(f"    Weighted Recall:    {rec * 100:.2f}%")
        print(f"    Weighted F1 Score:  {f1 * 100:.2f}%")
        print(f"    Macro F1 Score:     {macro_f1 * 100:.2f}%")

    with open(DATA_DIR / "attribute_evaluation_report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[*] Full evaluation report saved to {DATA_DIR / 'attribute_evaluation_report.json'}")

if __name__ == "__main__":
    train_and_evaluate()
