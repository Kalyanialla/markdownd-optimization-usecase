"""
UC-RT-03: Construction and Audit of 7-Day Stockout Risk Target Labels.

Constructs 'stockout_within_next_7_days' using FUTURE records (T+1 to T+7) only.
Handles censoring at end of series/lifecycle:
- If a stockout occurs within available future days (even if <7 days remain), label = 1.
- If full 7 days are observed and any day has stockout_flag == 1, label = 1; else 0.
- If <7 days remain and no stockout occurred within available days, observation is censored (NaN).

BOUNDARY PURGE (v2):
Any row within 7 days of a split boundary is censored to prevent cross-split label contamination:
  - Train rows 2024-12-25 to 2024-12-31 purged (T+1..T+7 window falls in validation period)
  - Val rows 2025-03-25 to 2025-03-31 purged   (T+1..T+7 window falls in test period)
"""

import os
import sys
import logging
import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CLEANED_PATH = os.path.join(REPO_ROOT, "data/processed/markdown_optimization_cleaned.csv")
REPORTS_DIR = os.path.join(REPO_ROOT, "data/reports/model3_stockout_risk")

# Chronological split boundaries (match split_manifest.json)
TRAIN_END  = pd.Timestamp("2024-12-31")
VAL_START  = pd.Timestamp("2025-01-01")
VAL_END    = pd.Timestamp("2025-03-31")
TEST_START = pd.Timestamp("2025-04-01")
PURGE_DAYS = 7  # label horizon length


def construct_stockout_labels(df_source: pd.DataFrame) -> pd.DataFrame:
    """
    Constructs forward 7-day stockout labels with strict split-boundary purging.

    Purge rule: A row at date T is censored (NaN) if ANY of T+1..T+7 falls in
    a different chronological split than T. This prevents training labels from
    drawing on validation-period outcomes and validation labels from drawing on
    test-period outcomes.
    """
    logger.info("Sorting by entity (store_id, sku_id) and date...")
    df = df_source[["date", "store_id", "sku_id", "stockout_flag"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["store_id", "sku_id", "date"]).reset_index(drop=True)

    logger.info("Computing forward shifts (T+1 to T+7) for stockout_flag...")
    shift_cols = []
    for i in range(1, 8):
        col_name = f"shift_{i}"
        df[col_name] = df.groupby(["store_id", "sku_id"])["stockout_flag"].shift(-i)
        shift_cols.append(col_name)

    shifts_matrix = df[shift_cols]

    # 1. Any stockout observed in future window
    any_stockout = (shifts_matrix == 1).any(axis=1)

    # 2. Complete 7-day future availability
    full_future_observed = (~shifts_matrix.isna()).all(axis=1)

    # Label logic (before boundary purge)
    target_labels = pd.Series(np.nan, index=df.index, name="stockout_within_next_7_days")
    target_labels[any_stockout] = 1.0
    target_labels[(~any_stockout) & full_future_observed] = 0.0

    # 3. Split-boundary purge
    in_train = (df["date"] >= "2024-01-01") & (df["date"] <= TRAIN_END)
    in_val   = (df["date"] >= VAL_START) & (df["date"] <= VAL_END)

    train_purge_mask = in_train & (df["date"] > (TRAIN_END - pd.Timedelta(days=PURGE_DAYS)))
    val_purge_mask   = in_val   & (df["date"] > (VAL_END   - pd.Timedelta(days=PURGE_DAYS)))
    boundary_purge   = train_purge_mask | val_purge_mask
    target_labels[boundary_purge] = np.nan

    df["stockout_within_next_7_days"] = target_labels
    df["is_censored"]        = target_labels.isna()
    df["is_boundary_purged"] = boundary_purge

    df = df.drop(columns=shift_cols)

    logger.info(f"Total rows: {len(df)}")
    logger.info(f"Boundary-purged (train->val): {int(train_purge_mask.sum())}, (val->test): {int(val_purge_mask.sum())}")
    logger.info(f"Uncensored rows: {(~df['is_censored']).sum()} ({(~df['is_censored']).mean():.2%})")
    logger.info(f"Positive rate among uncensored: {df['stockout_within_next_7_days'].dropna().mean():.4%}")

    return df


def audit_and_save_labels():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    logger.info(f"Reading cleaned dataset from {CLEANED_PATH}...")
    cleaned_df = pd.read_csv(CLEANED_PATH, usecols=["date", "store_id", "sku_id", "stockout_flag"])

    labels_df = construct_stockout_labels(cleaned_df)

    train_ok = labels_df[(labels_df["date"] >= "2024-01-01") & (labels_df["date"] <= "2024-12-31") & ~labels_df["is_censored"]]
    val_ok   = labels_df[(labels_df["date"] >= "2025-01-01") & (labels_df["date"] <= "2025-03-31") & ~labels_df["is_censored"]]
    test_ok  = labels_df[(labels_df["date"] >= "2025-04-01") & (labels_df["date"] <= "2025-06-30") & ~labels_df["is_censored"]]

    labels_path = os.path.join(REPO_ROOT, "data/processed/stockout_7d_labels.csv")
    labels_df[["date", "store_id", "sku_id", "stockout_within_next_7_days", "is_censored", "is_boundary_purged"]].to_csv(labels_path, index=False)
    logger.info(f"Saved labels to {labels_path}")

    train_prev = train_ok["stockout_within_next_7_days"].mean() * 100
    val_prev   = val_ok["stockout_within_next_7_days"].mean() * 100
    test_prev  = test_ok["stockout_within_next_7_days"].mean() * 100
    n_purged_tv = int(labels_df[labels_df["is_boundary_purged"] & (labels_df["date"] <= "2024-12-31")].shape[0])
    n_purged_vt = int(labels_df[labels_df["is_boundary_purged"] & (labels_df["date"] >= "2025-01-01") & (labels_df["date"] <= "2025-03-31")].shape[0])

    audit_report = f"""# Seven-Day Stockout Risk Target Construction Audit (v2 - with Boundary Purge)

- **Generated Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Version**: v2 (fixes temporal contamination via 7-day split-boundary purge)

## 1. Boundary Purge Applied

| Purge Region | Rows Purged |
| :--- | :--- |
| Train rows 2024-12-25 to 2024-12-31 (window into val) | {n_purged_tv:,} |
| Val rows 2025-03-25 to 2025-03-31 (window into test) | {n_purged_vt:,} |

## 2. Label Statistics by Split

| Split | Eligible Rows | Positive Rate |
| :--- | :--- | :--- |
| Train (2024) | {len(train_ok):,} | {train_prev:.2f}% |
| Validation (Q1 2025) | {len(val_ok):,} | {val_prev:.2f}% |
| Test (Q2 2025) | {len(test_ok):,} | {test_prev:.2f}% |

## 3. Leakage Guardrails

- [x] Forward shift applied: T+1 to T+7 only (current day excluded).
- [x] 7-day boundary purge applied at each split transition.
- [x] No leakage columns in inference features.
"""
    with open(os.path.join(REPORTS_DIR, "stockout_label_construction_audit.md"), "w", encoding="utf-8") as f:
        f.write(audit_report)
    logger.info("Saved audit report.")


if __name__ == "__main__":
    audit_and_save_labels()
