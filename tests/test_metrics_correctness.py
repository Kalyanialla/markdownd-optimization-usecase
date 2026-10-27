"""
Tests for WAPE metric correctness, zero-denominator handling, and
Model 1 / Model 2 metric reproducibility from saved artifacts.
UC-RT-03 Markdown Optimization
"""

import os
import numpy as np
import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M1_PREDS  = os.path.join(REPO_ROOT, "ml/artifacts/model1/test_predictions_demand.csv")
M3_PREDS  = os.path.join(REPO_ROOT, "ml/artifacts/model3/test_predictions_stockout.csv")


def _wape(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.clip(np.asarray(y_pred, dtype=float), 0, None)
    s = float(np.sum(y_true))
    return float(np.sum(np.abs(y_true - y_pred)) / s * 100) if s > 0 else float("nan")


def test_wape_zero_denominator_returns_nan_not_error():
    """WAPE must return nan when sum(actual)==0 and predictions are non-zero."""
    result = _wape([0, 0, 0], [1, 2, 3])
    assert np.isnan(result), f"Expected nan, got {result}"


def test_wape_perfect_prediction_is_zero():
    result = _wape([1, 2, 3], [1, 2, 3])
    assert abs(result) < 1e-9


def test_model1_wape_matches_saved_predictions():
    """Recompute M1 WAPE and RMSE from saved predictions and check it matches the reported values."""
    df = pd.read_csv(M1_PREDS)
    wape = _wape(df["target_units_sold"], df["pred_units_sold"])
    assert abs(wape - 107.42) < 0.1, f"Expected ~107.42%, got {wape:.4f}%"
    
    # Authoritative Candidate RMSE: 0.7702 (exact: 0.770208)
    rmse = float(np.sqrt(np.mean((df["target_units_sold"] - df["pred_units_sold"])**2)))
    assert round(rmse, 4) == 0.7702, f"Candidate RMSE must be exactly 0.7702, got {rmse:.4f}"
    
    # Candidate MAE: 0.4228
    mae = float(np.mean(np.abs(df["target_units_sold"] - df["pred_units_sold"])))
    assert round(mae, 4) == 0.4228, f"Candidate MAE must be exactly 0.4228, got {mae:.4f}"


def test_model1_baseline_metrics_on_test_csv():
    """Recompute M1 Baseline 7-day MA metrics on test.csv: RMSE=0.8422, MAE=0.4553, WAPE=115.67%."""
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    df = pd.read_csv(test_csv)
    y_true = df["target_units_sold"].values
    y_pred = np.clip(df["sales_rolling_mean_7d"].values, 0, None)
    
    rmse = float(np.sqrt(np.mean((y_true - y_pred)**2)))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    wape = float(np.sum(np.abs(y_true - y_pred)) / np.sum(y_true) * 100)
    
    assert round(rmse, 4) == 0.8422, f"Baseline RMSE must be exactly 0.8422, got {rmse:.4f}"
    assert round(mae, 4) == 0.4553, f"Baseline MAE must be exactly 0.4553, got {mae:.4f}"
    assert round(wape, 2) == 115.67, f"Baseline WAPE must be exactly 115.67%, got {wape:.2f}%"


def test_model1_no_negative_predictions():
    df = pd.read_csv(M1_PREDS)
    assert (df["pred_units_sold"] >= 0).all(), "Model 1 produced negative predictions"


def test_model1_bias_is_small_positive():
    """Model 1 should have slight overforecast bias — mean bias (pred-actual) < 0.1."""
    df = pd.read_csv(M1_PREDS)
    bias = float((df["pred_units_sold"] - df["target_units_sold"]).mean())
    assert bias > 0, "Expected slight positive bias (overforecast)"
    assert bias < 0.1, f"Bias {bias:.4f} is too large — investigate"


def test_model3_no_probability_outside_unit_interval():
    df = pd.read_csv(M3_PREDS)
    assert df["candidate_prob"].between(0.0, 1.0).all(), "M3 probabilities outside [0,1]"


def test_model3_label_is_binary():
    df = pd.read_csv(M3_PREDS)
    assert set(df["stockout_within_next_7_days"].unique()).issubset({0, 1}), \
        "Non-binary labels in M3 test predictions"


def test_model3_test_dates_within_frozen_test_period():
    """All test predictions must fall within 2025-04-01..2025-06-30."""
    df = pd.read_csv(M3_PREDS)
    df["date"] = pd.to_datetime(df["date"])
    assert df["date"].min() >= pd.Timestamp("2025-04-01")
    assert df["date"].max() <= pd.Timestamp("2025-06-30")
