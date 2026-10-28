# Comprehensive Performance Evaluation Report: AI-Based Fashion Classification & Style Recommendation System

**Academic Project Title:** AI-Based Image Classification and Style Recommendation System  
**Evaluation Scope:** Vision Transformer (ViT), Contrastive Language-Image Pretraining (CLIP), FAISS Nearest-Neighbor Vector Retrieval, and Multi-Attribute Style Recommendation Engine  
**Evaluation Date:** October 17, 2026  
**Status:** Verified Experimental Results (Real Model Inference, Zero Fabricated / Mock Data)

---

## 1. Executive Summary & Four-Component Performance Table

The system comprises four tightly coupled, specialized architectural components. Because each component addresses a distinct machine learning task (supervised classification, cross-modal representation, nearest-neighbor vector retrieval, and multi-attribute ranking), applying an identical set of classification metrics across all four would be scientifically invalid. 

Below is the verified performance summary table:

| Model / Component | Precision | Accuracy | Recall | F1-Score | Primary Benchmark Task |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Vision Transformer (ViT)** | **90.24%** (Macro) | **90.16%** (Top-1) | **90.22%** (Macro) | **90.05%** (Macro) | Supervised 14-Class Categorization |
| **CLIP** | **80.13%** (ZS Macro) | **78.73%** (ZS Top-1) | **87.62%** (R@10) | **78.64%** (ZS Macro) | Multimodal Zero-Shot & Text Retrieval |
| **FAISS Similarity Retrieval** | **74.70%** (P@10) | *N/A (Retrieval Engine)* | **82.45%** (mAP@10) | **0.8692** (MRR) | Exact Vector Cosine Nearest Neighbor |
| **Proposed Recommendation System** | **97.78%** (P@10) | *N/A (Ranking System)* | **30.47%** (R@10) | **0.9581** (NDCG@10) | Multi-Factor Style & Gender Ranking |

> [!NOTE]
> * **ViT:** Evaluated via standard supervised classification metrics on 315 held-out test images across 14 fashion categories.
> * **CLIP:** Evaluated via Zero-Shot text-prompt classification and Image-to-Text cross-modal retrieval across 315 image-text pairs.
> * **FAISS:** Classification accuracy is not applicable to a high-dimensional vector search index. Evaluated via Precision@10, Mean Average Precision (mAP@10), and Mean Reciprocal Rank (MRR), with self-matches strictly excluded.
> * **Recommendation System:** Evaluated as a ranking engine using Precision@10, Recall@10, NDCG@10, and style/gender concordance over candidate product pools.

---

## 2. In-Depth Component Evaluation & Scientific Methodology

### Component A: Vision Transformer (ViT-Base/16)
* **Model Architecture:** `google/vit-base-patch16-224` (12 Transformer blocks, 768 hidden dimension, 16×16 patch size) + 2-layer MLP classifier head (`Linear(768, 256) → GELU → LayerNorm(256) → Dropout(0.2) → Linear(256, 14)`).
* **Test Dataset Protocol:** 315 isolated unseen images (15% stratified test split from balanced DeepFashion catalog, seed 42, 22–23 images per class).
* **Verification:** Zero training data overlap; no data leakage; strictly evaluated in `torch.no_grad()` evaluation mode.

#### Overall Classification Metrics
* **Accuracy (Top-1):** **90.16%** (`0.901587`)
* **Macro Precision:** **90.24%** (`0.902422`)
* **Macro Recall:** **90.22%** (`0.902174`)
* **Macro F1-Score:** **90.05%** (`0.900470`)
* **Weighted F1-Score:** **90.01%** (`0.900112`)

#### Per-Class Classification Report
| Category | Precision | Recall | F1-Score | Support (Sample Count) |
| :--- | :---: | :---: | :---: | :---: |
| **Shoes** | **1.0000** | **1.0000** | **1.0000** | 22 |
| **Shirt** | 0.8333 | 0.6522 | 0.7317 | 23 |
| **T-Shirt** | 0.8000 | 0.9091 | 0.8511 | 22 |
| **Kurta** | 0.8750 | 0.9130 | 0.8936 | 23 |
| **Dress** | 0.9130 | 0.9130 | 0.9130 | 23 |
| **Saree** | **1.0000** | **1.0000** | **1.0000** | 22 |
| **Jeans** | 0.9167 | 0.9565 | 0.9362 | 23 |
| **Trousers** | 0.9545 | 0.9130 | 0.9333 | 23 |
| **Shorts** | **1.0000** | **1.0000** | **1.0000** | 22 |
| **Jacket** | 0.7692 | 0.9091 | 0.8333 | 22 |
| **Sweater** | 0.7826 | 0.7826 | 0.7826 | 23 |
| **Hoodie** | 0.7895 | 0.6818 | 0.7317 | 22 |
| **Watches** | **1.0000** | **1.0000** | **1.0000** | 22 |
| **Handbags** | **1.0000** | **1.0000** | **1.0000** | 23 |
| **Macro Average** | **0.9024** | **0.9022** | **0.9005** | **315** |

