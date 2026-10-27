# Store-Opening Feature Availability Audit Report: Inventory Features

**Project:** UC-RT-03 — Markdown Optimization  
**Auditor:** Senior Data Engineer & ML Leakage Auditor  
**Workspace:** `C:\MarkDown Optimization Usecase`  
**Audit Date:** 2026-10-18T18:42:00+05:30  
**Cutoff Contract:** Store opening on Day T, strictly before any customer sales or transactions occur that day.

---

## 1. Executive Summary & Status

### **FINAL STATUS: READY FOR PHASE 3B**

All four audited inventory features (`inbound_units`, `incoming_eta_days`, `inventory_runout_days`, and `inventory_to_capacity_ratio`) along with `opening_stock_units` have been rigorously inspected and verified against raw source data, timestamps, movement registries, and derivation code. 

**Summary of Decisions:**
- `inbound_units`: **PASS** (Confirmed in-transit order quantity known at opening; does not contain intraday receipts).
- `incoming_eta_days`: **PASS** (Confirmed days until scheduled arrival countdown; strictly strictly prior-planned logistical pipeline).
- `inventory_runout_days`: **PASS** (Derived strictly from `opening_stock_units` and strictly causal $T-1$ past 7-day rolling mean sales).
- `inventory_to_capacity_ratio`: **PASS** (Derived strictly from `opening_stock_units` and static `store_capacity_units`).

---

## 2. In-Depth Feature Audit Evidence

### Feature 1: `inbound_units` — **STATUS: PASS**
- **Provenance & Source Table**: Derived from `inventory_snapshots.csv:inbound_units`.
- **Semantics**: Represents purchase orders or warehouse transfers dispatched and currently in-transit toward the destination store.
- **Audit Findings**:
  - Across 149,270 records, exactly **558 records** have active inbound shipments (`inbound_units > 0`, ranging from 5 to 40 units).
  - Traced against `inventory_movements.csv`: On `2024-03-11`, `STORE-01` / `SKU-0028` had `inbound_units = 7`. This shipment corresponds to purchase order `MOV-0002050` (`quantity_units = 7`, `movement_type = RECEIPT`) which was dispatched from `WAREHOUSE` and arrived on `2024-03-19`.
  - During the transit window (`2024-03-11` to `2024-03-18`), `inbound_units` remained 7, and decremented to 0 on `2024-03-19` when physical receipt took place.
  - **Leakage Check**: Does **not** include intraday receipts of day T. Only represents orders shipped prior to day T that have not yet arrived. Fully verified available at store opening on Day T.

### Feature 2: `incoming_eta_days` — **STATUS: PASS**
- **Provenance & Source Table**: Derived from `inventory_snapshots.csv:incoming_eta_days`.
- **Semantics**: An integer countdown tracking scheduled transit days remaining until inbound delivery arrival.
- **Audit Findings**:
  - In the traced purchase order `MOV-0002050` above, `incoming_eta_days` decrements day-by-day:
    - 2024-03-11: ETA = 8 days
    - 2024-03-12: ETA = 7 days
    - 2024-03-13: ETA = 6 days
    - ...
    - 2024-03-18: ETA = 1 day
    - 2024-03-19: ETA = 0 days (Receipt completed).
  - **Leakage Check**: Derived purely from supply chain purchase order schedules known at store opening. Zero incorporation of same-day transactions.

### Feature 3: `inventory_runout_days` — **STATUS: PASS**
- **Provenance & Derivation**:  
  $$\text{inventory\_runout\_days} = \frac{\text{opening\_stock\_units}[T]}{\text{sales\_rolling\_mean\_7d}[T-1]}$$
