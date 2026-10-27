"""
Governance, audit trail, and artifact reporting models.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base

PortableJSON = JSON().with_variant(JSONB, "postgresql")


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("recommendations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # SUBMIT, APPROVE, REJECT, WITHDRAW
    reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    previous_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationships
    recommendation = relationship("Recommendation", back_populates="approval_events")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(PortableJSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )


class ReportArtifact(Base):
    __tablename__ = "report_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("optimization_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)  # json, csv, md
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    run = relationship("OptimizationRun", back_populates="artifacts")