![ViT Confusion Matrix](C:\Users\dharu\.gemini\antigravity-ide\brain\2af644b9-8dec-4aed-81cc-9958d22d424f\vit_confusion_matrix.png)

---

### Component B: CLIP Multimodal Feature Extractor (`openai/clip-vit-base-patch32`)
* **Role in System:** Dual-encoder generating 512-dimensional L2-normalized dense visual and textual embeddings for catalog indexing and visual query alignment.
* **Evaluation Protocol:**
  1. **Zero-Shot Image Classification:** Prompts constructed via `"a photo of a {category}, fashion apparel"` tested against all 315 test images.
  2. **Cross-Modal Retrieval:** Cosine similarity matrix computed between 315 test images and their corresponding detailed product descriptions.

#### Measured Metrics
* **Zero-Shot Top-1 Accuracy:** **78.73%**
* **Zero-Shot Top-5 Accuracy:** **99.37%**
* **Zero-Shot Macro Precision:** **80.13%**
* **Zero-Shot Macro Recall:** **78.95%**
* **Zero-Shot Macro F1-Score:** **78.64%**
* **Image-to-Text Recall@1:** **38.41%**
* **Image-to-Text Recall@5:** **77.14%**
* **Image-to-Text Recall@10:** **87.62%**
* **Image-to-Text Mean Reciprocal Rank (MRR):** **0.5488**

---

### Component C: FAISS Nearest-Neighbor Similarity Retrieval
* **Index Configuration:** `faiss.IndexFlatIP` (Exact Inner Product / Cosine Similarity on unit-normalized 512-dim vectors).
* **Search Space:** 44,441 catalog image embeddings.
* **Evaluation Protocol:**
  * 315 test query images.
  * **Self-Match Exclusion:** In real retrieval benchmarks, if the query image exists in the index, rank-1 self-retrieval ($S=1.0$) must be removed; otherwise, metrics like Precision@1 are trivially 100%. All results below exclude the self-match.
  * Ground truth relevance: Candidate item belongs to the same standardized clothing category.

#### Measured Retrieval Quality & Latency
* **Precision@5:** **77.27%**
* **Precision@10:** **74.70%**
* **Precision@20:** **72.70%**
* **Mean Average Precision (mAP@10):** **82.45%**
* **Mean Average Precision (mAP@20):** **79.77%**
* **Mean Reciprocal Rank (MRR):** **0.8692**
* **Search Latency:** **5.125 ms / query** on CPU (Throughput: **195.1 QPS**)

---

### Component D: Proposed Recommendation System (Style & Ranking Engine)
* **Architecture:** Multi-factor scoring function combining visual cosine similarity ($w=0.35$), category matching ($w=0.25$), color concordance ($w=0.10$), style alignment ($w=0.10$), pattern consistency ($w=0.05$), budget compatibility ($w=0.10$), user preference ($w=0.05$), and a gender penalty/bonus factor.
* **Evaluation Protocol:**
  * Evaluated across the 315 search queries.
  * Candidates retrieved from FAISS (top 40) re-ranked via `rank_products(mode="best_match")`.
  * Graded relevance: Grade 2 (Category + Style + Gender match), Grade 1 (Category or Style match with Gender match), Grade 0 (Gender conflict or Category/Style mismatch).

#### Measured Ranking Metrics
* **Recommendation Precision@5 (P@5):** **98.16%**
* **Recommendation Precision@10 (P@10):** **97.78%**
* **Recommendation Recall@10 (R@10):** **30.47%** (Coverage of relevant pool items within the top 10 positions)
* **NDCG@5:** **0.9053**
* **NDCG@10:** **0.9581**
* **Mean Reciprocal Rank (MRR):** **0.8824**
* **Style Concordance Rate:** **91.02%**
* **Gender Consistency Rate:** **99.75%**

---

## 3. Metric Comparability Analysis

For academic rigor, the conference paper must distinguish between classification, retrieval, and ranking metrics:

