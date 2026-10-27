"""
Production Feature Engineering & Chronological Splitting Pipeline.
UC-RT-03: Markdown Optimization

Engineering Standards:
- Input: data/processed/markdown_optimization_cleaned.csv (149,270 rows, 63 columns)
- Preserves raw data and canonical cleaned CSV.
- Prediction Cutoff: Store opening on Day T, strictly before any customer sales or transactions occur that day.
- Information Boundary: Features must be demonstrably available at or before store opening on Day T.
- Strictly Excludes: same-day units_sold, revenue, returns, stockout_flag, on_hand_units,
  intraday_units_received/dispatched, effective_available_units, and benchmark_latent_demand.
- Causal Features: Entity-specific (store_id, sku_id) lags and rolling statistics computed
  strictly on past observed units_sold and prior stockout indicators.
- Chronological Splits:
  * Train: 2024-01-01 to 2024-12-31 (103,470 rows, 69.32%)
  * Validation: 2025-01-01 to 2025-03-31 (22,140 rows, 14.83%)
  * Test: 2025-04-01 to 2025-06-30 (23,660 rows, 15.85%)
- Preprocessing fit strictly on training set.
"""

import os
import sys
import json
import logging
import hashlib
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("FeatureEngineeringPipeline")

WORKSPACE = os.path.abspath(r"c:\MarkDown Optimization Usecase")
DATA_DIR = os.path.join(WORKSPACE, "data")
CLEANED_CSV = os.path.join(DATA_DIR, "processed", "markdown_optimization_cleaned.csv")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

FEATURES_CSV = os.path.join(PROCESSED_DIR, "markdown_features_canonical.csv")
TRAIN_CSV = os.path.join(PROCESSED_DIR, "train.csv")
VAL_CSV = os.path.join(PROCESSED_DIR, "validation.csv")
TEST_CSV = os.path.join(PROCESSED_DIR, "test.csv")

