# Store-Opening Cutoff & Feature Availability Audit Report

**Project:** UC-RT-03 — Markdown Optimization  
**Auditor:** Senior ML Engineer, Data Engineer & Independent Leakage Auditor  
**Audit Timestamp:** 2026-10-18T18:35:00+05:30  
**Timing Contract Reconciled:** Store opening on Day T, strictly before any customer sales or transactions occur.  

---

## 1. Executive Status

### **FINAL DECISION: PHASE 3A APPROVED FOR BASELINE MODELING**

---

## 2. Evidence of Provenance, Lead-Time & Allowlist

### 1. Inventory Provenance Evidence
- **Mathematical Relationship**: In `inventory_snapshots.csv`, we proved that across all 148,400 daily entity transitions:
  $$\text{opening\_stock\_units}[T] \equiv \text{on\_hand\_units}[T-1] \quad (\mathbf{148,400 / 148,400 \text{ exact matches, 0 discrepancies}})$$
- **Separation from Intraday Transactions**: `opening_stock_units` represents strictly the opening balance before store opening. Closing stock `on_hand_units[T]` incorporates day T transactions ($\text{opening} - \text{sales} + \text{returns} + \text{receipts} - \text{dispatches}$). `on_hand_units[T]` and all intraday movement quantities remain **strictly prohibited** from the inference feature matrix.

### 2. Pricing, Promotion & Signal Timestamp Evidence
- **Price Approval Lead Time**: Inspection of `price_history.csv` against `effective_from` dates shows that **100% of approved price events (7,712/7,712)** were approved at least **6.02 hours** prior to store opening (00:00:00 of Day T). Zero price events were approved during or after day T trading.
- **External Forecast Observation Timestamps**: In `external_signals.csv`, weather forecasts were recorded between 17:22 and 19:35 of $T-1$ (lead time 4.02 to 7.00 hours prior to midnight), and competitor prices were recorded between 20:16 and 22:57 of $T-1$ (lead time 1.02 to 4.00 hours prior to midnight). Both were known and immutable before store opening on Day T.

### 3. Model Inference Allowlist & Matrix Construction
- **Approved Feature Count**: Exactly **66 features** verified available at store opening.
- **Construction Test**: Test `test_08_explicit_model_matrix_allowlist_validation` builds the actual feature matrices $X_{\text{train}} \in \mathbb{R}^{103,470 \times 66}$ and $X_{\text{test}} \in \mathbb{R}^{23,660 \times 66}$, proving that all targets, post-outcome metrics, and ground truth columns are excluded.

---

## 3. Approved Feature Matrix vs Prohibited Columns

| Category | Count | Fields Included |
| :--- | :--- | :--- |
| **Entity & Catalog** | 15 | `date`, `store_id`, `sku_id`, `style_id`, `category`, `subcategory`, `brand`, `size`, `color`, `season_id`, `unit_cost`, `regular_price`, `minimum_price`, `maximum_discount_pct`, `product_status` |
| **Store Hierarchy** | 6 | `store_name`, `region`, `city`, `store_type`, `climate_zone`, `store_capacity_units` |
| **Calendar Context** | 11 | `year`, `month`, `quarter`, `week_of_year`, `day_of_week`, `is_weekend`, `is_public_holiday`, `season_phase`, `week_of_season`, `days_to_season_end`, `season_completion_pct` |
| **Planned Pricing & Promotions**| 14 | `selling_price`, `discount_pct`, `promotion_flag`, `promotion_id`, `promotion_type`, `promotion_discount_pct`, `policy_id`, `policy_minimum_margin_pct`, `policy_maximum_discount_pct`, `policy_min_days_between_changes`, `price_ratio_to_regular`, `price_ratio_to_cost`, `planned_margin_pct`, `price_difference_to_competitor` |
| **External Signals** | 4 | `temperature_forecast`, `rainfall_forecast`, `competitor_price`, `local_event_flag` |
| **Opening Inventory State** | 5 | `opening_stock_units`, `inbound_units`, `incoming_eta_days`, `inventory_runout_days`, `inventory_to_capacity_ratio` |
| **Causal Lags & Rolling Dynamics** | 11 | `sales_lag_1d`, `sales_lag_2d`, `sales_lag_7d`, `sales_lag_14d`, `sales_rolling_mean_7d`, `sales_rolling_std_7d`, `sales_rolling_mean_14d`, `sales_rolling_mean_28d`, `stockout_lag_1d`, `stockout_rolling_sum_7d`, `stockout_rolling_sum_14d` |
| **Total Approved Features** | **66** | |

### Strictly Excluded Fields
1. `target_units_sold`: Supervised modeling target (fulfilled sales).
2. `target_stockout_mask`: Censoring mask (used for loss evaluation, never as an inference feature).
3. `eval_benchmark_latent_demand`: Offline benchmark evaluation only.
4. `revenue`, `returns_units`: Realized transactions.
5. `on_hand_units`, `available_units`: Closing inventory.
6. `intraday_units_received`, `intraday_units_dispatched`, `intraday_shrinkage_units`, `effective_available_units`: Intraday operational flows.

---

## 4. Chronological Splits & SHA-256 Hashes

- **Train**: 2024-01-01 to 2024-12-31 | **103,470 rows (69.32%)** | SHA-256 verified in `split_manifest.json`
- **Validation**: 2025-01-01 to 2025-03-31 | **22,140 rows (14.83%)** | SHA-256 verified in `split_manifest.json`
- **Test**: 2025-04-01 to 2025-06-30 | **23,660 rows (15.85%)** | SHA-256 verified in `split_manifest.json`
- **Canonical Cleaned Dataset**: Preserved byte-for-byte (`markdown_optimization_cleaned.csv`).
