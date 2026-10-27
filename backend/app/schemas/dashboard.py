"""
Pydantic schemas for Pricing Policy, Audit Trail, and Dashboard endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class PolicyItem(BaseModel):
    policy_id: str
    category: str
    min_markdown_pct: float
    max_markdown_pct: float
    allowed_steps: List[float]
    min_gross_margin_pct: float
    max_markdown_frequency_days: int
    cadence: str
    effective_start: str
    effective_end: str
    is_active: bool


class PolicyResolveResponse(BaseModel):
    category: str
    target_date: str
    matched_policy_id: Optional[str] = None
    min_markdown_pct: Optional[float] = None
    max_markdown_pct: Optional[float] = None
    allowed_steps: List[float] = []
    min_gross_margin_pct: Optional[float] = None
    cadence: Optional[str] = None
    rule_source: str
    last_price_change_date: Optional[str] = None
    days_since_last_change: Optional[int] = None
    minimum_days_required: Optional[int] = 14
    cadence_eligible: Optional[bool] = None


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: Optional[UUID] = None
    actor_email: Optional[str] = None
    actor_name: Optional[str] = None
    event_type: str
    entity_type: str
    entity_id: str
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    outcome: Optional[str] = "SUCCESS"


class AuditSummaryResponse(BaseModel):
    total: int
    successful: int
    failed: int
    today: int


class AuditListResponse(BaseModel):
    items: List[AuditEventResponse]
    total: int


class AuditEventDetailResponse(BaseModel):
    event: AuditEventResponse
    summary: str
    outcome: str
    related_events: List[AuditEventResponse] = []
    related_records: Dict[str, Any] = {}


class DashboardMetrics(BaseModel):
    total_runs: int
    total_candidates: int
    pending_approvals: int
    approved_recommendations: int
    rejected_recommendations: int
    total_skus_tracked: int
    active_policies_count: int
    models_healthy: bool
    models_status: Dict[str, Any]
    recent_events: List[AuditEventResponse]
    approved_revenue_impact: float
    approved_profit_impact: float
