"""
Tests for Leakage Prevention and Store-Opening Cutoff Guarantees.
UC-RT-03 Markdown Optimization
"""

import os
import json
import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "data/reports/feature_schema.json")
TRAIN_PATH = os.path.join(REPO_ROOT, "data/processed/train.csv")

def test_no_forbidden_columns_in_inference_allowlist():
    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    approved = set(schema["approved_feature_columns"])
    forbidden = set(schema["prohibited_leakage_features"])
    
    intersection = approved.intersection(forbidden)
    assert len(intersection) == 0, f"Critical leakage! Prohibited columns present in approved list: {intersection}"

def test_strictly_store_opening_availability():
    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    approved = set(schema["approved_feature_columns"])
    targets = set(schema["target_columns"])
    forbidden = set(schema["prohibited_leakage_features"])
    
    # Critical targets and leaking fields that must never be in approved inference features
    critical_exclusions = [
        "target_units_sold",
        "target_stockout_mask",
        "eval_benchmark_latent_demand",
        "revenue",
        "returns_units",
        "stockout_flag",
        "on_hand_units",
        "available_units",
        "effective_available_units"
    ]
    for col in critical_exclusions:
        assert col not in approved, f"CRITICAL LEAKAGE: {col} is in approved_feature_columns!"
        assert (col in targets) or (col in forbidden), f"{col} must be classified as target or prohibited!"
