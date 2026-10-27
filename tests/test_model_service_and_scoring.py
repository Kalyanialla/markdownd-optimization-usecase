"""
Tests for OptimizerModelService, Model Contract Validation, and Candidate-Specific Stockout Scoring.
UC-RT-03 Markdown Optimization
"""

import os
import pytest
import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

from ml.optimizer.model_service import OptimizerModelService
from ml.optimizer.optimizer import DeterministicMarkdownOptimizer


@pytest.fixture(scope="module")
def sample_row():
    test_csv = os.path.join(REPO_ROOT, "data/processed/test.csv")
    df = pd.read_csv(test_csv, nrows=1)
    return df.iloc[0].copy()


@pytest.fixture(scope="module")
def model_service():
    return OptimizerModelService()


@pytest.fixture(scope="module")
def optimizer():
    return DeterministicMarkdownOptimizer()


# ==============================================================================
# 1. Model Feature Schema & Order Contract
# ==============================================================================

def test_model_service_loads_all_artifacts(model_service):
    """OptimizerModelService successfully loads all 3 XGBoost models and encoders."""
    assert model_service.m1_model is not None
    assert model_service.m1_encoder is not None
    assert model_service.m2_model is not None
    assert model_service.m2_encoder is not None
    assert model_service.m3_model is not None
    assert model_service.m3_encoder is not None


def test_model_service_feature_count_and_schema(model_service):
    """Model feature count matches the 65-feature contract for all models."""
    assert len(model_service.m1_model.feature_names_in_) == 65
    assert len(model_service.m2_model.feature_names_in_) == 65
    assert len(model_service.m3_model.feature_names_in_) == 65
    # M1 and M2 share exact feature ordering
    assert list(model_service.m1_model.feature_names_in_) == list(model_service.m2_model.feature_names_in_)
    # M3 contains the same set of 65 features
    assert set(model_service.m3_model.feature_names_in_) == set(model_service.m1_model.feature_names_in_)


# ==============================================================================
# 2. Candidate Feature Construction & Immutability
# ==============================================================================

def test_build_candidate_features_correctness_and_immutability(model_service, sample_row):
    """Candidate features are calculated correctly and do not mutate baseline row."""
    orig_selling_price = sample_row["selling_price"]
    orig_discount_pct = sample_row["discount_pct"]
    
    cand_df = model_service.build_candidate_features(
        baseline_row=sample_row,
        candidate_price=799.0,
        discount_pct=20.0,
        regular_price=999.0,
        unit_cost=400.0,
        competitor_price=850.0
    )
    
    # 1. Baseline row is strictly preserved (immutability)
    assert sample_row["selling_price"] == orig_selling_price
    assert sample_row["discount_pct"] == orig_discount_pct
    
    # 2. Candidate attributes are calculated correctly
    assert cand_df["selling_price"].iloc[0] == 799.0
    assert cand_df["discount_pct"].iloc[0] == 20.0
    assert cand_df["price_ratio_to_regular"].iloc[0] == round(799.0 / 999.0, 4)
    assert cand_df["price_ratio_to_cost"].iloc[0] == round(799.0 / 400.0, 4)
    assert cand_df["planned_margin_pct"].iloc[0] == round(((799.0 - 400.0) / 799.0) * 100.0, 2)
    assert cand_df["price_difference_to_competitor"].iloc[0] == round(799.0 - 850.0, 2)


# ==============================================================================
# 3. Model Roles: M1 Baseline Demand vs M2 Candidate Demand
# ==============================================================================

def test_model1_predicts_nonnegative_baseline_demand(model_service, sample_row):
    """Model 1 baseline demand prediction is finite, non-negative float."""
    m1_demand = model_service.predict_baseline_demand(sample_row)
    assert isinstance(m1_demand, float)
    assert np.isfinite(m1_demand)
    assert m1_demand >= 0.0


def test_model2_predicts_candidate_demand(model_service, sample_row):
    """Model 2 candidate demand prediction evaluates candidate-specific features."""
    cand_df = model_service.build_candidate_features(
        baseline_row=sample_row,
        candidate_price=800.0,
        discount_pct=20.0,
        regular_price=1000.0,
        unit_cost=400.0,
        competitor_price=900.0
    )
    m2_demand = model_service.predict_candidate_demand(cand_df)
    assert isinstance(m2_demand, float)
    assert np.isfinite(m2_demand)
    assert m2_demand >= 0.0


# ==============================================================================
# 4. Model 3 Candidate-Specific Stockout Risk Scoring
# ==============================================================================

def test_model3_predicts_valid_probability(model_service, sample_row):
    """Model 3 returns a probability bounded in [0, 1]."""
    feat_df = sample_row[model_service.features_66].to_frame().T
    prob = model_service.predict_stockout_risk(feat_df)
    assert isinstance(prob, float)
    assert np.isfinite(prob)
    assert 0.0 <= prob <= 1.0


def test_optimizer_uses_candidate_specific_stockout_risk(optimizer, sample_row):
    """
    In the optimizer, candidate discount steps must evaluate candidate-specific stockout risk
    and record both baseline and candidate-specific probabilities in the audit log.
    """
    rec = optimizer.optimize_sku_day(sample_row)
    assert rec["recommendation_status"] in ["RECOMMENDED", "NO_FEASIBLE_CANDIDATE"]
    
    # 1. Baseline demand and baseline risk are recorded
    assert "baseline_demand_forecast_m1" in rec
    assert "baseline_stockout_probability" in rec
    assert isinstance(rec["baseline_demand_forecast_m1"], float)
    assert 0.0 <= rec["baseline_stockout_probability"] <= 1.0
    
    # 2. Observational scenario flag is set for Model 2
    assert rec.get("model2_is_observational_scenario") is True
    
    # 3. Feasible candidates record candidate-specific stockout probability
    feasible_cands = [c for c in rec["candidate_evaluations"] if c["is_feasible"]]
    for cand in feasible_cands:
        assert "candidate_stockout_probability" in cand
        prob = cand["candidate_stockout_probability"]
        assert isinstance(prob, float)
        assert 0.0 <= prob <= 1.0
        # Financials must contain the matching stockout probability
        assert cand["financials"]["stockout_probability"] == round(prob, 4)