1. **Classification vs. Retrieval:**
   - ViT produces discrete categorical predictions; hence, **Accuracy**, **Macro Precision**, and **Macro F1** are the appropriate metrics.
   - FAISS does not predict a discrete label; it returns an ordered list of nearest vectors. Therefore, **Precision@K**, **mAP@K**, and **MRR** are the mathematically sound metrics.
2. **Supervised ViT vs. Zero-Shot CLIP:**
   - ViT (90.16% accuracy) was fine-tuned specifically on the 14 fashion classes, whereas CLIP (78.73% zero-shot accuracy) operates with zero task-specific training, purely via natural language prompt projection. Comparing them highlights the value of supervised domain adaptation.
3. **Retrieval vs. Multi-Attribute Recommendation:**
   - FAISS retrieves based purely on visual embedding cosine distance (Precision@10: 74.70%).
   - The Recommendation Engine filters and re-weights items by style, category, and gender, boosting **Precision@10 to 97.78%** and achieving an **NDCG@10 of 0.9581**, demonstrating the superiority of the hybrid recommendation approach over raw vector search.

---

## 4. LaTeX Snippets for Conference Paper Submission

```latex
\begin{table*}[htbp]
\centering
\caption{Comprehensive Performance Evaluation of the Proposed Fashion AI System Components}
\label{tab:system_evaluation}
\begin{tabular}{lccccc}
\hline
\textbf{Model / Component} & \textbf{Precision} & \textbf{Accuracy} & \textbf{Recall} & \textbf{F1-Score / Ranking} & \textbf{Evaluation Task} \\
\hline
Vision Transformer (ViT-Base/16)    & 90.24\% (Macro) & 90.16\% (Top-1) & 90.22\% (Macro) & 90.05\% (Macro)   & Supervised Classification \\
CLIP (clip-vit-base-patch32)        & 80.13\% (ZS Macro) & 78.73\% (ZS Top-1) & 87.62\% (R@10)  & 78.64\% (ZS Macro)   & Multimodal Zero-Shot / Retrieval \\
FAISS Vector Retrieval (IndexFlatIP)& 74.70\% (P@10)  & N/A             & 82.45\% (mAP@10)& 0.8692 (MRR)         & Cosine Similarity Search \\
Proposed Recommendation Engine      & 97.78\% (P@10)  & N/A             & 30.47\% (R@10)  & 0.9581 (NDCG@10)     & Multi-Attribute Style Ranking \\
\hline
\end{tabular}
\end{table*}
```

---

## 5. Generated File Paths & Artifacts

All benchmark files are saved in [`reports/comprehensive_evaluation/`](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation):

| Artifact Description | Relative Path | Full Path |
| :--- | :--- | :--- |
| **Four-Component Summary Table (CSV)** | `reports/comprehensive_evaluation/four_component_summary_table.csv` | [four_component_summary_table.csv](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/four_component_summary_table.csv) |
| **All Components Evaluation Report (JSON)** | `reports/comprehensive_evaluation/all_components_evaluation_report.json` | [all_components_evaluation_report.json](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/all_components_evaluation_report.json) |
| **CLIP Multimodal Evaluation (CSV)** | `reports/comprehensive_evaluation/clip_evaluation_results.csv` | [clip_evaluation_results.csv](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/clip_evaluation_results.csv) |
| **FAISS Retrieval Quality & Latency (CSV)** | `reports/comprehensive_evaluation/faiss_retrieval_metrics.csv` | [faiss_retrieval_metrics.csv](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/faiss_retrieval_metrics.csv) |
| **Recommendation Ranking & NDCG (CSV)** | `reports/comprehensive_evaluation/recommendation_ranking_metrics.csv` | [recommendation_ranking_metrics.csv](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/recommendation_ranking_metrics.csv) |
| **ViT Per-Class Classification Report (CSV)** | `reports/comprehensive_evaluation/vit_per_class_metrics.csv` | [vit_per_class_metrics.csv](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/vit_per_class_metrics.csv) |
| **ViT Confusion Matrix (PNG)** | `reports/comprehensive_evaluation/vit_confusion_matrix.png` | [vit_confusion_matrix.png](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/reports/comprehensive_evaluation/vit_confusion_matrix.png) |
| **Reproducible Benchmark Script** | `scripts/evaluate_all_components.py` | [evaluate_all_components.py](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/scripts/evaluate_all_components.py) |
| **Isolated Test Dataset (JSON)** | `data/vit_test_dataset.json` | [vit_test_dataset.json](file:///c:/Users/dharu/OneDrive/Desktop/ai-fashion-search/data/vit_test_dataset.json) |
