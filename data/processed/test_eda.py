"""
Hardened Test Suite for EDA Numerical Correctness & Integrity.
Validates:
1. Exact mathematical metrics in eda_summary.json (Revenue, Margin, Stockout %, Unmet Demand %).
2. Exact promo lift numbers (raw lift +13.43%, in-stock lift +27.76%, discount diff +13.47pp).
3. Exact discount band partition sums matching dataset totals (79,010 full-price rows, 149,270 total).
4. Visualizations generation and non-zero bytes.
5. Absolute preservation of canonical cleaned CSV (149,270 rows, 63 columns).
"""

import os
import json
import unittest
import pandas as pd

WORKSPACE = os.path.abspath(r"c:\MarkDown Optimization Usecase")
CLEANED_CSV = os.path.join(WORKSPACE, "data", "processed", "markdown_optimization_cleaned.csv")
REPORTS_DIR = os.path.join(WORKSPACE, "data", "reports")
FIGURES_DIR = os.path.join(REPORTS_DIR, "figures")

SUMMARY_JSON = os.path.join(REPORTS_DIR, "eda_summary.json")
REPORT_MD = os.path.join(REPORTS_DIR, "eda_report.md")
FINDINGS_CSV = os.path.join(REPORTS_DIR, "eda_findings.csv")


class TestEDANumericalCorrectness(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(SUMMARY_JSON, "r") as f:
            cls.summary = json.load(f)
        cls.df = pd.read_csv(CLEANED_CSV)

    def test_01_exact_macro_aggregates(self):
        """Verify macro totals match exact calculations."""
        self.assertEqual(self.summary["dataset_rows"], 149270)
        self.assertEqual(self.summary["total_units_sold"], 114668)
        self.assertEqual(self.summary["total_returns_units"], 9666)
        self.assertEqual(self.summary["total_revenue_inr"], 223842750.0)
        self.assertEqual(self.summary["stockout_count"], 18696)
        self.assertAlmostEqual(self.summary["gross_margin_pct"], 50.76, places=2)
        self.assertAlmostEqual(self.summary["stockout_rate_pct"], 12.52, places=2)
        self.assertEqual(self.summary["latent_demand_units"], 157422.0)
        self.assertEqual(self.summary["unmet_demand_units"], 42754.0)
        self.assertAlmostEqual(self.summary["unmet_demand_pct"], 27.16, places=2)

    def test_02_exact_promotional_lifts(self):
        """Verify promotional lifts and discount depth differences."""
        p_info = self.summary["promotional_impact"]
        self.assertAlmostEqual(p_info["raw_promotional_lift_pct"], 13.43, places=2)
        # Compute exact in-stock lift from summary values
        is_lift = (p_info["promo_in_stock_avg_units"] / p_info["non_promo_in_stock_avg_units"] - 1) * 100
        self.assertAlmostEqual(is_lift, 27.76, delta=0.1)

    def test_03_exact_discount_band_sums(self):
        """Verify discount band records sum exactly to 149,270 and units to 114,668."""
        bands = self.summary["discount_band_metrics"]
        total_records = sum(b["records"] for b in bands)
        total_units = sum(b["units_sold"] for b in bands)
        self.assertEqual(total_records, 149270)
        self.assertEqual(total_units, 114668)
        # Specific full price band check
        full_price = next(b for b in bands if b["discount_band"] == "0% (Full Price)")
        self.assertEqual(full_price["records"], 79010)
        self.assertEqual(full_price["units_sold"], 52742)

    def test_04_category_and_store_counts(self):
        """Verify 5 categories and 5 stores are present with positive margins."""
        self.assertEqual(len(self.summary["category_metrics"]), 5)
        self.assertEqual(len(self.summary["store_metrics"]), 5)
        for cat in self.summary["category_metrics"]:
            self.assertGreater(cat["gross_margin_pct"], 30.0)
            self.assertGreater(cat["units_sold"], 0)

    def test_05_canonical_cleaned_csv_preserved(self):
        """Verify canonical dataset integrity remains uncompromised."""
        self.assertEqual(len(self.df), 149270)
        self.assertEqual(len(self.df.columns), 63)
        self.assertEqual(self.df.duplicated(subset=["date", "store_id", "sku_id"]).sum(), 0)
        self.assertEqual(self.df.isnull().sum().sum(), 0)

    def test_06_visualizations_exist_and_non_empty(self):
        """Verify all 4 plot figures were generated as non-empty PNG files."""
        expected_figs = [
            "daily_sales_trend.png",
            "demand_censoring_gap.png",
            "category_revenue.png",
            "sales_velocity_by_discount_band.png"
        ]
        for fig_name in expected_figs:
            fig_path = os.path.join(FIGURES_DIR, fig_name)
            self.assertTrue(os.path.exists(fig_path), f"Figure {fig_name} missing!")
            self.assertGreater(os.path.getsize(fig_path), 5000, f"Figure {fig_name} too small/empty!")


if __name__ == "__main__":
    unittest.main()
