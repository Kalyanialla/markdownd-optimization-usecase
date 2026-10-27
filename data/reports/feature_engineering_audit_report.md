# Phase 3A Feature Engineering & Leakage Prevention Audit Report

**Project:** UC-RT-03 — Markdown Optimization  
**Auditor:** Senior ML Engineer & Independent Leakage Auditor  
**Audit Timestamp:** 2026-10-18T18:26:00+05:30  
**Inspected Artifacts:**
- `data/processed/run_feature_engineering.py`
- `data/processed/test_feature_engineering.py`
- `data/processed/markdown_features_canonical.csv` (149,270 rows, 69 columns)
- `data/processed/train.csv` (103,470 rows, 69.32%)
- `data/processed/validation.csv` (22,140 rows, 14.83%)
- `data/processed/test.csv` (23,660 rows, 15.85%)
- `data/reports/feature_schema.json`
- `data/reports/split_manifest.json`
- `data/reports/feature_engineering_report.md`
- `data/processed/markdown_optimization_cleaned.csv` (Canonical dataset)

---

## 1. Executive Audit Decision

### **FINAL DECISION: PHASE 3A APPROVED FOR BASELINE MODELING**

**Core Verdict:**
- **Zero Leakage**: All 66 approved inference features have proven availability prior to the forecast cutoff ($T-1$ at 23:59:59).
- **Prohibited Outcomes Excluded**: Target realizations (`target_units_sold`), same-day financials (`revenue`, `returns_units`), realized stockout indicators (`stockout_flag`), closing inventories (`on_hand_units`, `available_units`), intraday movements, and synthetic latent ground truth (`eval_benchmark_latent_demand`) are strictly excluded from the approved feature contract.
- **Sparse Time-Series & Contiguity Verified**: All 870 active store-SKU time series have zero interior calendar gaps within their active lifecycle windows. Lags ($T-1$, $T-7$) and rolling averages (7d, 14d, 28d) correspond to true calendar days without temporal distortion.
- **Chronological Split Integrity**: Zero date overlap across Train, Validation, and Test sets. All file hashes match `split_manifest.json`.
- **Preservation of Source Files**: `markdown_optimization_cleaned.csv` and all 11 raw source CSVs remain 100% untouched and identical in hash.

---

## 2. Finding-by-Finding Audit Matrix

| Audit Dimension | Target / Feature Scope | Measured Evidence | Severity | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Prediction Cutoff Reconciled** | Cutoff: $T-1$ at 23:59:59 vs Day $T$ Opening | `opening_stock_units` represents on-hand stock at store opening of day $T$ before customer transactions begin. All pricing, promotional, and weather features are proven available prior to midnight $T-1$. | Informational | **PASS** |
| **2. Price/Promotion Availability** | `selling_price`, `discount_pct`, promotions, competitor price | `price_history.csv` shows 100% of price changes approved $\ge 1$ day before `effective_from`. `external_signals.csv` competitor and weather signals recorded between 17:22 and 22:57 of $T-1$. | Critical | **PASS** |
| **3. Sparse Time-Series Contiguity** | Active grid vs calendar continuity | 870 distinct store-SKU entities. Audit proved **0 entities have interior date gaps** between launch and season end. `shift(1)` is mathematically identical to a 1-day calendar lag. | High | **PASS** |
| **4. Lag & Rolling Leakage** | `sales_lag_*`, `sales_rolling_*`, `stockout_lag_*` | Strictly shifted by 1 row within entity groupby. Day $T$ target outcome is proven absent from all rolling aggregations. Verified across multiple sample entities. | Critical | **PASS** |
| **5. Target & Censoring Contract** | `target_units_sold`, `target_stockout_mask` | `target_units_sold` is observed fulfilled sales; `target_stockout_mask` is preserved strictly as an evaluation loss mask. Ground truth is isolated as `eval_benchmark_latent_demand`. | Critical | **PASS** |
| **6. Split Integrity & Hashes** | Train (2024), Val (Q1 2025), Test (Q2 2025) | Exact row lineage verified: 103,470 + 22,140 + 23,660 = 149,270. Zero date overlap. SHA-256 hashes in `split_manifest.json` match actual files on disk. | High | **PASS** |
| **7. Source Integrity & Determinism** | `markdown_optimization_cleaned.csv` | SHA-256 hash verified identical before and after feature engineering. Deterministic rerun verified. | Critical | **PASS** |
| **8. SyntaxWarning Remediation** | `run_feature_engineering.py` line 282 | Replaced standard string prefix with raw f-string `fr"""` in `report_content` to cleanly resolve LaTeX `\ge` escape warning. | Low | **PASS (Fixed)** |

