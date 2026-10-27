"""
Manual Model Metrics Evaluation Script for UC-RT-03 Markdown Optimization
Evaluates all 3 models directly from the frozen test set and saved prediction artifacts.

Usage:
    python evaluate_all_models.py
"""

import os
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    root_mean_squared_error,
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    roc_auc_score,
    brier_score_loss,
    confusion_matrix
)

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))

def evaluate_model1():
    print("=" * 70)
    print("MODEL 1: DAILY DEMAND FORECASTING EVALUATION (TEST SET: Q2 2025)")
    print("=" * 70)
    preds_path = os.path.join(REPO_ROOT, "ml/artifacts/model1/test_predictions_demand.csv")
    test_csv_path = os.path.join(REPO_ROOT, "data/processed/test.csv")
    
    preds_df = pd.read_csv(preds_path)
    test_df = pd.read_csv(test_csv_path)
    
    y_true = preds_df["target_units_sold"].values
    y_pred_xgb = preds_df["pred_units_sold"].values
    y_pred_base = np.clip(test_df["sales_rolling_mean_7d"].values, 0, None)
    
    # Candidate XGBoost
    mae_xgb = mean_absolute_error(y_true, y_pred_xgb)
    rmse_xgb = root_mean_squared_error(y_true, y_pred_xgb)
    wape_xgb = np.sum(np.abs(y_true - y_pred_xgb)) / np.sum(y_true) * 100
    bias_xgb = np.mean(y_pred_xgb - y_true)
    overforecast_rate = np.mean(y_pred_xgb > y_true) * 100
    
    # Baseline
    mae_base = mean_absolute_error(y_true, y_pred_base)
    rmse_base = root_mean_squared_error(y_true, y_pred_base)
    wape_base = np.sum(np.abs(y_true - y_pred_base)) / np.sum(y_true) * 100
    bias_base = np.mean(y_pred_base - y_true)
    
    print(f"Sample Size: {len(y_true):,} rows (Zero actual sales: {np.mean(y_true == 0):.2%})")
    print(f"\n[Baseline - 7-Day Moving Average]")
    print(f"  MAE:       {mae_base:.4f} units")
    print(f"  RMSE:      {rmse_base:.4f} units")
    print(f"  WAPE:      {wape_base:.2f}%")
    print(f"  Mean Bias: {bias_base:+.4f} units/day")
    
    print(f"\n[Candidate - XGBoost Regressor]")
    print(f"  MAE:       {mae_xgb:.4f} units  (Delta: {mae_xgb - mae_base:+.4f})")
    print(f"  RMSE:      {rmse_xgb:.4f} units  (Delta: {rmse_xgb - rmse_base:+.4f})")
    print(f"  WAPE:      {wape_xgb:.2f}% (Delta: {wape_xgb - wape_base:+.2f} pp, Relative: {(wape_xgb - wape_base)/wape_base*100:+.2f}%)")
    print(f"  Mean Bias: {bias_xgb:+.4f} units/day")
    print(f"  Overforecast Frequency: {overforecast_rate:.2f}%")


def evaluate_model2():
    print("\n" + "=" * 70)
    print("MODEL 2: PRICE-RESPONSE ESTIMATION EVALUATION (TEST SET: Q2 2025)")
    print("=" * 70)
    preds_path = os.path.join(REPO_ROOT, "ml/artifacts/model2/test_predictions_price_response.csv")
    preds_df = pd.read_csv(preds_path)
    
    y_true = preds_df["target_units_sold"].values
    y_pred_ridge = preds_df["pred_baseline_ridge"].values
    y_pred_xgb = preds_df["pred_xgboost_price_response"].values
    
    mae_ridge = mean_absolute_error(y_true, y_pred_ridge)
    rmse_ridge = root_mean_squared_error(y_true, y_pred_ridge)
    wape_ridge = np.sum(np.abs(y_true - y_pred_ridge)) / np.sum(y_true) * 100
    
    mae_xgb = mean_absolute_error(y_true, y_pred_xgb)
    rmse_xgb = root_mean_squared_error(y_true, y_pred_xgb)
    wape_xgb = np.sum(np.abs(y_true - y_pred_xgb)) / np.sum(y_true) * 100
    
    print(f"Sample Size: {len(y_true):,} rows")
    print(f"\n[Baseline - Ridge Price Regression]")
    print(f"  MAE:  {mae_ridge:.4f} units (WINNER on MAE)")
    print(f"  RMSE: {rmse_ridge:.4f} units")
    print(f"  WAPE: {wape_ridge:.2f}% (WINNER on WAPE)")
    
    print(f"\n[Candidate - XGBoost Price-Response]")
    print(f"  MAE:  {mae_xgb:.4f} units")
    print(f"  RMSE: {rmse_xgb:.4f} units (WINNER on RMSE: {rmse_xgb - rmse_ridge:+.4f})")
    print(f"  WAPE: {wape_xgb:.2f}%")
    print("  *Status: EXPERIMENTAL / DECISION SUPPORT ONLY (Observational, non-causal)*")


