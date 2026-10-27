# Model 2: Price-Response Estimation Evaluation Report
**Model Type:** XGBoost Regressor (Candidate) vs Ridge Price Regression (Baseline)  
**Target:** `target_units_sold` (Observed daily sales per SKU-Store at store opening)  
**Classification:** **EXPERIMENTAL / DECISION SUPPORT ONLY**  
*(Explicit Scientific Caveat: Predictions under candidate prices represent learned associations from historical pricing policies. They are not guaranteed causal elasticity curves.)*

---

## 1. Held-Out Predictive Performance Comparison

| Dataset Split | Model | MAE | RMSE | WAPE (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Validation (Q1 2025)** | **Ridge Linear Baseline** | 0.695 | 1.1487 | 89.32% |
| **Validation (Q1 2025)** | **XGBoost Price-Response** | **0.7485** | **1.1023** | **96.18%** |
| **Test (Q2 2025 - Frozen)** | **Ridge Linear Baseline** | **0.4047** | 0.8012 | **102.83%** |
| **Test (Q2 2025 - Frozen)** | **XGBoost Price-Response** | 0.4160 | **0.7658** | 105.68% |

> **Audit Observation & Model Selection Rationale**:
> - **Ridge Wins on Primary Retail Demand Metrics**: Ridge achieves lower MAE (0.4047 vs 0.4160) and lower WAPE (102.83% vs 105.68%).
> - **XGBoost Chosen for Non-Linear Scenario Elasticity & Variance Control**: XGBoost achieves lower RMSE (0.7658 vs 0.8012, -4.4% penalty on large outlier misses) and captures interaction terms (e.g., category-specific discount saturation).
> - **Governance Mandate**: Because there is no unambiguous winner across all metrics, Model 2 retains strict **EXPERIMENTAL** status and must not autonomously enact unconstrained pricing decisions without human supervisory sign-off.

---

## 2. Counterfactual Price Scenario Stability

Sample demand curves predicted across candidate discount steps ($0\% 	o 50\%$):

| SKU ID | Category | Regular Price | Candidate Discount | Candidate Price | Predicted Daily Demand | Expected Unit Margin |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| SKU-0141 | TShirt | ₹799 | 0.0% | ₹799.0 | **1.02** units | ₹489.0 |
| SKU-0141 | TShirt | ₹799 | 10.0% | ₹719.1 | **1.283** units | ₹409.1 |
| SKU-0141 | TShirt | ₹799 | 20.0% | ₹639.2 | **1.446** units | ₹329.2 |
| SKU-0141 | TShirt | ₹799 | 30.0% | ₹559.3 | **1.539** units | ₹249.3 |
| SKU-0141 | TShirt | ₹799 | 40.0% | ₹479.4 | **1.691** units | ₹169.4 |
| SKU-0141 | TShirt | ₹799 | 50.0% | ₹399.5 | **1.852** units | ₹89.5 |
| SKU-0161 | Dress | ₹2499 | 0.0% | ₹2499.0 | **0.281** units | ₹1576.0 |
| SKU-0161 | Dress | ₹2499 | 10.0% | ₹2249.1 | **0.318** units | ₹1326.1 |
| SKU-0161 | Dress | ₹2499 | 20.0% | ₹1999.2 | **0.354** units | ₹1076.2 |
| SKU-0161 | Dress | ₹2499 | 30.0% | ₹1749.3 | **0.423** units | ₹826.3 |
| SKU-0161 | Dress | ₹2499 | 40.0% | ₹1499.4 | **0.462** units | ₹576.4 |
| SKU-0161 | Dress | ₹2499 | 50.0% | ₹1249.5 | **0.86** units | ₹326.5 |

---

## 3. Production Governance & Caveats

1. **Approved Role**: Used inside the downstream Markdown Optimizer to supply candidate demand estimates for candidate prices.
2. **Deterministic Fallbacks**: Must be bounded by binding business constraints (`minimum_price`, `minimum_margin_pct`, `maximum_discount_pct`).
3. **Causal Attribution Disclaimer**: Model reflects observational retail data where deep discounts co-occurred with season end; real-world rollout requires controlled A/B testing.