---

## 3. Approved Inference Features & Prohibited Fields

### Approved Feature Matrix (66 Predictor Columns)
- **Entity Keys & Assortment Metadata (15)**: `date`, `store_id`, `sku_id`, `style_id`, `category`, `subcategory`, `brand`, `size`, `color`, `season_id`, `unit_cost`, `regular_price`, `minimum_price`, `maximum_discount_pct`, `product_status`.
- **Store Attributes (6)**: `store_name`, `region`, `city`, `store_type`, `climate_zone`, `store_capacity_units`.
- **Calendar & Seasonality (11)**: `year`, `month`, `quarter`, `week_of_year`, `day_of_week`, `is_weekend`, `is_public_holiday`, `season_phase`, `week_of_season`, `days_to_season_end`, `season_completion_pct`.
- **Planned Pricing & Promotions (14)**: `selling_price`, `discount_pct`, `promotion_flag`, `promotion_id`, `promotion_type`, `promotion_discount_pct`, `policy_id`, `policy_minimum_margin_pct`, `policy_maximum_discount_pct`, `policy_min_days_between_changes`, `price_ratio_to_regular`, `price_ratio_to_cost`, `planned_margin_pct`, `price_difference_to_competitor`.
- **External Signals (4)**: `temperature_forecast`, `rainfall_forecast`, `competitor_price`, `local_event_flag`.
- **Opening Inventory State (5)**: `opening_stock_units`, `inbound_units`, `incoming_eta_days`, `inventory_runout_days`, `inventory_to_capacity_ratio`.
- **Causal Entity Lags & Rolling Dynamics (11)**: `sales_lag_1d`, `sales_lag_2d`, `sales_lag_7d`, `sales_lag_14d`, `sales_rolling_mean_7d`, `sales_rolling_std_7d`, `sales_rolling_mean_14d`, `sales_rolling_mean_28d`, `stockout_lag_1d`, `stockout_rolling_sum_7d`, `stockout_rolling_sum_14d`.

### Strictly Prohibited Columns (Excluded from Feature Matrix)
1. `target_units_sold`: Target outcome to be predicted.
2. `revenue`, `returns_units`: Post-outcome realizations.
3. `target_stockout_mask` (`stockout_flag`): Censoring indicator used exclusively for loss masking and evaluation.
4. `on_hand_units`, `available_units`: End-of-day closing inventory.
5. `intraday_units_received`, `intraday_units_dispatched`, `intraday_shrinkage_units`, `effective_available_units`: Intraday operational flows.
6. `eval_benchmark_latent_demand`, `benchmark_demand_model_profile`: Synthetic unconstrained demand (offline evaluation benchmark only).

---

## 4. Methodological Note on Demand Censoring

- Observed sales (`target_units_sold`) are **right-censored on 18,696 store-days (12.52%)** where `target_stockout_mask == 1`.
- On stockout days, observed sales reflect available stock, not true customer demand.
- Downstream baseline models must evaluate performance with censoring-aware metrics (e.g. evaluating prediction error on uncensored days vs full population) and avoid treating stockout zeros as evidence of zero customer demand.
