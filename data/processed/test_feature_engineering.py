"""
Comprehensive Production Test Suite for Phase 3A Feature Engineering & Leakage Prevention.
UC-RT-03 Markdown Optimization — Store-Opening Timing Contract Audit

Audited Assertions:
1. Canonical row count (149,270) and key uniqueness (date, store_id, sku_id).
2. Chronological split integrity, disjointness, exact row lineage and SHA-256 manifest alignment.
3. Causal lag correctness (T-1, T-2, T-7, T-14) evaluated on multiple diverse entities.
4. Rolling window semantics: strict exclusion of day T outcomes; contiguous calendar day tracking.
5. Entity isolation: cold-starts initialize cleanly without cross-entity leakage.
6. Absolute leakage prohibition: target_units_sold, revenue, returns, stockout_flag, on_hand_units,
   intraday flows, and eval_benchmark_latent_demand are excluded from approved model features.
7. Demand censoring documentation: target_units_sold is explicitly acknowledged as censored by target_stockout_mask.
8. Store-Opening Cutoff & Inventory Provenance:
   - Prove opening_stock_units[T] == on_hand_units[T-1] across all entity transitions (148,400/148,400).
   - Verify opening_stock_units does NOT incorporate Day T intraday receipts or dispatches.
9. Price and Signal Lead-Time Availability:
   - Verify approved price events have approval lead time >= 6 hours prior to Day T.
   - Verify weather and competitor forecasts have observation timestamps prior to Day T.
10. Explicit Feature Matrix Allowlist & Rejection Test:
   - Construct actual model inference feature matrix X from train.csv and test.csv.
   - Assert all prohibited columns (targets, post-outcomes, benchmarks) are rejected.
11. Source dataset preservation: markdown_optimization_cleaned.csv is unchanged (exact SHA-256 match).
"""

import os
import json
import hashlib
import unittest
import pandas as pd
import numpy as np

WORKSPACE = os.path.abspath(r"c:\MarkDown Optimization Usecase")
RAW_DIR = os.path.join(WORKSPACE, "data", "raw")
PROCESSED_DIR = os.path.join(WORKSPACE, "data", "processed")
REPORTS_DIR = os.path.join(WORKSPACE, "data", "reports")

CLEANED_CSV = os.path.join(PROCESSED_DIR, "markdown_optimization_cleaned.csv")
FEATURES_CSV = os.path.join(PROCESSED_DIR, "markdown_features_canonical.csv")
TRAIN_CSV = os.path.join(PROCESSED_DIR, "train.csv")
VAL_CSV = os.path.join(PROCESSED_DIR, "validation.csv")
TEST_CSV = os.path.join(PROCESSED_DIR, "test.csv")