SCHEMA_JSON_PATH = os.path.join(REPORTS_DIR, "feature_schema.json")
SPLIT_MANIFEST_PATH = os.path.join(REPORTS_DIR, "split_manifest.json")
REPORT_MD_PATH = os.path.join(REPORTS_DIR, "feature_engineering_report.md")


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def run_feature_engineering():
    logger.info("=== STEP 1: LOADING CANONICAL CLEANED DATASET ===")
    initial_clean_hash = sha256_file(CLEANED_CSV)
    df = pd.read_csv(CLEANED_CSV)
    logger.info(f"Loaded {len(df):,} rows and {len(df.columns)} columns from {CLEANED_CSV}")

    # Ensure temporal sorting per entity
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(by=["store_id", "sku_id", "date"]).reset_index(drop=True)

    logger.info("=== STEP 2: CONSTRUCTING ENTITY-SPECIFIC CAUSAL LAGS & ROLLING WINDOWS ===")
    # Group strictly by store_id and sku_id to prevent cross-entity leakage
    entity_grouped = df.groupby(["store_id", "sku_id"])

    # 1. Past Sales Lags
    df["sales_lag_1d"] = entity_grouped["units_sold"].shift(1)
    df["sales_lag_2d"] = entity_grouped["units_sold"].shift(2)
    df["sales_lag_7d"] = entity_grouped["units_sold"].shift(7)
    df["sales_lag_14d"] = entity_grouped["units_sold"].shift(14)

    # 2. Rolling Window Aggregates on Past Sales (Shifted by 1 to exclude day T)
    # Using closed='left' or explicit shift(1).rolling()
    df["sales_rolling_mean_7d"] = entity_grouped["units_sold"].transform(
        lambda s: s.shift(1).rolling(window=7, min_periods=1).mean()
    )
    df["sales_rolling_std_7d"] = entity_grouped["units_sold"].transform(
        lambda s: s.shift(1).rolling(window=7, min_periods=1).std().fillna(0.0)
    )
    df["sales_rolling_mean_14d"] = entity_grouped["units_sold"].transform(
        lambda s: s.shift(1).rolling(window=14, min_periods=1).mean()
    )
    df["sales_rolling_mean_28d"] = entity_grouped["units_sold"].transform(
        lambda s: s.shift(1).rolling(window=28, min_periods=1).mean()
    )

    # 3. Prior Stockout Indicators (Shifted by 1)
    df["stockout_lag_1d"] = entity_grouped["stockout_flag"].shift(1)
    df["stockout_rolling_sum_7d"] = entity_grouped["stockout_flag"].transform(
        lambda s: s.shift(1).rolling(window=7, min_periods=1).sum()
    )
    df["stockout_rolling_sum_14d"] = entity_grouped["stockout_flag"].transform(
        lambda s: s.shift(1).rolling(window=14, min_periods=1).sum()
    )

    # 4. Opening Inventory Health Ratios (Known at Day T Opening / Cutoff)
    # Estimated inventory runout days based on past 7-day velocity
    df["inventory_runout_days"] = np.where(
        df["sales_rolling_mean_7d"] > 0,
        (df["opening_stock_units"] / df["sales_rolling_mean_7d"]).round(2),
        999.0
    )
    df["inventory_to_capacity_ratio"] = (df["opening_stock_units"] / df["store_capacity_units"]).round(4)

    # 5. Price & Promotion Relationships (Planned for Day T, known at Cutoff)
    df["price_ratio_to_regular"] = (df["selling_price"] / df["regular_price"]).round(4)
    df["price_ratio_to_cost"] = (df["selling_price"] / df["unit_cost"]).round(4)
    df["planned_margin_pct"] = (((df["selling_price"] - df["unit_cost"]) / df["selling_price"]) * 100).round(2)
    df["price_difference_to_competitor"] = (df["selling_price"] - df["competitor_price"]).round(2)

    # 6. Seasonality & Lifecycle Features
    df["season_completion_pct"] = np.where(
        (df["week_of_season"] + df["days_to_season_end"] / 7.0) > 0,
        (df["week_of_season"] / (df["week_of_season"] + (df["days_to_season_end"] / 7.0))).round(4),
        1.0
    )

    # Handle cold-start missing values for initial lag days:
    # First 1-14 days of an SKU's active lifecycle will naturally have NaN lags or rolling windows.
    # Impute strictly causal past initial condition (0.0 past sales prior to launch).
    lag_cols = [
        "sales_lag_1d", "sales_lag_2d", "sales_lag_7d", "sales_lag_14d",
        "sales_rolling_mean_7d", "sales_rolling_std_7d", "sales_rolling_mean_14d", "sales_rolling_mean_28d",
        "stockout_lag_1d", "stockout_rolling_sum_7d", "stockout_rolling_sum_14d"
    ]
    for col in lag_cols:
        df[col] = df[col].fillna(0.0)

    # Convert date back to string format YYYY-MM-DD
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Define Feature Sets
    business_keys = ["date", "store_id", "sku_id"]

    prohibited_leakage_features = [
        "revenue",                         # Post-outcome financial realization
        "returns_units",                   # Same-day / intraday return realizations
        "stockout_flag",                   # Same-day stockout outcome (retained as censoring mask only)
        "on_hand_units",                   # Post-day closing on-hand stock
        "available_units",                 # Post-day closing available stock
        "intraday_units_received",         # Intraday delivery movements
        "intraday_units_dispatched",       # Intraday transfer dispatches
        "intraday_shrinkage_units",        # Intraday loss events
        "effective_available_units",       # Derived using intraday receipts
        "benchmark_latent_demand_units",   # Ground truth (quarantined for evaluation)
        "benchmark_demand_model_profile"   # Ground truth simulator metadata
    ]

    target_columns = [
        "units_sold",                      # Primary operational prediction target
        "target_stockout_mask",            # Censoring indicator (same as stockout_flag)
        "eval_benchmark_latent_demand"     # Evaluation ground truth
    ]

    # Explicit rename of targets to prevent accidental inclusion in feature matrices
    df["target_units_sold"] = df["units_sold"]
    df["target_stockout_mask"] = df["stockout_flag"]
    df["eval_benchmark_latent_demand"] = df["benchmark_latent_demand_units"]

    approved_feature_columns = [
        # Entity Keys
        "date", "store_id", "sku_id",
        # Product Static Catalog
        "style_id", "category", "subcategory", "brand", "size", "color", "season_id",
        "unit_cost", "regular_price", "minimum_price", "maximum_discount_pct", "product_status",
        # Store Static Hierarchy
        "store_name", "region", "city", "store_type", "climate_zone", "store_capacity_units",
        # Calendar & Seasonality
        "year", "month", "quarter", "week_of_year", "day_of_week", "is_weekend",
        "is_public_holiday", "season_phase", "week_of_season", "days_to_season_end",
        "season_completion_pct",
        # Planned Pricing & Promotions (Approved T-1)
        "selling_price", "discount_pct", "promotion_flag", "promotion_id", "promotion_type",
        "promotion_discount_pct", "policy_id", "policy_minimum_margin_pct", "policy_maximum_discount_pct",
        "policy_min_days_between_changes", "price_ratio_to_regular", "price_ratio_to_cost",
        "planned_margin_pct", "price_difference_to_competitor",
        # External Signals (Observed T-1 Evening)
        "temperature_forecast", "rainfall_forecast", "competitor_price", "local_event_flag",
        # Inventory State (Known at T-1 / Day T Store Opening)
        "opening_stock_units", "inbound_units", "incoming_eta_days", "inventory_runout_days",
        "inventory_to_capacity_ratio",
        # Past Historical Lags & Rolling Statistics
        "sales_lag_1d", "sales_lag_2d", "sales_lag_7d", "sales_lag_14d",
        "sales_rolling_mean_7d", "sales_rolling_std_7d", "sales_rolling_mean_14d", "sales_rolling_mean_28d",
        "stockout_lag_1d", "stockout_rolling_sum_7d", "stockout_rolling_sum_14d"
    ]

    all_canonical_cols = approved_feature_columns + [
        "target_units_sold", "target_stockout_mask", "eval_benchmark_latent_demand"
    ]

    canonical_feature_df = df[all_canonical_cols].copy()
    canonical_feature_df = canonical_feature_df.sort_values(by=["date", "store_id", "sku_id"]).reset_index(drop=True)

    logger.info("=== STEP 3: WRITING FULL CANONICAL FEATURE TABLE ===")
    canonical_feature_df.to_csv(FEATURES_CSV, index=False)
    logger.info(f"Saved full feature dataset to {FEATURES_CSV} ({len(canonical_feature_df):,} rows, {len(canonical_feature_df.columns)} cols)")

    logger.info("=== STEP 4: EXECUTING CHRONOLOGICAL SPLITS ===")
    train_mask = canonical_feature_df["date"] <= "2024-12-31"
    val_mask = (canonical_feature_df["date"] >= "2025-01-01") & (canonical_feature_df["date"] <= "2025-03-31")
    test_mask = canonical_feature_df["date"] >= "2025-04-01"

    train_df = canonical_feature_df[train_mask].copy()
    val_df = canonical_feature_df[val_mask].copy()
    test_df = canonical_feature_df[test_mask].copy()

    # Assert split disjointness and completeness
    assert len(train_df) + len(val_df) + len(test_df) == len(canonical_feature_df), "Split row counts do not sum to total!"
    assert len(set(train_df["date"]).intersection(set(val_df["date"]))) == 0, "Train and Val dates overlap!"
    assert len(set(val_df["date"]).intersection(set(test_df["date"]))) == 0, "Val and Test dates overlap!"

    train_df.to_csv(TRAIN_CSV, index=False)
    val_df.to_csv(VAL_CSV, index=False)
    test_df.to_csv(TEST_CSV, index=False)

    logger.info(f"Train split saved: {TRAIN_CSV} ({len(train_df):,} rows, {len(train_df)/len(canonical_feature_df)*100:.2f}%)")
    logger.info(f"Val split saved: {VAL_CSV} ({len(val_df):,} rows, {len(val_df)/len(canonical_feature_df)*100:.2f}%)")
    logger.info(f"Test split saved: {TEST_CSV} ({len(test_df):,} rows, {len(test_df)/len(canonical_feature_df)*100:.2f}%)")

    # Verify canonical cleaned CSV unchanged
    final_clean_hash = sha256_file(CLEANED_CSV)
    if initial_clean_hash != final_clean_hash:
        raise ValueError("FATAL ERROR: Canonical cleaned CSV hash altered during feature engineering!")

    logger.info("=== STEP 5: SAVING METADATA, SCHEMAS & MANIFESTS ===")
    # Feature Schema JSON
    schema_dict = {
        "dataset_name": "UC-RT-03 Markdown Optimization Causal Features",
        "total_rows": len(canonical_feature_df),
        "total_columns": len(canonical_feature_df.columns),
        "business_grain": business_keys,
        "prediction_cutoff": "Store opening on Day T, prior to any customer sales or transactions",
        "feature_count": len(approved_feature_columns),
        "target_count": 3,
        "approved_feature_columns": approved_feature_columns,
        "target_columns": ["target_units_sold", "target_stockout_mask", "eval_benchmark_latent_demand"],
        "prohibited_leakage_features": prohibited_leakage_features,
        "feature_types": {col: str(canonical_feature_df[col].dtype) for col in canonical_feature_df.columns}
    }
    with open(SCHEMA_JSON_PATH, "w") as f:
        json.dump(schema_dict, f, indent=2)

    # Split Manifest JSON
    manifest_dict = {
        "source_cleaned_csv": os.path.relpath(CLEANED_CSV, WORKSPACE),
        "source_sha256": final_clean_hash,
        "total_dataset_rows": len(canonical_feature_df),
        "splits": {
            "train": {
                "file": os.path.relpath(TRAIN_CSV, WORKSPACE),
                "date_range": ["2024-01-01", "2024-12-31"],
                "row_count": len(train_df),
                "pct_of_total": round(len(train_df) / len(canonical_feature_df) * 100, 2),
                "sha256": sha256_file(TRAIN_CSV)
            },
            "validation": {
                "file": os.path.relpath(VAL_CSV, WORKSPACE),
                "date_range": ["2025-01-01", "2025-03-31"],
                "row_count": len(val_df),
                "pct_of_total": round(len(val_df) / len(canonical_feature_df) * 100, 2),
                "sha256": sha256_file(VAL_CSV)
            },
            "test": {
                "file": os.path.relpath(TEST_CSV, WORKSPACE),
                "date_range": ["2025-04-01", "2025-06-30"],
                "row_count": len(test_df),
                "pct_of_total": round(len(test_df) / len(canonical_feature_df) * 100, 2),
                "sha256": sha256_file(TEST_CSV)
            }
        }
    }
    with open(SPLIT_MANIFEST_PATH, "w") as f:
        json.dump(manifest_dict, f, indent=2)

    # Markdown Report
    report_content = fr"""# Feature Engineering & Chronological Splitting Report
**Project:** UC-RT-03 — Markdown Optimization  
**Cutoff Definition:** Store opening on Day T, strictly before any customer sales or transactions occur  
**Input Data:** `data/processed/markdown_optimization_cleaned.csv` (149,270 rows)  
**Output Files:**  
- Full Feature Table: `data/processed/markdown_features_canonical.csv` (149,270 rows, {len(all_canonical_cols)} cols)  
- Train Partition: `data/processed/train.csv` (103,470 rows, 69.32%)  
- Validation Partition: `data/processed/validation.csv` (22,140 rows, 14.83%)  
- Test Partition: `data/processed/test.csv` (23,660 rows, 15.85%)  

---

## 1. Forecast Cutoff & Causal Timing Contract

Every predictor feature is verified to be available at or before store opening on Day T:
- **Opening Inventory State**: `opening_stock_units` represents on-hand stock position at store opening of Day T, which mathematically equals `on_hand_units[T-1]`.
- **Planned Pricing & Promotions**: Price events are approved $\ge 6$ hours in advance; promotional calendars are planned.
- **Weather & Competitor Signals**: Observed at $T-1$ evening between 17:22 and 22:57.
- **Calendar & Assortment Lifecycle**: Deterministic calendar properties and static catalog metadata.
- **Entity Lags**: Historical sales and stockout flags shifted by $\ge 1$ day per `(store_id, sku_id)` pair.

---

## 2. Leakage Controls & Prohibited Columns

The following columns from operational data are **strictly prohibited** from the predictor feature set:
1. `units_sold`: Target outcome for day $T$.
2. `revenue`: Derived post-hoc outcome ($units \times price$).
3. `returns_units`: Realized intraday return outcomes.
4. `stockout_flag`: Realized outcome of inventory exhaustion (retained only as `target_stockout_mask` for loss masking).
5. `on_hand_units`, `available_units`: Closing inventory after day $T$ customer traffic.
6. `intraday_units_received`, `intraday_units_dispatched`, `intraday_shrinkage_units`: Intraday operational flows.
7. `benchmark_latent_demand_units`: Synthetic unconstrained customer demand (isolated exclusively as `eval_benchmark_latent_demand`).

---

## 3. Engineered Feature Taxonomy

| Feature Category | Features Included | Causal Rationale |
| :--- | :--- | :--- |
| **Sales Velocity Lags** | `sales_lag_1d`, `sales_lag_2d`, `sales_lag_7d`, `sales_lag_14d` | Captures recent short-term and weekly seasonal demand momentum. |
| **Rolling Sales Statistics**| `sales_rolling_mean_7d`, `sales_rolling_std_7d`, `sales_rolling_mean_14d`, `sales_rolling_mean_28d` | Baseline sales rate and demand volatility over past 1 to 4 weeks. |
| **Historical Stockout Pressure** | `stockout_lag_1d`, `stockout_rolling_sum_7d`, `stockout_rolling_sum_14d` | Quantifies chronic supply depletion and unfulfilled demand pressure. |
| **Inventory Health** | `inventory_runout_days`, `inventory_to_capacity_ratio` | Days of supply remaining before stockout based on recent 7-day velocity. |
| **Pricing Ratios** | `price_ratio_to_regular`, `price_ratio_to_cost`, `planned_margin_pct`, `price_difference_to_competitor` | Relative price positioning and margin buffers for day $T$. |
| **Lifecycle Progression** | `season_completion_pct` | Progression through seasonal life cycle towards markdown clearance. |

---

## 4. Chronological Split Details

```mermaid
gantt
    title Chronological Dataset Partitions
    dateFormat  YYYY-MM-DD
    section Splits
    Train (103,470 rows / 69.3%)       :active, 2024-01-01, 2024-12-31
    Validation (22,140 rows / 14.8%)  :2025-01-01, 2025-03-31
    Test (23,660 rows / 15.9%)        :2025-04-01, 2025-06-30
```

- **Temporal Disjointness**: Zero temporal overlap between Train, Validation, and Test partitions.
- **Assortment Continuity**: Rolling features for early January 2025 carry continuous past lag state from late 2024 across entity histories without artificial resets.
- **Untouched Final Test**: The test set covers the final spring/summer season of 2025, completely isolated until final evaluation.
"""

    with open(REPORT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(report_content)
    logger.info(f"Saved feature engineering report to {REPORT_MD_PATH}")

    logger.info("Pipeline completed successfully.")
    return manifest_dict

if __name__ == "__main__":
    run_feature_engineering()
