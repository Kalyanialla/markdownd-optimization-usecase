"""
UC-RT-03: Model Service for Markdown Optimization.

Provides a unified, decoupled interface for:
- Model 1: Baseline demand reference forecast (certified production demand model)
- Model 2: Candidate-price demand estimator (observational scenario model; non-causal)
- Model 3: 7-day stockout risk estimator (candidate-specific and baseline scenario risk)

Enforces exact feature schemas, categorical encoding, and column order alignment
prior to model inference. Rejects missing or misordered features.
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from ml.common.feature_contract import STORE_OPENING_FEATURES_66, CATEGORICAL_FEATURES

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
ARTIFACTS_DIR = os.path.join(REPO_ROOT, "ml/artifacts")


class OptimizerModelService:
    def __init__(self, artifacts_dir: str = ARTIFACTS_DIR):
        self.artifacts_dir = artifacts_dir
        
        m1_path = os.path.join(artifacts_dir, "model1/xgboost_demand_model.joblib")
        m1_enc_path = os.path.join(artifacts_dir, "model1/categorical_encoder.joblib")
        m2_path = os.path.join(artifacts_dir, "model2/xgboost_price_response_model.joblib")
        m2_enc_path = os.path.join(artifacts_dir, "model2/categorical_encoder.joblib")
        m3_path = os.path.join(artifacts_dir, "model3/xgboost_stockout_model.joblib")
        m3_enc_path = os.path.join(artifacts_dir, "model3/categorical_encoder.joblib")
        
        self.m1_model = joblib.load(m1_path)
        self.m1_encoder = joblib.load(m1_enc_path)
        
        self.m2_model = joblib.load(m2_path)
        self.m2_encoder = joblib.load(m2_enc_path)
        
        self.m3_model = joblib.load(m3_path)
        self.m3_encoder = joblib.load(m3_enc_path)
        
        self.features_66 = list(STORE_OPENING_FEATURES_66)
        self.cat_cols = list(CATEGORICAL_FEATURES)
        self.num_cols = [c for c in self.features_66 if c not in self.cat_cols]

    def build_candidate_features(
        self,
        baseline_row: pd.Series,
        candidate_price: float,
        discount_pct: float,
        regular_price: float,
        unit_cost: float,
        competitor_price: float
    ) -> pd.DataFrame:
        """
        Builds a fresh, independent candidate feature row with candidate-specific
        pricing and derived margin/ratio attributes. Does not mutate the input row.
        """
        # Create fresh single-row DataFrame from baseline features
        cand_df = baseline_row[self.features_66].to_frame().T.copy()
        
        p_price = float(round(candidate_price, 2))
        disc = float(discount_pct)
        reg_p = float(regular_price)
        unit_c = float(unit_cost)
        comp_p = float(competitor_price)
        
        cand_df["selling_price"] = p_price
        cand_df["discount_pct"] = disc
        cand_df["price_ratio_to_regular"] = round(p_price / reg_p, 4) if reg_p > 0 else 1.0
        cand_df["price_ratio_to_cost"] = round(p_price / unit_c, 4) if unit_c > 0 else 1.0
        cand_df["planned_margin_pct"] = round(((p_price - unit_c) / p_price) * 100.0, 2) if p_price > 0 else 0.0
        cand_df["price_difference_to_competitor"] = round(p_price - comp_p, 2)
        
        return cand_df

    def predict_baseline_demand(self, baseline_row: pd.Series) -> float:
        """
        Model 1: Predicts baseline daily demand reference under current/regular price.
        Certified production demand forecast.
        """
        feat_df = baseline_row[self.features_66].to_frame().T.copy()
        feat_enc = feat_df.copy()
        feat_enc[self.cat_cols] = self.m1_encoder.transform(feat_enc[self.cat_cols].astype(str))
        feat_enc[self.num_cols] = feat_enc[self.num_cols].apply(pd.to_numeric)
        feat_enc = feat_enc[self.m1_model.feature_names_in_]
        
        pred = float(np.clip(self.m1_model.predict(feat_enc)[0], 0.0, None))
        return round(pred, 4)

    def predict_candidate_demand(self, candidate_feat_df: pd.DataFrame) -> float:
        """
        Model 2: Estimates candidate-price daily demand.
        NOTE: Model 2 is an observational scenario estimator trained on historical
        markdown data; it represents an observational scenario estimate rather than
        a validated causal price elasticity.
        """
        feat_enc = candidate_feat_df.copy()
        feat_enc[self.cat_cols] = self.m2_encoder.transform(feat_enc[self.cat_cols].astype(str))
        feat_enc[self.num_cols] = feat_enc[self.num_cols].apply(pd.to_numeric)
        feat_enc = feat_enc[self.m2_model.feature_names_in_]
        
        pred = float(np.clip(self.m2_model.predict(feat_enc)[0], 0.0, None))
        return round(pred, 4)

    def predict_stockout_risk(self, feat_df: pd.DataFrame) -> float:
        """
        Model 3: Predicts 7-day stockout risk probability for a given scenario (baseline or candidate).
        Features MUST be candidate-specific and ordered strictly to m3_model.feature_names_in_.
        """
        feat_enc = feat_df.copy()
        feat_enc[self.cat_cols] = self.m3_encoder.transform(feat_enc[self.cat_cols].astype(str))
        feat_enc[self.num_cols] = feat_enc[self.num_cols].apply(pd.to_numeric)
        
        # Enforce exact column order required by Model 3
        feat_enc = feat_enc[self.m3_model.feature_names_in_]
        
        prob = float(self.m3_model.predict_proba(feat_enc)[:, 1][0])
        if not np.isfinite(prob) or prob < 0.0 or prob > 1.0:
            raise ValueError(f"Model 3 returned invalid stockout probability: {prob}")
            
        return round(prob, 4)
