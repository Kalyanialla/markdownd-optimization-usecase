"""
Production Data Cleaning Pipeline for UC-RT-03: Markdown Optimization.

Author: Senior Data Engineer & ML Data Quality Reviewer
Purpose:
- Combines 10 operational CSVs + 1 ground truth evaluation benchmark into ONE canonical cleaned CSV.
- Enforces strict grain: (date, store_id, sku_id) across active assortment/lifecycle.
- Audits inventory movement directions, completed movement semantics, and adjustments.
- Resolves multi-scope promotion campaigns deterministically (e.g. CATEGORY/STORE overlaps).
- Resolves pricing policy scope precedence (SKU > CATEGORY > STORE > CHAIN).
- Segregates benchmark ground-truth from operational predictor features.
- Zero raw CSV modification.
"""

import os
import sys
import json
import logging
import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("CleaningPipeline")

WORKSPACE = os.path.abspath(r"c:\MarkDown Optimization Usecase")
DATA_DIR = os.path.join(WORKSPACE, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
GT_DIR = os.path.join(DATA_DIR, "ground_truth")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

OUTPUT_CSV_PATH = os.path.join(PROCESSED_DIR, "markdown_optimization_cleaned.csv")
CLEANING_REPORT_PATH = os.path.join(REPORTS_DIR, "cleaning_and_validation_report.json")
CLEANING_LOG_PATH = os.path.join(REPORTS_DIR, "cleaning_log.jsonl")


def run_cleaning_pipeline():
    logger.info("=== STEP 1: LOADING RAW DATASETS ===")
    products = pd.read_csv(os.path.join(RAW_DIR, "products.csv"))
    stores = pd.read_csv(os.path.join(RAW_DIR, "stores.csv"))
    calendar = pd.read_csv(os.path.join(RAW_DIR, "calendar.csv"))
    pricing_policies = pd.read_csv(os.path.join(RAW_DIR, "pricing_policies.csv"))
    promotions = pd.read_csv(os.path.join(RAW_DIR, "promotions.csv"))
    external_signals = pd.read_csv(os.path.join(RAW_DIR, "external_signals.csv"))
    inventory_movements = pd.read_csv(os.path.join(RAW_DIR, "inventory_movements.csv"))
    inventory_snapshots = pd.read_csv(os.path.join(RAW_DIR, "inventory_snapshots.csv"))
    sales_history = pd.read_csv(os.path.join(RAW_DIR, "sales_history.csv"))
    simulated_demand = pd.read_csv(os.path.join(GT_DIR, "simulated_demand.csv"))

    logger.info(f"Loaded: Sales={len(sales_history):,}, Snapshots={len(inventory_snapshots):,}, Products={len(products):,}, Stores={len(stores):,}")

    # STEP 2: VERIFY GRAIN & ARITHMETIC ON BASE SALES
    logger.info("=== STEP 2: VERIFYING SALES GRAIN & ARITHMETIC ===")
    base_keys = ["date", "store_id", "sku_id"]
    if sales_history.duplicated(subset=base_keys).sum() > 0:
        raise ValueError("Duplicate business keys detected in sales_history.csv!")

    expected_disc = ((sales_history["regular_price"] - sales_history["selling_price"]) / sales_history["regular_price"] * 100).round(2)
    disc_diff = (sales_history["discount_pct"].round(2) - expected_disc).abs()
    disc_mismatches = int((disc_diff > 0.05).sum())

    expected_rev = (sales_history["units_sold"] * sales_history["selling_price"]).round(2)
    rev_diff = (sales_history["revenue"].round(2) - expected_rev).abs()
    rev_mismatches = int((rev_diff > 0.05).sum())

    if disc_mismatches > 0 or rev_mismatches > 0:
        raise ValueError(f"Arithmetic validation failed: disc_mismatches={disc_mismatches}, rev_mismatches={rev_mismatches}")

    # STEP 3: PRECISE INVENTORY MOVEMENT AGGREGATION
    # Strictly handle movement_type, movement_status, store direction, and adjustments
    logger.info("=== STEP 3: AGGREGATING INVENTORY MOVEMENTS WITH DIRECTIONAL SEMANTICS ===")
    completed_mov = inventory_movements[inventory_movements["movement_status"] == "COMPLETED"].copy()

    # Inbound to destination_store:
    # RECEIPT, TRANSFER_IN, RETURN_RESTOCK, OPENING_STOCK, ADJUSTMENT_IN
    inbound_types = ["RECEIPT", "TRANSFER_IN", "RETURN_RESTOCK", "OPENING_STOCK", "ADJUSTMENT_IN"]
    inbound_recs = completed_mov[completed_mov["movement_type"].isin(inbound_types)]
    mov_in = inbound_recs.groupby(["movement_date", "destination_store_id", "sku_id"])["quantity_units"].sum().reset_index()
    mov_in.columns = ["date", "store_id", "sku_id", "intraday_units_received"]

    # Outbound from source_store:
    # TRANSFER_OUT, ADJUSTMENT_OUT
    outbound_types = ["TRANSFER_OUT", "ADJUSTMENT_OUT"]
    outbound_recs = completed_mov[completed_mov["movement_type"].isin(outbound_types)]
    mov_out = outbound_recs.groupby(["movement_date", "source_store_id", "sku_id"])["quantity_units"].sum().reset_index()
    mov_out.columns = ["date", "store_id", "sku_id", "intraday_units_dispatched"]

    # Specifically track physical shrinkage / damages for loss prevention context
    shrinkage_recs = completed_mov[completed_mov["adjustment_reason"] == "SHRINKAGE"]
    shrinkage_agg = shrinkage_recs.groupby(["movement_date", "source_store_id", "sku_id"])["quantity_units"].sum().reset_index()
    shrinkage_agg.columns = ["date", "store_id", "sku_id", "intraday_shrinkage_units"]

    # STEP 4: PROMOTIONS SCOPE EXPANSION & DETERMINISTIC OVERLAP RESOLUTION
    logger.info("=== STEP 4: RESOLVING PROMOTION SCOPE PRECEDENCE ===")
    active_promos = promotions[promotions["promotion_status"].isin(["COMPLETED", "ACTIVE"])].copy()

    # Priority ranking for scope resolution: STORE > CATEGORY > REGION > CHAIN
    scope_rank = {"STORE": 4, "CATEGORY": 3, "REGION": 2, "CHAIN": 1}
    active_promos["scope_priority"] = active_promos["scope_type"].map(scope_rank)

    promo_expanded_rows = []
    for idx, p in active_promos.iterrows():
        p_dates = pd.date_range(p["start_date"], p["end_date"]).strftime("%Y-%m-%d")
        
        # Determine applicable stores
        if p["scope_type"] == "CHAIN":
            p_stores = stores["store_id"].unique()
        elif p["scope_type"] == "REGION":
            p_stores = stores[stores["region"] == p["scope_id"]]["store_id"].unique()
        elif p["scope_type"] == "STORE":
            p_stores = [p["store_id"]]
        else: # CATEGORY
            p_stores = stores["store_id"].unique()

        # Determine applicable SKUs
        if p["scope_type"] == "CATEGORY":
            p_skus = products[products["category"] == p["scope_id"]]["sku_id"].unique()
        else:
            p_skus = products["sku_id"].unique()

        for d in p_dates:
            for st in p_stores:
                for sk in p_skus:
                    promo_expanded_rows.append({
                        "date": d,
                        "store_id": st,
                        "sku_id": sk,
                        "promotion_id": p["promotion_id"],
                        "promotion_type": p["promotion_type"],
                        "promotion_discount_pct": p["promotion_discount_pct"],
                        "campaign_cost": p["campaign_cost"],
                        "scope_priority": p["scope_priority"]
                    })

    promo_exp_df = pd.DataFrame(promo_expanded_rows)
    # Sort deterministically by scope_priority descending, then promotion_discount_pct descending
    promo_exp_df = promo_exp_df.sort_values(
        by=["date", "store_id", "sku_id", "scope_priority", "promotion_discount_pct"],
        ascending=[True, True, True, False, False]
    )
    # Deduplicate deterministically to highest priority promotion
    promo_unique = promo_exp_df.drop_duplicates(subset=["date", "store_id", "sku_id"], keep="first").copy()
    logger.info(f"Expanded promotions resolved to {len(promo_unique):,} unique store-SKU-date promotion assignments")

    # STEP 5: PRICING POLICIES RESOLUTION
    logger.info("=== STEP 5: RESOLVING PRICING POLICIES PRECEDENCE ===")
    active_policies = pricing_policies[pricing_policies["policy_status"] == "ACTIVE"].copy()
    pol_scope_rank = {"SKU": 4, "CATEGORY": 3, "STORE": 2, "CHAIN": 1}
    active_policies["policy_priority"] = active_policies["scope_type"].map(pol_scope_rank)

    # Compile policy rules for each SKU
    sku_policies = []
    for idx, prod in products.iterrows():
        sku = prod["sku_id"]
        cat = prod["category"]
        # Match SKU-specific first, then Category, then Chain
        match_sku = active_policies[(active_policies["scope_type"] == "SKU") & (active_policies["scope_id"] == sku)]
        match_cat = active_policies[(active_policies["scope_type"] == "CATEGORY") & (active_policies["scope_id"] == cat)]
        match_chain = active_policies[active_policies["scope_type"] == "CHAIN"]
        
        chosen = None
        if not match_sku.empty:
            chosen = match_sku.sort_values(by="policy_version", ascending=False).iloc[0]
        elif not match_cat.empty:
            chosen = match_cat.sort_values(by="policy_version", ascending=False).iloc[0]
        elif not match_chain.empty:
            chosen = match_chain.sort_values(by="policy_version", ascending=False).iloc[0]
            
        sku_policies.append({
            "sku_id": sku,
            "policy_id": chosen["policy_id"] if chosen is not None else "POL-DEFAULT",
            "policy_minimum_margin_pct": chosen["minimum_margin_pct"] if chosen is not None else 0.20,
            "policy_minimum_price": chosen["minimum_price"] if chosen is not None else prod["minimum_price"],
            "policy_maximum_discount_pct": chosen["maximum_discount_pct"] if chosen is not None else prod["maximum_discount_pct"],
            "policy_min_days_between_changes": chosen["minimum_days_between_changes"] if chosen is not None else 7
        })
    sku_policies_df = pd.DataFrame(sku_policies)

    # STEP 6: EXPLICIT MERGES AND CARDINALITY VERIFICATION
    logger.info("=== STEP 6: EXECUTING CANONICAL MERGES ===")
    
    # 6.1 Merge snapshots (1:1)
    df = pd.merge(
        sales_history,
        inventory_snapshots,
        left_on=["date", "sku_id", "store_id"],
        right_on=["snapshot_date", "sku_id", "store_id"],
        how="inner",
        validate="one_to_one",
        suffixes=("", "_snap")
    )
    if len(df) != len(sales_history):
        raise ValueError(f"Snapshot join altered row count! Expected {len(sales_history)}, got {len(df)}")

    # 6.2 Merge products & stores (many-to-1)
    df = pd.merge(df, products, on="sku_id", how="inner", validate="many_to_one", suffixes=("", "_prod"))
    df = pd.merge(df, stores, on="store_id", how="inner", validate="many_to_one", suffixes=("", "_store"))

    # 6.3 Merge calendar (many-to-1)
    df = pd.merge(df, calendar, on="date", how="inner", validate="many_to_one", suffixes=("", "_cal"))

    # 6.4 Merge external signals (many-to-1)
    ext_cols = [
        "target_date", "store_id", "temperature_forecast", "rainfall_forecast",
        "competitor_price", "local_event_flag"
    ]
    df = pd.merge(
        df,
        external_signals[ext_cols],
        left_on=["date", "store_id"],
        right_on=["target_date", "store_id"],
        how="left",
        validate="many_to_one"
    )

    # 6.5 Merge directional movement aggregations
    df = pd.merge(df, mov_in, on=["date", "store_id", "sku_id"], how="left")
    df["intraday_units_received"] = df["intraday_units_received"].fillna(0).astype(int)

    df = pd.merge(df, mov_out, on=["date", "store_id", "sku_id"], how="left")
    df["intraday_units_dispatched"] = df["intraday_units_dispatched"].fillna(0).astype(int)

    df = pd.merge(df, shrinkage_agg, on=["date", "store_id", "sku_id"], how="left")
    df["intraday_shrinkage_units"] = df["intraday_shrinkage_units"].fillna(0).astype(int)

    # 6.6 Merge resolved promotions
    promo_join_cols = ["date", "store_id", "sku_id", "promotion_id", "promotion_type", "promotion_discount_pct"]
    df = pd.merge(df, promo_unique[promo_join_cols], on=["date", "store_id", "sku_id"], how="left")
    df["promotion_id"] = df["promotion_id"].fillna("NONE")
    df["promotion_type"] = df["promotion_type"].fillna("NONE")
    df["promotion_discount_pct"] = df["promotion_discount_pct"].fillna(0.0)

    # 6.7 Merge pricing policies
    df = pd.merge(df, sku_policies_df, on="sku_id", how="left", validate="many_to_one")

    # 6.8 Merge benchmark ground truth (1:1)
    gt_cols = ["date", "sku_id", "store_id", "latent_demand_units", "demand_model_profile"]
    df = pd.merge(
        df,
        simulated_demand[gt_cols],
        on=["date", "sku_id", "store_id"],
        how="inner",
        validate="one_to_one"
    )

    # STEP 7: INVENTORY RECONCILIATION
    df["effective_available_units"] = df["opening_stock_units"] + df["intraday_units_received"]
    unexplained_oversells = int((df["units_sold"] > df["effective_available_units"]).sum())
    logger.info(f"Inventory reconciliation: unexplained oversells = {unexplained_oversells}")

    # STEP 8: STANDARDIZE COLUMN DEFINITIONS & SELECTION
    canonical_columns = [
        # --- CANONICAL GRAIN ---
        "date",
        "store_id",
        "sku_id",
        
        # --- PRODUCT DIMENSIONS ---
        "product_name",
        "style_id",
        "category",
        "subcategory",
        "brand",
        "size",
        "color",
        "season_id",
        "unit_cost",
        "regular_price",
        "minimum_price",
        "maximum_discount_pct",
        "product_status",
        
        # --- STORE DIMENSIONS ---
        "store_name",
        "region",
        "city",
        "store_type",
        "climate_zone",
        "store_capacity_units",
        
        # --- CALENDAR & ASSORTMENT LIFECYCLE ---
        "year",
        "month",
        "quarter",
        "week_of_year",
        "day_of_week",
        "is_weekend",
        "is_public_holiday",
        "holiday_name",
        "week_of_season",
        "days_to_season_end",
        "season_phase",
        
        # --- OPERATIONAL PRICING & PROMOTIONS (Known for Day T) ---
        "selling_price",
        "discount_pct",
        "promotion_flag",
        "promotion_id",
        "promotion_type",
        "promotion_discount_pct",
        "policy_id",
        "policy_minimum_margin_pct",
        "policy_minimum_price",
        "policy_maximum_discount_pct",
        "policy_min_days_between_changes",
        
        # --- EXTERNAL SIGNALS (Observed T-1 for Day T) ---
        "temperature_forecast",
        "rainfall_forecast",
        "competitor_price",
        "local_event_flag",
        
        # --- INVENTORY STATE & INTRADAY MOVEMENTS ---
        "opening_stock_units",
        "intraday_units_received",
        "intraday_units_dispatched",
        "intraday_shrinkage_units",
        "effective_available_units",
        "on_hand_units",
        "available_units",
        "inbound_units",
        "incoming_eta_days",
        
        # --- REALIZED TRANSACTION OUTCOMES (Target / Target Censoring) ---
        "units_sold",
        "returns_units",
        "revenue",
        "stockout_flag",
        
        # --- GROUND TRUTH BENCHMARK (STRICTLY PROHIBITED AS MODEL INPUT) ---
        "benchmark_latent_demand_units",
        "benchmark_demand_model_profile"
    ]

    df = df.rename(columns={
        "latent_demand_units": "benchmark_latent_demand_units",
        "demand_model_profile": "benchmark_demand_model_profile"
    })

    canonical_df = df[canonical_columns].copy()
    canonical_df = canonical_df.sort_values(by=["date", "store_id", "sku_id"]).reset_index(drop=True)

    # STEP 9: ASSERTIONS & VALIDATION
    assert len(canonical_df) == 149270, f"Expected 149,270 rows, got {len(canonical_df)}"
    assert canonical_df.duplicated(subset=base_keys).sum() == 0, "Duplicate business keys detected!"
    assert canonical_df.isnull().sum().sum() == 0, f"Null values detected in canonical CSV:\n{canonical_df.isnull().sum()[canonical_df.isnull().sum() > 0]}"

    # STEP 10: SAVE CANONICAL CLEANED CSV
    logger.info(f"Writing canonical CSV to {OUTPUT_CSV_PATH}...")
    canonical_df.to_csv(OUTPUT_CSV_PATH, index=False)
    file_size_mb = os.path.getsize(OUTPUT_CSV_PATH) / (1024 * 1024)
    logger.info(f"Successfully generated {OUTPUT_CSV_PATH} ({file_size_mb:.2f} MB, {len(canonical_df):,} rows, {len(canonical_df.columns)} columns)")

    # STEP 11: GENERATE REPORT
    report = {
        "pipeline_status": "SUCCESS",
        "canonical_csv_path": os.path.relpath(OUTPUT_CSV_PATH, WORKSPACE),
        "total_rows": len(canonical_df),
        "total_columns": len(canonical_df.columns),
        "file_size_mb": round(file_size_mb, 2),
        "canonical_grain": base_keys,
        "exact_duplicates": int(canonical_df.duplicated().sum()),
        "key_duplicates": int(canonical_df.duplicated(subset=base_keys).sum()),
        "total_nulls": int(canonical_df.isnull().sum().sum()),
        "stockout_observations": int(canonical_df["stockout_flag"].sum()),
        "stockout_pct": round(float(canonical_df["stockout_flag"].mean() * 100), 2),
        "unexplained_oversells": unexplained_oversells,
        "pricing_arithmetic_discrepancies": disc_mismatches,
        "revenue_arithmetic_discrepancies": rev_mismatches,
        "included_columns": canonical_columns,
        "timing_and_leakage_declarations": {
            "prohibited_inference_features": [
                "benchmark_latent_demand_units",
                "benchmark_demand_model_profile",
                "units_sold",
                "returns_units",
                "revenue",
                "stockout_flag",
                "on_hand_units",
                "available_units",
                "intraday_units_received",
                "intraday_units_dispatched",
                "intraday_shrinkage_units",
                "effective_available_units"
            ],
            "approved_as_of_t_minus_1_features": [
                "date", "store_id", "sku_id", "product_name", "style_id", "category",
                "subcategory", "brand", "size", "color", "season_id", "unit_cost",
                "regular_price", "minimum_price", "maximum_discount_pct", "product_status",
                "store_name", "region", "city", "store_type", "climate_zone", "store_capacity_units",
                "year", "month", "quarter", "week_of_year", "day_of_week", "is_weekend",
                "is_public_holiday", "holiday_name", "week_of_season", "days_to_season_end", "season_phase",
                "selling_price", "discount_pct", "promotion_flag", "promotion_id", "promotion_type",
                "promotion_discount_pct", "policy_id", "policy_minimum_margin_pct", "policy_minimum_price",
                "policy_maximum_discount_pct", "policy_min_days_between_changes",
                "temperature_forecast", "rainfall_forecast", "competitor_price", "local_event_flag",
                "opening_stock_units", "inbound_units", "incoming_eta_days"
            ]
        }
    }

    with open(CLEANING_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Cleaning report updated at {CLEANING_REPORT_PATH}")
    return report

if __name__ == "__main__":
    run_cleaning_pipeline()
