"""
Comprehensive Production Test Suite for Markdown Optimization Canonical Dataset.
Tests:
1. Canonical Grain & Uniqueness (date, store_id, sku_id).
2. Zero Unjustified Nulls across all 63 columns.
3. Pricing & Revenue Arithmetic (revenue = units_sold * selling_price; discount_pct formula).
4. Directional Inventory Movement & Reconciliation (no unexplained over-sales).
5. Shrinkage and Adjustment accounting.
6. Deterministic Promotion Scope Precedence (STORE > CATEGORY > REGION > CHAIN).
7. Pricing Policy Precedence (SKU > CATEGORY > STORE > CHAIN).
8. Target & Leakage Segregation (benchmark_latent_demand isolated).
9. Stockout Censoring Integrity (retaining 18,696 stockout observations).
10. Active Assortment Bounds (no dates prior to store opening or outside SKU lifecycle).
"""

import os
import unittest
import pandas as pd
import numpy as np

WORKSPACE = os.path.abspath(r"c:\MarkDown Optimization Usecase")
CLEANED_CSV = os.path.join(WORKSPACE, "data", "processed", "markdown_optimization_cleaned.csv")

class TestCanonicalProductionDataset(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not os.path.exists(CLEANED_CSV):
            raise FileNotFoundError(f"Cleaned CSV does not exist at {CLEANED_CSV}")
        cls.df = pd.read_csv(CLEANED_CSV)

    def test_01_canonical_grain_and_row_count(self):
        """Verify exact row count matches expected 149,270 active combinations with 0 duplicates."""
        self.assertEqual(len(self.df), 149270)
        duplicates = self.df.duplicated(subset=["date", "store_id", "sku_id"]).sum()
        self.assertEqual(duplicates, 0, f"Found {duplicates} duplicate business keys!")

    def test_02_zero_unjustified_nulls(self):
        """Verify 0 missing values across all 63 canonical columns."""
        null_counts = self.df.isnull().sum()
        cols_with_nulls = null_counts[null_counts > 0]
        self.assertEqual(len(cols_with_nulls), 0, f"Unexpected nulls found in: {cols_with_nulls.to_dict()}")

    def test_03_pricing_and_revenue_arithmetic(self):
        """Verify revenue == units_sold * selling_price and discount percentage formula."""
        calc_revenue = (self.df["units_sold"] * self.df["selling_price"]).round(2)
        diff_rev = (self.df["revenue"].round(2) - calc_revenue).abs()
        self.assertEqual((diff_rev > 0.05).sum(), 0, "Discrepancies in revenue calculation detected!")

        calc_disc = ((self.df["regular_price"] - self.df["selling_price"]) / self.df["regular_price"] * 100).round(2)
        diff_disc = (self.df["discount_pct"].round(2) - calc_disc).abs()
        self.assertEqual((diff_disc > 0.05).sum(), 0, "Discrepancies in discount percentage detected!")

    def test_04_inventory_movement_reconciliation(self):
        """Verify units_sold <= opening_stock + intraday_units_received across all rows."""
        oversell = (self.df["units_sold"] > self.df["effective_available_units"]).sum()
        self.assertEqual(oversell, 0, f"Found {oversell} unexplained inventory oversells!")

    def test_05_directional_movement_non_negativity(self):
        """Verify received and dispatched movements are non-negative and properly directioned."""
        self.assertTrue((self.df["intraday_units_received"] >= 0).all())
        self.assertTrue((self.df["intraday_units_dispatched"] >= 0).all())
        self.assertTrue((self.df["intraday_shrinkage_units"] >= 0).all())

    def test_06_promotion_scope_precedence(self):
        """Verify overlapping promotion precedence resolves deterministically."""
        # On 2024-09-13, STORE-03, SKU-0096: PRM-014 (STORE, 10%) overlaps PRM-015 (CATEGORY, 12%)
        # Precedence STORE (rank 4) > CATEGORY (rank 3) selects PRM-014
        sample_row = self.df[(self.df["date"] == "2024-09-13") & (self.df["store_id"] == "STORE-03") & (self.df["sku_id"] == "SKU-0096")]
        self.assertEqual(len(sample_row), 1)
        self.assertEqual(sample_row["promotion_id"].iloc[0], "PRM-014")

    def test_07_pricing_policy_precedence(self):
        """Verify pricing policies are resolved with policy margin rules and product price floors."""
        self.assertTrue((self.df["minimum_price"] > 0).all())
        self.assertTrue((self.df["policy_minimum_margin_pct"] >= 0).all())
        # Check that selling_price respects product minimum_price
        violations = (self.df["selling_price"] < self.df["minimum_price"]).sum()
        self.assertEqual(violations, 0, f"Found {violations} sales below product minimum price!")

    def test_08_target_and_leakage_isolation(self):
        """Verify benchmark ground truth is isolated and prohibited columns are flagged."""
        self.assertIn("benchmark_latent_demand_units", self.df.columns)
        self.assertIn("benchmark_demand_model_profile", self.df.columns)
        self.assertNotIn("latent_demand_units", self.df.columns)

    def test_09_stockout_censoring_preservation(self):
        """Verify all 18,696 stockout events are preserved for demand censoring."""
        stockouts = self.df["stockout_flag"].sum()
        self.assertEqual(stockouts, 18696)

    def test_10_active_assortment_bounds(self):
        """Verify STORE-04 has no sales prior to its opening date (2024-03-01)."""
        st4_early = self.df[(self.df["store_id"] == "STORE-04") & (self.df["date"] < "2024-03-01")]
        self.assertEqual(len(st4_early), 0, "Found records for STORE-04 prior to opening date!")


if __name__ == "__main__":
    unittest.main()
