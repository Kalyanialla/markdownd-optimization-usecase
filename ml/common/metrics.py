"""
Evaluation metrics module for retail demand and markdown optimization models.
Computes MAE, RMSE, WAPE (with zero-division handling), Precision, Recall, F1, PR-AUC,
and subgroup performance by stockout status, category, and store.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
    precision_score,
    recall_score,
    f1_score,
    precision_recall_curve,
    auc,
    confusion_matrix
)

def compute_regression_metrics(y_true, y_pred, prefix=""):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    
    # Enforce non-negative prediction constraint for units sold
    y_pred_clipped = np.clip(y_pred, 0, None)
    
    mae = float(mean_absolute_error(y_true, y_pred_clipped))
    rmse = float(root_mean_squared_error(y_true, y_pred_clipped))
    
    sum_true = float(np.sum(y_true))
    if sum_true > 0:
        wape = float(np.sum(np.abs(y_true - y_pred_clipped)) / sum_true * 100)
    else:
        wape = 0.0 if np.sum(np.abs(y_true - y_pred_clipped)) == 0 else 100.0
        
    p = f"{prefix}_" if prefix else ""
    return {
        f"{p}mae": round(mae, 4),
        f"{p}rmse": round(rmse, 4),
        f"{p}wape_pct": round(wape, 2),
        f"{p}sample_size": len(y_true),
        f"{p}negative_predictions_clipped": int(np.sum(y_pred < 0))
    }

def compute_subgroup_metrics(df, y_true_col, y_pred_col, group_col):
    results = {}
    for grp_val, grp_df in df.groupby(group_col):
        metrics = compute_regression_metrics(grp_df[y_true_col], grp_df[y_pred_col])
        results[str(grp_val)] = metrics
    return results

def compute_classification_metrics(y_true, y_pred_proba, threshold=0.5, prefix=""):
    y_true = np.asarray(y_true, dtype=int)
    y_pred_proba = np.asarray(y_pred_proba, dtype=float)
    y_pred_binary = (y_pred_proba >= threshold).astype(int)
    
    prec = float(precision_score(y_true, y_pred_binary, zero_division=0))
    rec = float(recall_score(y_true, y_pred_binary, zero_division=0))
    f1 = float(f1_score(y_true, y_pred_binary, zero_division=0))
    
    precisions, recalls, _ = precision_recall_curve(y_true, y_pred_proba)
    pr_auc = float(auc(recalls, precisions))
    
    cm = confusion_matrix(y_true, y_pred_binary).tolist()
    
    p = f"{prefix}_" if prefix else ""
    return {
        f"{p}precision": round(prec, 4),
        f"{p}recall": round(rec, 4),
        f"{p}f1": round(f1, 4),
        f"{p}pr_auc": round(pr_auc, 4),
        f"{p}confusion_matrix": cm,
        f"{p}threshold": threshold,
        f"{p}sample_size": len(y_true),
        f"{p}positive_rate": round(float(np.mean(y_true) * 100), 2)
    }
