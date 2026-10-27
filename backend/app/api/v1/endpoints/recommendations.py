"""
Recommendation & Approval workflow API endpoints.
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.db.models.user import User
from backend.app.schemas.recommendation import (
    RecommendationCreateRequest,
    RecommendationResponse,
    RecommendationSummaryResponse,
    RecommendationListResponse,
    ApprovalActionRequest,
    RejectionActionRequest,
)
from backend.app.services.recommendation_service import RecommendationService

router = APIRouter(prefix="/recommendations", tags=["Recommendations & Approvals"])


@router.post("", response_model=RecommendationResponse, status_code=status.HTTP_201_CREATED)
def submit_recommendation(
    payload: RecommendationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit an optimization candidate as a markdown recommendation for review.
    Available to analysts, approvers, and admins.
    """
    return RecommendationService.submit_recommendation(db, current_user, payload)


@router.get("/summary", response_model=RecommendationSummaryResponse)
def get_recommendations_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns global aggregate counts of pending, approved, and rejected recommendations.
    """
    return RecommendationService.get_summary_counts(db)


@router.get("", response_model=RecommendationListResponse)
def list_recommendations(
    status: Optional[str] = Query(None, description="Filter by status (PENDING_APPROVAL, APPROVED, REJECTED)"),
    sku: Optional[str] = Query(None, description="Filter by SKU substring"),
    store: Optional[str] = Query(None, description="Filter by store identifier"),
    days: Optional[int] = Query(None, description="Filter by last N days"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists markdown recommendations with optional status, SKU, store, and date filtering.
    """
    items, total = RecommendationService.list_recommendations(
        db, status_filter=status, sku_filter=sku, store_filter=store, days_filter=days, limit=limit, offset=offset
    )
    return RecommendationListResponse(items=items, total=total)


@router.post("/{recommendation_id}/approve", response_model=RecommendationResponse)
def approve_recommendation(
    recommendation_id: UUID,
    payload: ApprovalActionRequest = ApprovalActionRequest(),
    current_user: User = Depends(require_roles(["approver", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Approves a pending markdown recommendation.
    Enforces 'approver' or 'admin' server-side RBAC.
    """
    return RecommendationService.approve_recommendation(
        db, current_user, recommendation_id, payload.notes
    )


@router.post("/{recommendation_id}/reject", response_model=RecommendationResponse)
def reject_recommendation(
    recommendation_id: UUID,
    payload: RejectionActionRequest,
    current_user: User = Depends(require_roles(["approver", "admin"])),
    db: Session = Depends(get_db)
):
    """
    Rejects a pending markdown recommendation. Requires non-empty reason.
    Enforces 'approver' or 'admin' server-side RBAC.
    """
    return RecommendationService.reject_recommendation(
        db, current_user, recommendation_id, payload.reason
    )
