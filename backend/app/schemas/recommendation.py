"""
Pydantic schemas for Recommendations and Approval workflows.
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RecommendationCreateRequest(BaseModel):
    run_id: UUID = Field(..., description="ID of the optimization run")
    candidate_id: UUID = Field(..., description="ID of the selected candidate")
    rationale: Optional[str] = Field(None, max_length=500, description="Optional justification for recommendation")


class ApprovalActionRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes on approval")


class RejectionActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Mandatory reason for rejection")


class RecommendationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    candidate_id: Optional[UUID] = None
    status: str
    submitted_by: Optional[UUID] = None
    submitted_at: datetime
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_reason: Optional[str] = None
    version: int

    # Enriched snapshot fields from Run / Candidate for UI display
    sku: Optional[str] = None
    product_name: Optional[str] = None
    store_id: Optional[str] = None
    regular_price: Optional[float] = None
    unit_cost: Optional[float] = None
    proposed_discount_pct: Optional[float] = None
    proposed_price: Optional[float] = None
    predicted_demand: Optional[float] = None
    expected_revenue: Optional[float] = None
    expected_margin: Optional[float] = None
    expected_profit: Optional[float] = None
    risk_adjusted_profit: Optional[float] = None
    expected_fulfilled_units: Optional[float] = None
    expected_terminal_stock: Optional[float] = None
    sell_through_pct: Optional[float] = None
    clearance_adjusted_profit: Optional[float] = None
    objective_mode: Optional[str] = None
    planning_horizon_days: Optional[int] = None
    stockout_prob: Optional[float] = None
    rationale: Optional[str] = None
    policy_passed: Optional[bool] = None
    rejection_reasons: Optional[str] = None
    submitter_name: Optional[str] = None
    reviewer_name: Optional[str] = None


class RecommendationSummaryResponse(BaseModel):
    pending: int = 0
    approved: int = 0
    rejected: int = 0
    total: int = 0


class RecommendationListResponse(BaseModel):
    items: List[RecommendationResponse]
    total: int