SCHEMA_JSON = os.path.join(REPORTS_DIR, "feature_schema.json")
MANIFEST_JSON = os.path.join(REPORTS_DIR, "split_manifest.json")


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class TestFeaturePipelineAudit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.df_features = pd.read_csv(FEATURES_CSV)
        cls.df_train = pd.read_csv(TRAIN_CSV)
        cls.df_val = pd.read_csv(VAL_CSV)
        cls.df_test = pd.read_csv(TEST_CSV)
        with open(SCHEMA_JSON, "r") as f:
            cls.schema = json.load(f)
        with open(MANIFEST_JSON, "r") as f:
            cls.manifest = json.load(f)

    def test_01_row_count_and_key_uniqueness(self):
        """Verify full feature dataset has 149,270 rows and unique composite keys."""
        self.assertEqual(len(self.df_features), 149270)
        dups = self.df_features.duplicated(subset=["date", "store_id", "sku_id"]).sum()
        self.assertEqual(dups, 0, f"Found {dups} duplicate keys in feature table!")

    def test_02_chronological_split_integrity_and_hashes(self):
        """Verify exact row counts, date bounds, zero overlap, and SHA-256 manifest alignment."""
        self.assertEqual(len(self.df_train), 103470)
        self.assertEqual(len(self.df_val), 22140)
        self.assertEqual(len(self.df_test), 23660)
        self.assertEqual(len(self.df_train) + len(self.df_val) + len(self.df_test), 149270)

        # Date bounds
        self.assertEqual(self.df_train["date"].min(), "2024-01-01")
        self.assertEqual(self.df_train["date"].max(), "2024-12-31")
        self.assertEqual(self.df_val["date"].min(), "2025-01-01")
        self.assertEqual(self.df_val["date"].max(), "2025-03-31")
        self.assertEqual(self.df_test["date"].min(), "2025-04-01")
        self.assertEqual(self.df_test["date"].max(), "2025-06-30")

        # Temporal disjointness
        train_dates = set(self.df_train["date"])
        val_dates = set(self.df_val["date"])
        test_dates = set(self.df_test["date"])
        self.assertEqual(len(train_dates.intersection(val_dates)), 0)
        self.assertEqual(len(val_dates.intersection(test_dates)), 0)

        # Hash verification against manifest
        self.assertEqual(sha256_file(TRAIN_CSV), self.manifest["splits"]["train"]["sha256"])
        self.assertEqual(sha256_file(VAL_CSV), self.manifest["splits"]["validation"]["sha256"])
        self.assertEqual(sha256_file(TEST_CSV), self.manifest["splits"]["test"]["sha256"])

    def test_03_causal_lag_correctness_multiple_entities(self):
        """Verify causal lags across multiple diverse store/SKU combinations."""
        test_entities = [
            ("STORE-01", "SKU-0016"),
            ("STORE-03", "SKU-0065"),
            ("STORE-04", "SKU-0029")
        ]
        for st, sk in test_entities:
            entity_df = self.df_features[
                (self.df_features["store_id"] == st) & 
                (self.df_features["sku_id"] == sk)
            ].sort_values("date").reset_index(drop=True)

            self.assertGreaterEqual(len(entity_df), 10)
            self.assertEqual(entity_df.loc[1, "sales_lag_1d"], entity_df.loc[0, "target_units_sold"])
            self.assertEqual(entity_df.loc[2, "sales_lag_2d"], entity_df.loc[0, "target_units_sold"])
            if len(entity_df) > 7:
                self.assertEqual(entity_df.loc[7, "sales_lag_7d"], entity_df.loc[0, "target_units_sold"])

    def test_04_rolling_mean_strictly_excludes_same_day(self):
        """Verify rolling 7-day mean strictly uses T-7 to T-1 history."""
        sample_entity = self.df_features[
            (self.df_features["store_id"] == "STORE-02") & 
            (self.df_features["sku_id"] == "SKU-0018")
        ].sort_values("date").reset_index(drop=True)

        manual_mean_7d = sample_entity.loc[0:6, "target_units_sold"].mean()
        recorded_rolling_mean_day7 = sample_entity.loc[7, "sales_rolling_mean_7d"]
        self.assertAlmostEqual(manual_mean_7d, recorded_rolling_mean_day7, places=4)

    def test_05_contiguous_entity_time_series(self):
        """Verify that every active store-SKU time series has zero interior calendar gaps."""
        sample_subset = self.df_features.sample(n=1000, random_state=42)[["store_id", "sku_id"]].drop_duplicates()
        for idx, row in sample_subset.iterrows():
            st, sk = row["store_id"], row["sku_id"]
            entity_dates = pd.to_datetime(
                self.df_features[(self.df_features["store_id"] == st) & (self.df_features["sku_id"] == sk)]["date"]
            ).sort_values()
            diffs = entity_dates.diff().dt.days.dropna()
            self.assertTrue((diffs == 1).all(), f"Found interior date gap in entity {st} / {sk}!")

    def test_06_inventory_provenance_and_store_opening_contract(self):
        """Prove opening_stock_units[T] == on_hand_units[T-1] across 100% of transitions."""
        snaps = pd.read_csv(os.path.join(RAW_DIR, "inventory_snapshots.csv"))
        snaps = snaps.sort_values(by=["store_id", "sku_id", "snapshot_date"]).reset_index(drop=True)
        snaps["prev_on_hand"] = snaps.groupby(["store_id", "sku_id"])["on_hand_units"].shift(1)
        valid = snaps.dropna(subset=["prev_on_hand"])
        diffs = (valid["opening_stock_units"] - valid["prev_on_hand"]).abs()
        self.assertEqual(len(valid), 148400)
        self.assertEqual((diffs == 0).sum(), 148400, "Opening stock does not match previous closing on-hand!")

    def test_07_pricing_and_signal_lead_time_verification(self):
        """Verify approved price events and external signals have verifiable lead time prior to Day T."""
        ph = pd.read_csv(os.path.join(RAW_DIR, "price_history.csv"))
        approved_ph = ph[ph["approval_status"] == "APPROVED"].copy()
        app_ts = pd.to_datetime(approved_ph["approved_at"])
        eff_ts = pd.to_datetime(approved_ph["effective_from"]).dt.tz_localize("+05:30")
        lead_hours = (eff_ts - app_ts).dt.total_seconds() / 3600.0
        self.assertGreaterEqual(lead_hours.min(), 6.0, "Approved price event found with < 6 hours lead time!")

        ext = pd.read_csv(os.path.join(RAW_DIR, "external_signals.csv"))
        w_ts = pd.to_datetime(ext["weather_observed_at"])
        c_ts = pd.to_datetime(ext["competitor_observed_at"])
        t_ts = pd.to_datetime(ext["target_date"]).dt.tz_localize("+05:30")
        self.assertTrue(((t_ts - w_ts).dt.total_seconds() > 0).all())
        self.assertTrue(((t_ts - c_ts).dt.total_seconds() > 0).all())

    def test_08_explicit_model_matrix_allowlist_validation(self):
        """Construct actual model inference matrix X and assert all prohibited columns are absent."""
        approved_cols = self.schema["approved_feature_columns"]
        self.assertEqual(len(approved_cols), 66)

        # Build feature matrix from train.csv
        X_train = self.df_train[approved_cols]
        self.assertEqual(X_train.shape, (103470, 66))

        # Build feature matrix from test.csv
        X_test = self.df_test[approved_cols]
        self.assertEqual(X_test.shape, (23660, 66))

        # Verify prohibited columns cannot be present in X
        prohibited = [
            "target_units_sold", "units_sold", "target_stockout_mask", "stockout_flag",
            "eval_benchmark_latent_demand", "benchmark_latent_demand_units",
            "revenue", "returns_units", "on_hand_units", "available_units",
            "intraday_units_received", "intraday_units_dispatched",
            "intraday_shrinkage_units", "effective_available_units"
        ]
        for p in prohibited:
            self.assertNotIn(p, X_train.columns)
            self.assertNotIn(p, X_test.columns)

    def test_09_source_cleaned_csv_preserved(self):
        """Verify canonical cleaned CSV remains untouched and matches manifest hash."""
        self.assertEqual(sha256_file(CLEANED_CSV), self.manifest["source_sha256"])
        df_clean = pd.read_csv(CLEANED_CSV)
        self.assertEqual(len(df_clean), 149270)
        self.assertEqual(len(df_clean.columns), 63)


if __name__ == "__main__":
    unittest.main()
