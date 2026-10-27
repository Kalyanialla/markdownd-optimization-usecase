"""
Audit Trail API endpoints.
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import Session

from backend.app.core.permissions import get_current_user
from backend.app.db.session import get_db
from backend.app.db.models.user import User
from backend.app.db.models.governance import AuditEvent
from backend.app.schemas.dashboard import (
    AuditEventResponse,
    AuditListResponse,
    AuditEventDetailResponse,
    AuditSummaryResponse,
)

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


def compute_event_outcome(event_type: str, details: Optional[dict]) -> str:
    details = details or {}
    outcome = details.get("outcome")
    if outcome:
        return str(outcome).upper()
    if event_type in ("APPROVAL_ATTEMPT_REJECTED", "RECOMMENDATION_REJECTED"):
        return "REJECTED"
    if "FAILED" in event_type or "ERROR" in event_type:
        return "FAILED"
    if "BLOCKED" in event_type:
        return "BLOCKED"
    return "SUCCESS"


@router.get("/summary", response_model=AuditSummaryResponse)
def get_audit_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns dynamic aggregate summary metrics across the persisted audit log:
    total events, successful outcomes, failed/rejected outcomes, and events recorded today.
    """
    total = db.execute(select(func.count(AuditEvent.id))).scalar_one()

    all_events = db.execute(select(AuditEvent.event_type, AuditEvent.details_json, AuditEvent.created_at)).all()
    
    successful = 0
    failed = 0
    today = 0
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    for ev_type, det, created in all_events:
        outcome = compute_event_outcome(ev_type, det)
        if outcome in ("FAILED", "REJECTED", "BLOCKED"):
            failed += 1
        else:
            successful += 1
        
        if created:
            c_tz = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
            if c_tz >= today_start:
                today += 1

    return AuditSummaryResponse(
        total=total,
        successful=successful,
        failed=failed,
        today=today,
    )


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome: SUCCESS, FAILED, REJECTED, BLOCKED"),
    search: Optional[str] = Query(None, description="Search across event type, entity ID, actor or details"),
    days: Optional[int] = Query(None, ge=0, description="Filter events within last N days (0 = all time)"),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns immutable, traceable audit logs of user and system events with pagination and rich filtering.
    """
    query = (
        select(AuditEvent, User)
        .outerjoin(User, AuditEvent.actor_id == User.id)
    )
    count_query = (
        select(func.count(AuditEvent.id))
        .outerjoin(User, AuditEvent.actor_id == User.id)
    )

    if event_type and event_type != "ALL":
        query = query.where(AuditEvent.event_type == event_type)
        count_query = count_query.where(AuditEvent.event_type == event_type)

    if entity_type and entity_type != "ALL":
        query = query.where(AuditEvent.entity_type == entity_type)
        count_query = count_query.where(AuditEvent.entity_type == entity_type)

    if days and days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(AuditEvent.created_at >= cutoff)
        count_query = count_query.where(AuditEvent.created_at >= cutoff)

    if search and search.strip():
        term = f"%{search.strip()}%"
        search_filter = or_(
            AuditEvent.event_type.ilike(term),
            AuditEvent.entity_type.ilike(term),
            AuditEvent.entity_id.ilike(term),
            User.email.ilike(term),
            User.full_name.ilike(term)
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if outcome and outcome != "ALL":
        outcome_upper = outcome.upper()
        if outcome_upper == "SUCCESS":
            success_filter = and_condition = (
                ~AuditEvent.event_type.in_(["APPROVAL_ATTEMPT_REJECTED", "RECOMMENDATION_REJECTED"]) &
                ~AuditEvent.event_type.ilike("%FAILED%") &
                ~AuditEvent.event_type.ilike("%ERROR%") &
                ~AuditEvent.event_type.ilike("%BLOCKED%")
            )
            query = query.where(success_filter)
            count_query = count_query.where(success_filter)
        elif outcome_upper in ("REJECTED", "FAILED", "BLOCKED"):
            failed_filter = or_(
                AuditEvent.event_type.in_(["APPROVAL_ATTEMPT_REJECTED", "RECOMMENDATION_REJECTED"]),
                AuditEvent.event_type.ilike("%FAILED%"),
                AuditEvent.event_type.ilike("%ERROR%"),
                AuditEvent.event_type.ilike("%BLOCKED%")
            )
            query = query.where(failed_filter)
            count_query = count_query.where(failed_filter)

    total = db.execute(count_query).scalar_one()

    rows = db.execute(
        query.order_by(desc(AuditEvent.created_at)).limit(limit).offset(offset)
    ).all()

    items = [
        AuditEventResponse(
            id=ev.id,
            actor_id=ev.actor_id,
            actor_email=user.email if user else None,
            actor_name=user.full_name if user else None,
            event_type=ev.event_type,
            entity_type=ev.entity_type,
            entity_id=ev.entity_id,
            details_json=ev.details_json,
            created_at=ev.created_at,
            outcome=compute_event_outcome(ev.event_type, ev.details_json)
        )
        for ev, user in rows
    ]

    return AuditListResponse(items=items, total=total)


@router.get("/{event_id}", response_model=AuditEventDetailResponse)
def get_audit_event_detail(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns full investigation details for a specific audit event, including
    event summary, outcome, related events, and linked run/recommendation records.
    """
    from uuid import UUID
    from fastapi import HTTPException, status
    from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation

    try:
        ev_uuid = UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event UUID")

    row = db.execute(
        select(AuditEvent, User)
        .outerjoin(User, AuditEvent.actor_id == User.id)
        .where(AuditEvent.id == ev_uuid)
    ).first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit event not found")

    ev, user = row
    details = ev.details_json or {}

    # Standardize outcome: respect explicitly recorded outcome or map deterministically by event type
    outcome = details.get("outcome")
    if not outcome:
        if ev.event_type in ("APPROVAL_ATTEMPT_REJECTED", "RECOMMENDATION_REJECTED"):
            outcome = "REJECTED"
        elif "FAILED" in ev.event_type or "ERROR" in ev.event_type:
            outcome = "FAILED"
        else:
            outcome = "SUCCESS"

    # Generate human-readable summary from recorded facts
    summary = f"Audit event {ev.event_type} recorded"
    sku_val = details.get("sku") or details.get("product", {}).get("sku") if isinstance(details.get("product"), dict) else details.get("sku")
    store_val = details.get("store_id") or details.get("product", {}).get("store_id") if isinstance(details.get("product"), dict) else details.get("store_id")
    actor_str = user.full_name or user.email or "System"

    if ev.event_type == "OPTIMIZATION_RUN_CREATED":
        summary = f"Markdown optimization run created for {sku_val or 'SKU'} at {store_val or 'Store'} by {actor_str}"
    elif ev.event_type == "RECOMMENDATION_SUBMITTED":
        disc = details.get("discount_pct", 0)
        summary = f"Markdown recommendation ({disc}% discount) submitted for review by {actor_str}"
    elif ev.event_type == "RECOMMENDATION_APPROVED":
        disc = details.get("discount_pct", 0)
        summary = f"Recommendation ({disc}% discount) approved by authorized manager {actor_str}"
    elif ev.event_type == "RECOMMENDATION_REJECTED":
        reason = details.get("reason", "Business discretion")
        summary = f"Recommendation rejected by {actor_str} (Reason: {reason})"
    elif ev.event_type == "APPROVAL_ATTEMPT_REJECTED":
        outcome = "REJECTED"
        reason = details.get("rejection_reason") or details.get("reason", "Policy constraint violation")
        summary = f"Approval blocked because policy validation failed: {reason}"

    # Correlate related run and recommendation
    run_id_str = details.get("run_id")
    rec_id_str = details.get("recommendation_id") or (ev.entity_id if ev.entity_type.lower() == "recommendation" else None)
    if not run_id_str and ev.entity_type.lower() in ("optimizationrun", "optimization_run"):
        run_id_str = ev.entity_id

    related_records: dict = {}
    related_events_list: list = []

    # Fetch linked run if present
    if run_id_str:
        try:
            run_uuid = UUID(run_id_str)
            db_run = db.execute(select(OptimizationRun).where(OptimizationRun.id == run_uuid)).scalar_one_or_none()
            if db_run:
                related_records["run"] = {
                    "id": str(db_run.id),
                    "sku": db_run.sku,
                    "store_id": db_run.store_id,
                    "status": db_run.status,
                    "started_at": db_run.started_at.isoformat() if db_run.started_at else None,
                    "completed_at": db_run.completed_at.isoformat() if db_run.completed_at else None,
                    "input_snapshot": db_run.input_snapshot,
                    "model_versions": db_run.model_versions,
                    "policy_snapshot": db_run.policy_snapshot,
                }
        except Exception:
            pass

    # Fetch linked recommendation if present
    if rec_id_str:
        try:
            rec_uuid = UUID(rec_id_str)
            db_rec = db.execute(select(Recommendation).where(Recommendation.id == rec_uuid)).scalar_one_or_none()
            if db_rec:
                related_records["recommendation"] = {
                    "id": str(db_rec.id),
                    "run_id": str(db_rec.run_id),
                    "candidate_id": str(db_rec.candidate_id) if db_rec.candidate_id else None,
                    "status": db_rec.status,
                    "submitted_at": db_rec.submitted_at.isoformat() if db_rec.submitted_at else None,
                    "reviewed_at": db_rec.reviewed_at.isoformat() if db_rec.reviewed_at else None,
                    "review_reason": db_rec.review_reason,
                }
        except Exception:
            pass

    # Fetch related audit events sharing run_id or entity_id
    if run_id_str or rec_id_str:
        rel_query = (
            select(AuditEvent, User)
            .outerjoin(User, AuditEvent.actor_id == User.id)
            .where(AuditEvent.id != ev.id)
            .order_by(desc(AuditEvent.created_at))
            .limit(10)
        )
        rel_rows = db.execute(rel_query).all()
        for r_ev, r_u in rel_rows:
            r_det = r_ev.details_json or {}
            match = False
            if run_id_str and (r_ev.entity_id == run_id_str or r_det.get("run_id") == run_id_str):
                match = True
            if rec_id_str and (r_ev.entity_id == rec_id_str or r_det.get("recommendation_id") == rec_id_str):
                match = True
            if match:
                related_events_list.append(
                    AuditEventResponse(
                        id=r_ev.id,
                        actor_id=r_ev.actor_id,
                        actor_email=r_u.email if r_u else None,
                        actor_name=r_u.full_name if r_u else None,
                        event_type=r_ev.event_type,
                        entity_type=r_ev.entity_type,
                        entity_id=r_ev.entity_id,
                        details_json=r_ev.details_json,
                        created_at=r_ev.created_at,
                    )
                )

    ev_resp = AuditEventResponse(
        id=ev.id,
        actor_id=ev.actor_id,
        actor_email=user.email if user else None,
        actor_name=user.full_name if user else None,
        event_type=ev.event_type,
        entity_type=ev.entity_type,
        entity_id=ev.entity_id,
        details_json=ev.details_json,
        created_at=ev.created_at,
    )

    return AuditEventDetailResponse(
        event=ev_resp,
        summary=summary,
        outcome=outcome,
        related_events=related_events_list,
        related_records=related_records,
    )
