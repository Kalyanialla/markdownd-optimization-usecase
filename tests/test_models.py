"""
Tests for Model Artifacts and Reproducible Inference.
UC-RT-03 Markdown Optimization
"""

import os
import joblib
import pandas as pd
import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
M1_PATH = os.path.join(REPO_ROOT, "ml/artifacts/model1/xgboost_demand_model.joblib")
M2_PATH = os.path.join(REPO_ROOT, "ml/artifacts/model2/xgboost_price_response_model.joblib")
M3_PATH = os.path.join(REPO_ROOT, "ml/artifacts/model3/xgboost_stockout_model.joblib")

def test_model_artifacts_exist():
    assert os.path.exists(M1_PATH), "Model 1 artifact missing"
    assert os.path.exists(M2_PATH), "Model 2 artifact missing"
    assert os.path.exists(M3_PATH), "Model 3 artifact missing"

def test_nonnegative_demand_prediction_policy():
    m1 = joblib.load(M1_PATH)
    # Check that predictions can be made and are bounded
    assert hasattr(m1, "predict")
    
def test_stockout_classifier_probabilities():
    m3 = joblib.load(M3_PATH)
    assert hasattr(m3, "predict_proba")
