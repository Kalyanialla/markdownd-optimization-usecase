"""
Optimization run execution and candidate retrieval endpoints.
"""

import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.permissions import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.user import User
from backend.app.schemas.optimization import (
    OptimizationRunCreateRequest,
    OptimizationRunResponse,
    OptimizationRunDetailResponse,
    CandidateResponse,
)
from backend.app.services.optimization_service import OptimizationService

router = APIRouter(prefix="/optimization-runs", tags=["Markdown Optimization"])


@router.post("", response_model=OptimizationRunDetailResponse, status_code=status.HTTP_201_CREATED)
def create_optimization_run(
    request: OptimizationRunCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes a multi-objective markdown optimization run for a given SKU and Store.
    Evaluates policy constraints, invokes trained ML models (XGBoost Demand, Price Response, Stockout),
    computes risk-adjusted profit outcomes, and persists results with full audit trail.
    """
    return OptimizationService.execute_run(db=db, user=current_user, request=request)


@router.get("", response_model=List[OptimizationRunResponse])
def list_optimization_runs(
    sku: Optional[str] = Query(None, description="Filter by SKU code"),
    store_id: Optional[str] = Query(None, description="Filter by store ID"),
    limit: int = Query(50, ge=1, le=100, description="Max runs to return"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns recent historical optimization runs.
    """
    return OptimizationService.list_runs(db=db, sku=sku, store_id=store_id, limit=limit)


@router.get("/{run_id}", response_model=OptimizationRunDetailResponse)
def get_optimization_run(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns full run specification including inputs, model metadata, and candidate evaluations.
    """
    return OptimizationService.get_run_detail(db=db, run_id=run_id)


@router.get("/{run_id}/candidates", response_model=List[CandidateResponse])
def get_run_candidates(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns candidate price points, predicted demand, stockout risk, and financials for a run.
    """
    run_detail = OptimizationService.get_run_detail(db=db, run_id=run_id)
    return run_detail.candidates