- **Semantics**: Estimated days of supply remaining before store exhaustion if past 7-day velocity continues.
- **Audit Findings**:
  - Numerator is `opening_stock_units` (verified equal to `on_hand_units[T-1]`).
  - Denominator is `sales_rolling_mean_7d`, which is constructed via `shift(1).rolling(window=7, min_periods=1).mean()`, strictly using sales from days $T-7$ through $T-1$.
  - When past velocity is 0, safely set to ceiling placeholder 999.0 days.
  - **Leakage Check**: Excludes all same-day sales, same-day returns, and intraday receipts. Zero leakage.

### Feature 4: `inventory_to_capacity_ratio` — **STATUS: PASS**
- **Provenance & Derivation**:  
  $$\text{inventory\_to\_capacity\_ratio} = \frac{\text{opening\_stock\_units}[T]}{\text{store\_capacity\_units}}$$
- **Semantics**: SKU physical footprint relative to overall store shelf/storage capacity.
- **Audit Findings**:
  - `opening_stock_units` is the verified opening inventory balance.
  - `store_capacity_units` is static store metadata from `stores.csv` (10,000 to 20,000 units).
  - Ratios range from 0.0000 to 0.0473 (mean 0.0035).
  - **Leakage Check**: Purely pre-opening inputs. Zero post-opening or intraday data.

---

## 3. Verified Allowlist vs Excluded Features

### Approved Inference Features (66 Columns)
The allowlist remains intact with all 66 verified features:
- **Assortment / SKU (15)**: `date`, `store_id`, `sku_id`, `style_id`, `category`, `subcategory`, `brand`, `size`, `color`, `season_id`, `unit_cost`, `regular_price`, `minimum_price`, `maximum_discount_pct`, `product_status`.
- **Store Metadata (6)**: `store_name`, `region`, `city`, `store_type`, `climate_zone`, `store_capacity_units`.
- **Calendar & Seasonality (11)**: `year`, `month`, `quarter`, `week_of_year`, `day_of_week`, `is_weekend`, `is_public_holiday`, `season_phase`, `week_of_season`, `days_to_season_end`, `season_completion_pct`.
- **Planned Pricing & Promotions (14)**: `selling_price`, `discount_pct`, `promotion_flag`, `promotion_id`, `promotion_type`, `promotion_discount_pct`, `policy_id`, `policy_minimum_margin_pct`, `policy_maximum_discount_pct`, `policy_min_days_between_changes`, `price_ratio_to_regular`, `price_ratio_to_cost`, `planned_margin_pct`, `price_difference_to_competitor`.
- **External Signals (4)**: `temperature_forecast`, `rainfall_forecast`, `competitor_price`, `local_event_flag`.
- **Opening Inventory State (5)**: `opening_stock_units`, `inbound_units`, `incoming_eta_days`, `inventory_runout_days`, `inventory_to_capacity_ratio`.
- **Causal Historical Lags (11)**: `sales_lag_1d`, `sales_lag_2d`, `sales_lag_7d`, `sales_lag_14d`, `sales_rolling_mean_7d`, `sales_rolling_std_7d`, `sales_rolling_mean_14d`, `sales_rolling_mean_28d`, `stockout_lag_1d`, `stockout_rolling_sum_7d`, `stockout_rolling_sum_14d`.

### Strictly Prohibited Post-Opening Fields
1. `target_units_sold`: Supervised target (fulfilled sales).
2. `target_stockout_mask`: Evaluation censoring indicator.
3. `eval_benchmark_latent_demand`: Offline simulation evaluation.
4. `revenue`, `returns_units`: Post-opening financial outcomes.
5. `on_hand_units`, `available_units`: Closing inventory.
6. `intraday_units_received/dispatched/shrinkage`, `effective_available_units`: Intraday delivery flows.

---

## 4. Preservation & Verification Results
- **Cleaned Dataset Preservation**: `data/processed/markdown_optimization_cleaned.csv` remains 100% untouched.
- **Split Lineage**: Train (103,470), Val (22,140), Test (23,660).
- **Automated Test Results**:
  - `test_feature_engineering.py`: **9/9 tests passed**
  - `test_eda.py`: **6/6 tests passed**
