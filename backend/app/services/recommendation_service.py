"""
Recommendation and Approval service handling state transitions, governance logs, and enrichments.
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session, aliased

from backend.app.db.models.user import User
from backend.app.db.models.optimization import OptimizationRun, OptimizationCandidate, Recommendation
from backend.app.db.models.governance import ApprovalEvent, AuditEvent
from backend.app.schemas.recommendation import (
    RecommendationCreateRequest,
    RecommendationResponse,
)


class RecommendationService:

    @staticmethod
    def _enrich_recommendation(
        rec: Recommendation,
        run: Optional[OptimizationRun],
        cand: Optional[OptimizationCandidate],
        submitter: Optional[User],
        reviewer: Optional[User]
    ) -> RecommendationResponse:
        snap = run.input_snapshot if (run and isinstance(run.input_snapshot, dict)) else {}
        product_name = snap.get("product_name")
        reg_price = float(snap.get("regular_price")) if snap.get("regular_price") is not None else None
        cost = float(snap.get("unit_cost")) if snap.get("unit_cost") is not None else None
        horizon = int(snap.get("planning_horizon_days", 7)) if snap.get("planning_horizon_days") is not None else 7

        submit_event = next((e for e in rec.approval_events if e.action == "SUBMIT"), None) if hasattr(rec, "approval_events") and rec.approval_events else None
        rationale = submit_event.reason if submit_event else None

        return RecommendationResponse(
            id=rec.id,
            run_id=rec.run_id,
            candidate_id=rec.candidate_id,
            status=rec.status,
            submitted_by=rec.submitted_by,
            submitted_at=rec.submitted_at,
            reviewed_by=rec.reviewed_by,
            reviewed_at=rec.reviewed_at,
            review_reason=rec.review_reason,
            version=rec.version,
            sku=run.sku if run else None,
            product_name=product_name,
            store_id=run.store_id if run else None,
            regular_price=reg_price,
            unit_cost=cost,
            proposed_discount_pct=cand.discount_pct if cand else None,
            proposed_price=cand.candidate_price if cand else None,
            predicted_demand=cand.predicted_demand if cand else None,
            expected_revenue=cand.estimated_revenue if cand else None,
            expected_margin=cand.unit_margin if cand else None,
            expected_profit=cand.estimated_gross_profit if cand else None,
            risk_adjusted_profit=cand.risk_adjusted_profit if cand else None,
            expected_fulfilled_units=(cand.score_details.get("expected_fulfilled_units") if cand and cand.score_details else None),
            expected_terminal_stock=(cand.score_details.get("expected_terminal_stock") if cand and cand.score_details else None),
            sell_through_pct=(cand.score_details.get("sell_through_pct") if cand and cand.score_details else None),
            clearance_adjusted_profit=(cand.score_details.get("clearance_adjusted_profit") if cand and cand.score_details else None),
            objective_mode=(cand.score_details.get("objective_mode", "MAX_PROFIT") if cand and cand.score_details else "MAX_PROFIT"),
            planning_horizon_days=horizon,
            stockout_prob=cand.stockout_risk if cand else None,
            rationale=rationale,
            policy_passed=cand.policy_passed if cand else True,
            rejection_reasons=cand.rejection_reasons if cand else None,
            submitter_name=submitter.full_name if submitter else None,
            reviewer_name=reviewer.full_name if reviewer else None,
        )

    @classmethod
    def submit_recommendation(
        cls,
        db: Session,
        user: User,
        payload: RecommendationCreateRequest
    ) -> RecommendationResponse:
        run = db.execute(select(OptimizationRun).where(OptimizationRun.id == payload.run_id)).scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Optimization run not found")

        cand = db.execute(
            select(OptimizationCandidate).where(
                OptimizationCandidate.id == payload.candidate_id,
                OptimizationCandidate.run_id == payload.run_id
            )
        ).scalar_one_or_none()
        if not cand:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Optimization candidate not found for this run"
            )

        # Policy Revalidation: Only policy-compliant candidates may be submitted for approval
        if not cand.policy_passed:
            rejection_msg = cand.rejection_reasons or "Candidate violates binding pricing policy constraints"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot submit recommendation: {rejection_msg}"
            )

        # Check for existing active pending recommendation
        existing = db.execute(
            select(Recommendation).where(
                Recommendation.candidate_id == payload.candidate_id,
                Recommendation.status == "PENDING_APPROVAL"
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pending recommendation already exists for this candidate"
            )

        now = datetime.now(timezone.utc)
        rec = Recommendation(
            run_id=run.id,
            candidate_id=cand.id,
            status="PENDING_APPROVAL",
            submitted_by=user.id,
            submitted_at=now,
            review_reason=payload.rationale,
            version=1,
        )
        db.add(rec)
        db.flush()

        # Approval Event
        appr_event = ApprovalEvent(
            recommendation_id=rec.id,
            actor_id=user.id,
            action="SUBMIT",
            reason=payload.rationale,
            previous_status=None,
            new_status="PENDING_APPROVAL",
            created_at=now,
        )
        db.add(appr_event)

        # Audit Event
        audit_event = AuditEvent(
            actor_id=user.id,
            event_type="RECOMMENDATION_SUBMITTED",
            entity_type="recommendation",
            entity_id=str(rec.id),
            details_json={
                "run_id": str(run.id),
                "sku": run.sku,
                "store_id": run.store_id,
                "candidate_id": str(cand.id),
                "discount_pct": cand.discount_pct,
                "price": cand.candidate_price,
                "rationale": payload.rationale,
            },
            created_at=now,
        )
        db.add(audit_event)

        db.commit()
        db.refresh(rec)

        return cls._enrich_recommendation(rec, run, cand, user, None)

    @classmethod
    def approve_recommendation(
        cls,
        db: Session,
        user: User,
        recommendation_id: UUID,
        notes: Optional[str] = None
    ) -> RecommendationResponse:
        # 1. Row-level lock on recommendation to prevent race conditions & concurrent approvals
        query = select(Recommendation).where(Recommendation.id == recommendation_id)
        if db.bind and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        rec = db.execute(query).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

        # 2. Check workflow status (must be strictly PENDING_APPROVAL)
        if rec.status != "PENDING_APPROVAL":
            now = datetime.now(timezone.utc)
            audit_fail = AuditEvent(
                actor_id=user.id,
                event_type="APPROVAL_ATTEMPT_REJECTED",
                entity_type="recommendation",
                entity_id=str(rec.id),
                details_json={
                    "run_id": str(rec.run_id),
                    "reason": f"Cannot approve recommendation in '{rec.status}' status",
                    "approver": user.email,
                },
                created_at=now,
            )
            db.add(audit_fail)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve recommendation in '{rec.status}' status"
            )

        # 3. Verify candidate exists and belongs to the linked optimization run
        cand = db.execute(
            select(OptimizationCandidate).where(
                OptimizationCandidate.id == rec.candidate_id,
                OptimizationCandidate.run_id == rec.run_id
            )
        ).scalar_one_or_none()
        if not cand:
            now = datetime.now(timezone.utc)
            audit_fail = AuditEvent(
                actor_id=user.id,
                event_type="APPROVAL_ATTEMPT_REJECTED",
                entity_type="recommendation",
                entity_id=str(rec.id),
                details_json={
                    "reason": "Candidate record missing or mismatched from linked run",
                    "approver": user.email,
                },
                created_at=now,
            )
            db.add(audit_fail)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Candidate record missing or mismatched from linked optimization run"
            )

        # 4. Verify run existence and load run input/policy snapshot
        run = db.execute(select(OptimizationRun).where(OptimizationRun.id == rec.run_id)).scalar_one_or_none()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Linked optimization run record missing"
            )

        # 5. Policy recalculation and revalidation at approval time against the run's evaluation snapshot
        from ml.optimizer.pricing_rules import PricingPolicyEngine, PriceHistoryService
        engine = PricingPolicyEngine()
        input_snap = run.input_snapshot or {}
        eval_date = str(input_snap.get("inventory_effective_date") or input_snap.get("date") or "2025-06-30")
        sku_clean = str(input_snap.get("sku_id") or run.sku).upper()
        store_clean = str(input_snap.get("store_id") or run.store_id).upper()
        cat_clean = input_snap.get("category")
        if not cat_clean:
            try:
                from backend.app.services.product_service import ProductService
                cat_clean = ProductService.get_product_by_sku(sku_clean, store_id=store_clean).category
            except Exception:
                cat_clean = "General"
        cat_clean = str(cat_clean)

        # Re-resolve policy using historical evaluation context
        resolved_policy = engine.resolve_policy(
            sku_id=sku_clean,
            store_id=store_clean,
            category=cat_clean,
            date_str=eval_date
        )

        phs = PriceHistoryService()
        days_since = phs.get_days_since_last_change(sku_clean, store_clean, eval_date)
        last_dt = phs.get_last_price_change_date(sku_clean, store_clean, eval_date)

        val_result = engine.validate_candidate(
            candidate_price=cand.candidate_price,
            discount_pct=cand.discount_pct,
            regular_price=float(input_snap.get("regular_price", cand.candidate_price)),
            unit_cost=float(input_snap.get("unit_cost", 0.0)),
            policy=resolved_policy,
            days_since_last_change=days_since,
            has_history=(last_dt is not None)
        )

        if not val_result.get("is_feasible", False) or not cand.policy_passed:
            rejection_msg = val_result.get("rejection_reason") or cand.rejection_reasons or "Candidate violates binding pricing policy constraints"
            now = datetime.now(timezone.utc)
            audit_fail = AuditEvent(
                actor_id=user.id,
                event_type="APPROVAL_ATTEMPT_REJECTED",
                entity_type="recommendation",
                entity_id=str(rec.id),
                details_json={
                    "run_id": str(rec.run_id),
                    "candidate_id": str(rec.candidate_id),
                    "discount_pct": cand.discount_pct,
                    "rejection_reason": rejection_msg,
                    "approver": user.email,
                },
                created_at=now,
            )
            db.add(audit_fail)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Policy constraint revalidation failed: {rejection_msg}"
            )

        # 6. Apply state transition atomically
        now = datetime.now(timezone.utc)
        prev_status = rec.status
        rec.status = "APPROVED"
        rec.reviewed_by = user.id
        rec.reviewed_at = now
        rec.review_reason = notes
        rec.version += 1

        appr_event = ApprovalEvent(
            recommendation_id=rec.id,
            actor_id=user.id,
            action="APPROVE",
            reason=notes,
            previous_status=prev_status,
            new_status="APPROVED",
            created_at=now,
        )
        db.add(appr_event)

        audit_event = AuditEvent(
            actor_id=user.id,
            event_type="RECOMMENDATION_APPROVED",
            entity_type="recommendation",
            entity_id=str(rec.id),
            details_json={
                "run_id": str(rec.run_id),
                "candidate_id": str(rec.candidate_id),
                "discount_pct": cand.discount_pct,
                "price": cand.candidate_price,
                "notes": notes,
                "approver": user.email,
                "policy_version_applied": resolved_policy.get("policy_version", 1),
                "evaluation_date": eval_date,
            },
            created_at=now,
        )
        db.add(audit_event)

        db.commit()
        db.refresh(rec)

        submitter = db.execute(select(User).where(User.id == rec.submitted_by)).scalar_one_or_none() if rec.submitted_by else None
        return cls._enrich_recommendation(rec, run, cand, submitter, user)

    @classmethod
    def reject_recommendation(
        cls,
        db: Session,
        user: User,
        recommendation_id: UUID,
        reason: str
    ) -> RecommendationResponse:
        if not reason or not reason.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rejection reason is required")

        query = select(Recommendation).where(Recommendation.id == recommendation_id)
        if db.bind and db.bind.dialect.name == "postgresql":
            query = query.with_for_update()

        rec = db.execute(query).scalar_one_or_none()
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

        if rec.status != "PENDING_APPROVAL":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject recommendation in '{rec.status}' status"
            )

        now = datetime.now(timezone.utc)
        prev_status = rec.status
        rec.status = "REJECTED"
        rec.reviewed_by = user.id
        rec.reviewed_at = now
        rec.review_reason = reason.strip()
        rec.version += 1

        appr_event = ApprovalEvent(
            recommendation_id=rec.id,
            actor_id=user.id,
            action="REJECT",
            reason=reason.strip(),
            previous_status=prev_status,
            new_status="REJECTED",
            created_at=now,
        )
        db.add(appr_event)

        audit_event = AuditEvent(
            actor_id=user.id,
            event_type="RECOMMENDATION_REJECTED",
            entity_type="recommendation",
            entity_id=str(rec.id),
            details_json={
                "run_id": str(rec.run_id),
                "candidate_id": str(rec.candidate_id) if rec.candidate_id else None,
                "reason": reason.strip(),
                "reviewer": user.email,
            },
            created_at=now,
        )
        db.add(audit_event)

        db.commit()
        db.refresh(rec)

        run = db.execute(select(OptimizationRun).where(OptimizationRun.id == rec.run_id)).scalar_one_or_none()
        cand = db.execute(select(OptimizationCandidate).where(OptimizationCandidate.id == rec.candidate_id)).scalar_one_or_none() if rec.candidate_id else None
        submitter = db.execute(select(User).where(User.id == rec.submitted_by)).scalar_one_or_none() if rec.submitted_by else None

        return cls._enrich_recommendation(rec, run, cand, submitter, user)

    @classmethod
    def get_summary_counts(cls, db: Session) -> dict:
        pending = db.execute(select(func.count(Recommendation.id)).where(Recommendation.status == "PENDING_APPROVAL")).scalar_one()
        approved = db.execute(select(func.count(Recommendation.id)).where(Recommendation.status == "APPROVED")).scalar_one()
        rejected = db.execute(select(func.count(Recommendation.id)).where(Recommendation.status == "REJECTED")).scalar_one()
        total = db.execute(select(func.count(Recommendation.id))).scalar_one()
        return {
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "total": total
        }

    @classmethod
    def list_recommendations(
        cls,
        db: Session,
        status_filter: Optional[str] = None,
        sku_filter: Optional[str] = None,
        store_filter: Optional[str] = None,
        days_filter: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[RecommendationResponse], int]:
        Submitter = aliased(User, name="submitter")
        Reviewer = aliased(User, name="reviewer")

        query = (
            select(Recommendation, OptimizationRun, OptimizationCandidate, Submitter, Reviewer)
            .join(OptimizationRun, Recommendation.run_id == OptimizationRun.id)
            .outerjoin(OptimizationCandidate, Recommendation.candidate_id == OptimizationCandidate.id)
            .outerjoin(Submitter, Recommendation.submitted_by == Submitter.id)
            .outerjoin(Reviewer, Recommendation.reviewed_by == Reviewer.id)
        )

        count_query = (
            select(func.count(Recommendation.id))
            .join(OptimizationRun, Recommendation.run_id == OptimizationRun.id)
        )

        if status_filter and status_filter.upper() != "ALL":
            query = query.where(Recommendation.status == status_filter.upper())
            count_query = count_query.where(Recommendation.status == status_filter.upper())

        if sku_filter:
            query = query.where(OptimizationRun.sku.ilike(f"%{sku_filter}%"))
            count_query = count_query.where(OptimizationRun.sku.ilike(f"%{sku_filter}%"))

        if store_filter and store_filter.upper() != "ALL":
            query = query.where(OptimizationRun.store_id == store_filter)
            count_query = count_query.where(OptimizationRun.store_id == store_filter)

        if days_filter and days_filter > 0:
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_filter)
            query = query.where(Recommendation.submitted_at >= cutoff)
            count_query = count_query.where(Recommendation.submitted_at >= cutoff)

        total = db.execute(count_query).scalar_one()

        rows = db.execute(
            query.order_by(desc(Recommendation.submitted_at)).limit(limit).offset(offset)
        ).all()

        items = [
            cls._enrich_recommendation(rec, run, cand, sub, rev)
            for rec, run, cand, sub, rev in rows
        ]

        return items, total

