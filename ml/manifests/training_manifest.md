# UC-RT-03 Markdown Optimization: ML Model Training and Governance Manifest

- **Pipeline Run Timestamp**: 2026-10-19 12:05:00
- **Workspace**: `C:\MarkDown Optimization Usecase`
- **Execution Python**: 3.14.5
- **Key Dependencies**:
  - `xgboost`: 3.3.0
  - `scikit-learn`: 1.9.0
  - `pandas`: 2.2.2
  - `numpy`: 2.1.2
  - `joblib`: 1.5.3
  - `pyyaml`: 6.0.3
  - `pytest`: 8.2.0

---

## 1. Data Contracts and Hashes

- **Source Cleaned Dataset**: `data/processed/markdown_optimization_cleaned.csv`
  - Total Rows: 149,270
  - SHA256: `e8348157440d4d3320100582ac8b6dfc921f89f24b76b0caa159bc001cfbe2dd`
- **Canonical Feature Matrix**: `data/processed/markdown_features_canonical.csv`
  - Rows: 149,270 | Columns: 69 (Date + 65 Store-Opening Pre-Sales Features + 3 Ground Truth Targets)
- **Time-Based Splits**:
  - **Train**: 2024-01-01 to 2024-12-31 | 103,470 rows (69.32%) | SHA256: `d1e08c186bed92c0af14dfc37da7fbf05cdf40831e0984baa2b65d7ab349bada`
  - **Validation**: 2025-01-01 to 2025-03-31 | 22,140 rows (14.83%) | SHA256: `f0b2f8622f4d610cfb05128037d2553ba14e3c920b0da40f49df36555d183aa0`
  - **Test (Frozen)**: 2025-04-01 to 2025-06-30 | 23,660 rows (15.85%) | SHA256: `bd7c8bf64b1a44e0c87968f2ee53b7a191aa636e4d8b88f68ea53297c0e1d6d3`
- **Prediction Cutoff**: Store opening on Day T, prior to any customer sales or inventory movements.

---

## 2. Model Governance and Evaluation Summary

### Model 1: Daily Demand Forecasting
- **Status**: **APPROVED FOR PRODUCTION PILOT**
- **Target**: `target_units_sold` (regression)
- **Baseline**: Historical 7-day trailing mean per entity (`past-only`)
- **Challenger**: XGBoost Regressor (`n_estimators=350, max_depth=5, lr=0.05`)
- **Validation Comparison (22,140 rows)**:
  - Baseline: MAE = 0.7804, RMSE = 1.1775, WAPE = 100.28%
  - Candidate: **MAE = 0.7570, RMSE = 1.1135, WAPE = 97.28%** (Delta WAPE: -3.00 pp)
- **Test Performance (Frozen Test Set, 23,660 rows)**:
  - Baseline: MAE = 0.4553, RMSE = 0.8422, WAPE = 115.67%
  - Candidate: **MAE = 0.4228, RMSE = 0.7702, WAPE = 107.42%** (Delta WAPE: -8.25 pp absolute, -7.13% relative)
- **Subgroup Breakdown (Test Set)**:
  - In-Stock Days (19,232 obs): MAE = 0.5098, RMSE = 0.8468, WAPE = 107.43%
  - Stockout Days (4,428 obs): MAE = 0.0448, RMSE = 0.2355, WAPE = 106.61%
- **Artifacts**:
  - Model: `ml/artifacts/model1/xgboost_demand_model.joblib`
  - Predictions: `ml/artifacts/model1/test_predictions_demand.csv`
  - Full Report: `data/reports/model1_demand/demand_model_evaluation.md`

### Model 2: Price-Response Estimation
- **Status**: **EXPERIMENTAL_DECISION_SUPPORT (Controlled Pilot Only)**
- **Target**: Fulfilled sales under candidate price scenarios
- **Baseline**: Ridge Regularized Linear Price-Response Regression
- **Challenger**: XGBoost Regressor with Price/Discount Context Features
- **Validation Comparison**:
  - Baseline: MAE = 0.6950, RMSE = 1.1487, WAPE = 89.32%
  - Candidate: MAE = 0.7485, RMSE = 1.1023, WAPE = 96.18%
- **Test Performance (Frozen Test Set)**:
  - Baseline: MAE = 0.4047, RMSE = 0.8012, WAPE = 102.83%
  - Candidate: MAE = 0.4160, **RMSE = 0.7658**, WAPE = 105.68%
- **Scenario Stability Audit**: Tested over discount steps 0% to 50%; exhibits consistent monotonic demand expansion across product categories.
- **Caveat**: Non-causal observational retail data; deep discounts co-occurred historically with clearance/season-end. Rollout must be bounded by deterministic pricing rules.
- **Artifacts**:
  - Model: `ml/artifacts/model2/xgboost_price_response_model.joblib`
  - Predictions: `ml/artifacts/model2/test_predictions_price_response.csv`
  - Stability Matrix: `data/reports/model2_price_response/price_scenario_stability.csv`
  - Full Report: `data/reports/model2_price_response/price_response_evaluation.md`

### Model 3: Seven-Day Stockout Risk Classification
- **Status**: **APPROVED FOR PRODUCTION PILOT**
- **Target**: `stockout_within_next_7_days` (Days $T+1$ to $T+7$ forward window)
- **Baseline**: Deterministic Inventory Runout Rule `(opening_stock + inbound) < 7 * sales_rolling_mean_7d`
- **Challenger**: XGBoost Classifier (`n_estimators=300, max_depth=5, lr=0.05, scale_pos_weight=3.0`, trained on split-boundary purged labels)
- **Test Performance (Frozen Test Set, 22,918 uncensored rows)**:
  - Baseline Rule: Precision = 0.7939, **Recall = 0.2377**, F1 = 0.3658 (7,412 False Negatives!)
  - Candidate XGBoost: **Precision = 0.8049, Recall = 0.9717, F1 = 0.8805, PR-AUC = 0.9421, ROC-AUC = 0.9623**
- **Value-Add Assessment**: Massive improvement (+0.5147 F1) over the baseline rule by anticipating lead times, surges, and inventory depletion while strictly preventing split-boundary lookahead leakage.
- **Artifacts**:
  - Model: `ml/artifacts/model3/xgboost_stockout_model.joblib`
  - Predictions: `ml/artifacts/model3/test_predictions_stockout.csv`
  - Audit: `data/reports/model3_stockout_risk/stockout_label_construction_audit.md`
  - Full Report: `data/reports/model3_stockout_risk/stockout_risk_evaluation.md`

---

## 3. Deterministic Markdown Optimizer Integration

- **Module**: `ml/optimizer/optimizer.py`
- **Pricing Policy Precedence**: `SKU` > `STORE` > `CATEGORY` > `CHAIN`
- **Binding Constraints**:
  - Allowed markdown discount steps (e.g. 0%, 10%, 20%, 30%, 40%, 50%)
  - Minimum gross margin percentage (10% to 15%)
  - Minimum floor price
  - Maximum discount limits (e.g. 30% for high-velocity jackets under `POL-009` through `POL-013`)
  - Inventory availability cap: Fulfilled 7-day units $\le$ `opening_stock_units`
  - High Stockout Risk Penalty: Applied when Model 3 stockout probability $> 60\%$
- **Human Approval Gate**: Requires explicit role sign-off (`APPROVED_BY_RULE_AND_HUMAN` logged in audit trail).
- **Pilot Run Results**: `data/reports/optimizer/pilot_recommendations_summary.csv` and `data/reports/optimizer/pilot_optimization_audit.json`.
