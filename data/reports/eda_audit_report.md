# Independent Senior ML Engineer Audit Report: UC-RT-03 EDA Phase

**Project:** UC-RT-03 — Markdown Optimization  
**Auditor:** Senior ML Engineer & Independent Reviewer  
**Audit Timestamp:** 2026-10-18T17:35:00+05:30  
**Target Files Inspected:**
- `data/processed/markdown_optimization_cleaned.csv` (Canonical dataset)
- `data/processed/run_eda.py`
- `data/processed/test_eda.py`
- `data/reports/eda_summary.json`
- `data/reports/eda_report.md`
- `data/reports/eda_findings.csv`
- `data/reports/figures/*.png`

---

## 1. Executive Audit Decision

### **DECISION: EDA ACCEPTED WITH CAVEATS**

**Audit Verdict:**
- The canonical cleaned dataset remains **100% intact and unchanged** (149,270 rows, 63 columns, matching SHA-256 integrity).
- Core aggregates (Revenue, Units Sold, Returns, Gross Margin, Stockout Rate, Latent Demand, and Unmet Demand) were independently verified and matched to exact decimal precision.
- Two descriptive discrepancies identified during deep verification:
  1. **Discount Band Table in Markdown Report**: The text table in `eda_report.md` had legacy placeholder bin counts that did not match the correctly computed values in `eda_summary.json` (e.g. 79,010 full-price rows vs legacy 85,910). This has been corrected and synchronized.
  2. **In-Stock Promotional Lift**: Raw promotional lift is **+13.43%**, while on in-stock days (`stockout_flag == 0`), promotional lift is **+27.76%** (with a +13.47 percentage point higher average discount). The in-stock lift was previously noted as +18.4% in the text report; it is now updated to the exact verified +27.76%.
- All 4 visual charts were verified to derive directly from the current canonical data.
- **Model Training Guardrail**: Modeling remains blocked until causal feature lags, censoring loss masks, and chronological splits are compiled.

---

## 2. Independent Numerical Recalculation & Reconciliation

| Metric | Reported Value | Independently Recalculated | Discrepancy | Severity | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gross Realized Revenue** | ₹223,842,750.00 | ₹223,842,750.00 | ₹0.00 | None | **PASS** |
| **Total Units Fulfilled** | 114,668 units | 114,668 units | 0 units | None | **PASS** |
| **Total Returns Units** | 9,666 units | 9,666 units | 0 units | None | **PASS** |
| **Total Cost of Goods (COGS)** | ₹110,216,238.00 | ₹110,216,238.00 | ₹0.00 | None | **PASS** |
| **Overall Gross Margin %** | 50.76% | 50.7618% | 0.0018pp (rounding) | Minor | **PASS** |
| **Stockout Occurrences** | 18,696 events | 18,696 events | 0 events | None | **PASS** |
| **Stockout Rate Denominator** | 149,270 store-days | 149,270 store-days | 0 | None | **PASS** |
| **Stockout Rate %** | 12.52% | 12.5250% | 0.005pp (rounding) | Minor | **PASS** |
| **Synthetic Latent Demand** | 157,422 units | 157,422 units | 0 units | None | **PASS** |
| **Unmet Demand Gap** | 42,754 units | 42,754 units | 0 units | None | **PASS** |
| **Unmet Demand Rate %** | 27.16% | 27.1588% (42,754 / 157,422) | 0.0012pp (rounding) | Minor | **PASS** |
| **Raw Promo Volume Lift** | +13.43% | +13.4312% (0.8463 vs 0.7461) | None | None | **PASS** |
| **In-Stock Promo Volume Lift** | +27.76% | +27.7640% (1.0537 vs 0.8247) | Prior report stated 18.4% | Minor (Fixed) | **PASS** |
| **Promo Discount Depth Difference** | +13.47 pp | +13.4681 pp (23.46% vs 9.99%) | None | None | **PASS** |

---

## 3. Verified Discount Band Partitions

Exact recalculation of bins `[-1, 0, 10, 20, 30, 40, 50, 100]` across all 149,270 rows:

| Discount Band | Exact Record Count | Exact Units Sold | Exact Gross Revenue (₹) | Mean Daily Units | Stockout Rate % |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **0% (Full Price)** | 79,010 | 52,742 | ₹115,835,858 | 0.668 | 6.16% |
| **0.1 - 10%** | 7,690 | 7,148 | ₹17,112,112 | 0.930 | 4.77% |
| **10.1 - 20%** | 16,770 | 14,514 | ₹23,769,314 | 0.865 | 12.15% |
| **20.1 - 30%** | 14,667 | 9,156 | ₹17,909,229 | 0.624 | 19.41% |
| **30.1 - 40%** | 8,443 | 7,382 | ₹12,213,148 | 0.874 | 23.98% |
| **40.1 - 50%** | 22,690 | 23,726 | ₹37,003,089 | 1.046 | 28.88% |
| **> 50%** | 0 | 0 | ₹0 | N/A | N/A |
| **Total Check** | **149,270** | **114,668** | **₹223,842,750** | **0.768** | **12.52%** |

---

## 4. Remediation Actions Taken

1. **Synchronized `eda_report.md` Table 5**: Updated discount band record days, units, and stockout percentages to match the exact mathematical partitions above.
2. **Synchronized In-Stock Promotional Lift in Reports**: Updated text and `eda_findings.csv` to state the exact measured **+27.76% in-stock lift** and **+13.47pp discount difference**.
3. **Hardened Test Suite (`test_eda.py`)**: Expanded unit tests to assert exact mathematical values for in-stock promotional lift, discount depth differences, exact category margin bounds, and discount band partitions rather than broad file-existence boundaries.

---

## 5. Cleaned Dataset Preservation Check
- Canonical CSV path: `data/processed/markdown_optimization_cleaned.csv`
- Total Rows: **149,270** (Exact match)
- Total Columns: **63** (Exact match)
- Duplicate Keys: **0**
- Nulls: **0**
- File Size: **54,451,879 bytes (51.93 MB)** (Preserved intact)
