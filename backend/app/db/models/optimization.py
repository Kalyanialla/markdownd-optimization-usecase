"""
Optimization runs, candidate evaluations, and recommendation models.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import String, Float, Boolean, Integer, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

# Portable JSON column: JSONB in PostgreSQL, standard JSON in SQLite
PortableJSON = JSON().with_variant(JSONB, "postgresql")


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    store_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING", index=True)  # PENDING, RUNNING, COMPLETED, FAILED
    
    input_snapshot: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    model_versions: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    policy_snapshot: Mapped[Dict[str, Any]] = mapped_column(PortableJSON, nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, index=True, nullable=True)

    # Relationships
    candidates = relationship("OptimizationCandidate", back_populates="run", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("ReportArtifact", back_populates="run", cascade="all, delete-orphan")


class OptimizationCandidate(Base):
    __tablename__ = "optimization_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    discount_pct: Mapped[float] = mapped_column(Float, nullable=False)
    candidate_price: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_demand: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stockout_risk: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    estimated_gross_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_adjusted_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    policy_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rejection_reasons: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    score_details: Mapped[Optional[Dict[str, Any]]] = mapped_column(PortableJSON, nullable=True)

    # Relationships
    run = relationship("OptimizationRun", back_populates="candidates")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("optimization_candidates.id", ondelete="SET NULL"),
        nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING_APPROVAL",
        index=True
    )  # PENDING_APPROVAL, APPROVED, REJECTED, WITHDRAWN
    submitted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    run = relationship("OptimizationRun", back_populates="recommendations")
    candidate = relationship("OptimizationCandidate")
    approval_events = relationship("ApprovalEvent", back_populates="recommendation", cascade="all, delete-orphan")
