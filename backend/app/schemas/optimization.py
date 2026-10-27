"""
Pydantic schemas for optimization runs, candidates, and multi-objective evaluations.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OptimizationRunCreateRequest(BaseModel):
    sku_id: str = Field(..., description="Target product SKU identifier")
    store_id: str = Field("STORE-01", description="Target store identifier")
    planning_horizon_days: int = Field(7, ge=1, le=30, description="Planning horizon in days")
    objective_mode: Optional[str] = Field("MAX_PROFIT", description="Optimization objective: 'MAX_PROFIT' or 'CLEAR_INVENTORY'")
    clearance_holding_cost_rate: Optional[float] = Field(0.15, ge=0.0, le=1.0, description="Holding and obsolescence rate as a fraction of unit cost")
    idempotency_key: Optional[str] = Field(None, description="Optional idempotency key for safe retries")


class CandidateResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    discount_pct: float
    candidate_price: float
    predicted_demand: Optional[float] = None
    stockout_risk: Optional[float] = None
    unit_margin: Optional[float] = None
    estimated_revenue: Optional[float] = None
    estimated_gross_profit: Optional[float] = None
    risk_adjusted_profit: Optional[float] = None
    expected_fulfilled_units: Optional[float] = None
    expected_terminal_stock: Optional[float] = None
    sell_through_pct: Optional[float] = None
    residual_holding_cost: Optional[float] = None
    clearance_adjusted_profit: Optional[float] = None
    ranking_score: Optional[float] = None
    explanation: Optional[str] = None
    policy_passed: bool
    rejection_reasons: Optional[str] = None
    is_recommended: bool = False
    score_details: Optional[Dict[str, Any]] = None


class OptimizationRunResponse(BaseModel):
    id: uuid.UUID
    sku: str
    store_id: str
    status: str
    requested_by: Optional[uuid.UUID] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    input_snapshot: Dict[str, Any]
    model_versions: Dict[str, Any]
    policy_snapshot: Dict[str, Any]
    candidates_count: int = 0
    objective_mode: Optional[str] = "MAX_PROFIT"
    recommended_discount_pct: Optional[float] = None
    recommended_price: Optional[float] = None
    recommended_sell_through_pct: Optional[float] = None
    recommended_explanation: Optional[str] = None


class OptimizationRunDetailResponse(OptimizationRunResponse):
    candidates: List[CandidateResponse] = []
