"""
Tests for Data Contract, Split Boundaries, and Feature Schema.
UC-RT-03 Markdown Optimization
"""

import os
import json
import pandas as pd
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCHEMA_PATH = os.path.join(REPO_ROOT, "data/reports/feature_schema.json")
MANIFEST_PATH = os.path.join(REPO_ROOT, "data/reports/split_manifest.json")
TRAIN_PATH = os.path.join(REPO_ROOT, "data/processed/train.csv")
VAL_PATH = os.path.join(REPO_ROOT, "data/processed/validation.csv")
TEST_PATH = os.path.join(REPO_ROOT, "data/processed/test.csv")

def test_feature_schema_and_manifest_exist():
    assert os.path.exists(SCHEMA_PATH), "feature_schema.json missing"
    assert os.path.exists(MANIFEST_PATH), "split_manifest.json missing"

def test_exact_split_row_counts_and_dates():
    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)
        
    train_meta = manifest["splits"]["train"]
    val_meta = manifest["splits"]["validation"]
    test_meta = manifest["splits"]["test"]
    
    assert train_meta["row_count"] == 103470
    assert val_meta["row_count"] == 22140
    assert test_meta["row_count"] == 23660
    
    assert train_meta["date_range"][0] == "2024-01-01"
    assert train_meta["date_range"][1] == "2024-12-31"
    assert val_meta["date_range"][0] == "2025-01-01"
    assert val_meta["date_range"][1] == "2025-03-31"
    assert test_meta["date_range"][0] == "2025-04-01"
    assert test_meta["date_range"][1] == "2025-06-30"

def test_approved_feature_allowlist_66():
    with open(SCHEMA_PATH, "r") as f:
        schema = json.load(f)
    approved = schema["approved_feature_columns"]
    # Total approved columns including date is 66
    assert len(approved) == 66, f"Expected 66 features, found {len(approved)}"
    assert schema["feature_count"] == 66
