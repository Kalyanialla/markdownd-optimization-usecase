# UC-RT-03: Markdown Optimization Data Preparation & Cleaning

## Overview
This repository manages data cleaning, validation, and preparation for retail markdown optimization and demand forecasting.

## Dataset Structure
- `data/raw/`: Original 10 immutable operational CSV files (stores, products, calendar, sales, inventory, pricing, promotions, signals).
- `data/ground_truth/`: `simulated_demand.csv` (latent customer demand for offline evaluation benchmark).
- `data/processed/`: Contains the single canonical cleaned operational dataset:
  - `markdown_optimization_cleaned.csv` (149,270 rows, 54 columns, 46.68 MB)
- `data/reports/`: Data quality, manifest, and cleaning validation reports.

## How to Rerun the Cleaning Pipeline
To regenerate the single canonical cleaned CSV deterministically:
```bash
python data/processed/run_cleaning.py
```

## Running Automated Validation Tests
To run the automated validation test suite:
```bash
python -m unittest data/processed/test_cleaning.py
```
Tests assert:
1. Exact row count (149,270) and key uniqueness `(date, store_id, sku_id)`.
2. Zero missing/null values across all 54 columns.
3. Accurate arithmetic for revenue and discounts.
4. Exact inventory reconciliation (sales <= opening stock + intraday receipts).
5. Ground truth benchmark column isolation.
