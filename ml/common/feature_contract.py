"""
Data contract and feature validation module for ML pipelines.
UC-RT-03 Markdown Optimization
"""

import json
import os
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
WORKSPACE = REPO_ROOT
SCHEMA_PATH = os.path.join(WORKSPACE, "data", "reports", "feature_schema.json")
MANIFEST_PATH = os.path.join(WORKSPACE, "data", "reports", "split_manifest.json")

def load_feature_schema():
    with open(SCHEMA_PATH, "r") as f:
        return json.load(f)

def load_split_manifest():
    with open(MANIFEST_PATH, "r") as f:
        return json.load(f)

def validate_features(df: pd.DataFrame, is_inference: bool = False):
    schema = load_feature_schema()
    approved_cols = schema["approved_feature_columns"]
    prohibited_cols = schema["prohibited_leakage_features"]
    
    # 1. Check for prohibited columns
    leaked = [col for col in prohibited_cols if col in df.columns]
    if is_inference and leaked:
        raise ValueError(f"CRITICAL LEAKAGE DETECTED! Prohibited columns in inference input: {leaked}")
        
    # 2. Check for missing approved features
    missing = [col for col in approved_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required approved features: {missing}")
        
    return True

def get_feature_lists():
    schema = load_feature_schema()
    approved_cols = schema["approved_feature_columns"]
    
    categorical_cols = [
        "store_id", "sku_id", "style_id", "category", "subcategory",
        "brand", "size", "color", "season_id", "product_status",
        "store_name", "region", "city", "store_type", "climate_zone",
        "day_of_week", "season_phase", "promotion_id", "promotion_type", "policy_id"
    ]
    numeric_cols = [c for c in approved_cols if c not in categorical_cols and c != "date"]
    
    return {
        "all_approved": approved_cols,
        "categorical": categorical_cols,
        "numeric": numeric_cols,
        "date_col": "date"
    }

# Convenient constants and functions for pipelines
schema_data = load_feature_schema()
STORE_OPENING_FEATURES_66 = [c for c in schema_data["approved_feature_columns"] if c != "date"]
CATEGORICAL_FEATURES = [
    "store_id", "sku_id", "style_id", "category", "subcategory",
    "brand", "size", "color", "season_id", "product_status",
    "store_name", "region", "city", "store_type", "climate_zone",
    "day_of_week", "season_phase", "promotion_id", "promotion_type", "policy_id"
]
NUMERICAL_FEATURES = [c for c in STORE_OPENING_FEATURES_66 if c not in CATEGORICAL_FEATURES]
FORBIDDEN_LEAKAGE_COLUMNS = schema_data["prohibited_leakage_features"]

def check_no_forbidden_columns(cols):
    leaked = [c for c in cols if c in FORBIDDEN_LEAKAGE_COLUMNS]
    if leaked:
        raise ValueError(f"Forbidden leakage columns found: {leaked}")
    return True

def validate_feature_availability(cols):
    missing = [c for c in STORE_OPENING_FEATURES_66 if c not in cols]
    if missing:
        raise ValueError(f"Missing required features from allowlist: {missing}")
    return True