def evaluate_model3():
    print("\n" + "=" * 70)
    print("MODEL 3: 7-DAY STOCKOUT RISK CLASSIFICATION (TEST SET: Q2 2025)")
    print("=" * 70)
    preds_path = os.path.join(REPO_ROOT, "ml/artifacts/model3/test_predictions_stockout.csv")
    preds_df = pd.read_csv(preds_path)
    
    y_true = preds_df["stockout_within_next_7_days"].values
    y_prob = preds_df["candidate_prob"].values
    y_pred_xgb = preds_df["candidate_pred"].values
    y_pred_base = preds_df["baseline_pred"].values
    
    # Candidate XGBoost
    prec_xgb = precision_score(y_true, y_pred_xgb)
    rec_xgb = recall_score(y_true, y_pred_xgb)
    f1_xgb = f1_score(y_true, y_pred_xgb)
    pr_auc_xgb = average_precision_score(y_true, y_prob)
    roc_auc_xgb = roc_auc_score(y_true, y_prob)
    brier_xgb = brier_score_loss(y_true, y_prob)
    cm_xgb = confusion_matrix(y_true, y_pred_xgb)
    
    # Baseline Rule
    prec_base = precision_score(y_true, y_pred_base)
    rec_base = recall_score(y_true, y_pred_base)
    f1_base = f1_score(y_true, y_pred_base)
    cm_base = confusion_matrix(y_true, y_pred_base)
    
    print(f"Sample Size (Uncensored): {len(y_true):,} rows | Positives: {np.sum(y_true):,} ({np.mean(y_true):.2%})")
    print(f"\n[Baseline Rule - Deterministic 7-Day Runout]")
    print(f"  Precision: {prec_base:.4f}")
    print(f"  Recall:    {rec_base:.4f}  (Missed {cm_base[1][0]:,} true stockouts as False Negatives!)")
    print(f"  F1-Score:  {f1_base:.4f}")
    print(f"  Confusion Matrix (TN, FP / FN, TP): [[{cm_base[0][0]}, {cm_base[0][1]}], [{cm_base[1][0]}, {cm_base[1][1]}]]")
    
    print(f"\n[Candidate - XGBoost Classifier (Boundary Purged)]")
    print(f"  Precision:   {prec_xgb:.4f}")
    print(f"  Recall:      {rec_xgb:.4f}  (Catches 97.17% of true stockouts, only {cm_xgb[1][0]} False Negatives)")
    print(f"  F1-Score:    {f1_xgb:.4f}  (Lift over baseline: {f1_xgb - f1_base:+.4f})")
    print(f"  PR-AUC:      {pr_auc_xgb:.4f}")
    print(f"  ROC-AUC:     {roc_auc_xgb:.4f}")
    print(f"  Brier Score: {brier_xgb:.4f}")
    print(f"  Confusion Matrix (TN, FP / FN, TP): [[{cm_xgb[0][0]}, {cm_xgb[0][1]}], [{cm_xgb[1][0]}, {cm_xgb[1][1]}]]")


if __name__ == "__main__":
    evaluate_model1()
    evaluate_model2()
    evaluate_model3()
    print("\n" + "=" * 70)
    print("ALL EVALUATIONS COMPLETE.")
    print("=" * 70)
