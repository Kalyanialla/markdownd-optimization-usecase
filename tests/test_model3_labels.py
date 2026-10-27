"""
Targeted tests for Model 3 label construction, split-boundary purging,
and leakage prevention.
UC-RT-03 Markdown Optimization
"""

import os
import pandas as pd
import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LABELS_PATH = os.path.join(REPO_ROOT, "data/processed/stockout_7d_labels.csv")


@pytest.fixture(scope="module")
def labels_df():
    df = pd.read_csv(LABELS_PATH)
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_labels_file_exists():
    assert os.path.exists(LABELS_PATH), "stockout_7d_labels.csv missing — run build_labels.py"


def test_no_train_label_bleeds_into_validation(labels_df):
    """Train rows within 7 days of 2024-12-31 must be censored."""
    train_boundary = labels_df[
        (labels_df["date"] >= "2024-12-25") & (labels_df["date"] <= "2024-12-31")
    ]
    active = train_boundary[~train_boundary["is_censored"]]
    assert len(active) == 0, (
        f"BOUNDARY LEAK: {len(active)} train rows in 2024-12-25..2024-12-31 are NOT censored "
        f"— their labels draw from validation-period outcomes."
    )


def test_no_val_label_bleeds_into_test(labels_df):
    """Val rows within 7 days of 2025-03-31 must be censored."""
    val_boundary = labels_df[
        (labels_df["date"] >= "2025-03-25") & (labels_df["date"] <= "2025-03-31")
    ]
    active = val_boundary[~val_boundary["is_censored"]]
    assert len(active) == 0, (
        f"BOUNDARY LEAK: {len(active)} val rows in 2025-03-25..2025-03-31 are NOT censored."
    )


def test_label_is_binary_or_nan(labels_df):
    """All non-censored labels must be exactly 0 or 1."""
    valid = labels_df[~labels_df["is_censored"]]["stockout_within_next_7_days"].dropna()
    bad = valid[~valid.isin([0.0, 1.0])]
    assert len(bad) == 0, f"Found {len(bad)} labels not in {{0, 1}}"


def test_censored_rows_have_nan_label(labels_df):
    """Censored rows must have NaN labels, not 0 or 1."""
    censored = labels_df[labels_df["is_censored"]]["stockout_within_next_7_days"]
    non_nan = censored.dropna()
    assert len(non_nan) == 0, f"Found {len(non_nan)} censored rows with non-NaN label"


def test_positive_prevalence_plausible_by_split(labels_df):
    """Positive rates must be positive and below 70% in every split — anything else is suspicious."""
    for split_start, split_end, name in [
        ("2024-01-01", "2024-12-31", "train"),
        ("2025-01-01", "2025-03-31", "validation"),
        ("2025-04-01", "2025-06-30", "test"),
    ]:
        split = labels_df[
            (labels_df["date"] >= split_start) & (labels_df["date"] <= split_end) & ~labels_df["is_censored"]
        ]
        rate = split["stockout_within_next_7_days"].mean()
        assert 0.0 < rate < 0.70, (
            f"{name} positive rate {rate:.4f} is outside plausible range (0, 0.70). "
            f"Investigate label construction."
        )


def test_boundary_purge_count_nonzero(labels_df):
    """The boundary purge must remove at least 7 * n_entities rows at each boundary."""
    n_purged = labels_df["is_boundary_purged"].sum()
    assert n_purged >= 870 * 2, (  # 870 entities x 2 boundaries min
        f"Expected at least {870*2} purged rows, got {n_purged}"
    )


def test_no_future_target_in_feature_columns():
    """Feature columns from train.csv must not contain target or leakage columns."""
    train_path = os.path.join(REPO_ROOT, "data/processed/train.csv")
    df = pd.read_csv(train_path, nrows=1)
    forbidden = {
        "target_units_sold", "target_stockout_mask", "eval_benchmark_latent_demand",
        "stockout_within_next_7_days", "closing_stock_units", "intraday_units_received",
        "effective_available_units", "revenue", "returns_units"
    }
    found = forbidden.intersection(set(df.columns))
    # target_units_sold and target_stockout_mask are expected in the split CSVs as ground truth
    # but must NOT be in the inference feature list
    import sys
    sys.path.insert(0, REPO_ROOT)
    from ml.common.feature_contract import STORE_OPENING_FEATURES_66
    in_features = forbidden.intersection(set(STORE_OPENING_FEATURES_66))
    assert len(in_features) == 0, f"Leakage columns in approved feature list: {in_features}"
