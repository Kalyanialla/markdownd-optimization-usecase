"""Initial schema for users, optimization, recommendations, approvals, audit, and reports.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-19 16:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    portable_json = sa.JSON().with_variant(postgresql.JSONB, "postgresql")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='analyst', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. refresh_tokens
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refresh_tokens_token_hash'), 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index(op.f('ix_refresh_tokens_user_id'), 'refresh_tokens', ['user_id'], unique=False)

    # 3. optimization_runs
    op.create_table(
        'optimization_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('requested_by', sa.Uuid(), nullable=True),
        sa.Column('store_id', sa.String(length=50), nullable=False),
        sa.Column('sku', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='PENDING', nullable=False),
        sa.Column('input_snapshot', portable_json, nullable=False),
        sa.Column('model_versions', portable_json, nullable=False),
        sa.Column('policy_snapshot', portable_json, nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_optimization_runs_idempotency_key'), 'optimization_runs', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_optimization_runs_requested_by'), 'optimization_runs', ['requested_by'], unique=False)
    op.create_index(op.f('ix_optimization_runs_sku'), 'optimization_runs', ['sku'], unique=False)
    op.create_index(op.f('ix_optimization_runs_started_at'), 'optimization_runs', ['started_at'], unique=False)
    op.create_index(op.f('ix_optimization_runs_status'), 'optimization_runs', ['status'], unique=False)
    op.create_index(op.f('ix_optimization_runs_store_id'), 'optimization_runs', ['store_id'], unique=False)

    # 4. optimization_candidates
    op.create_table(
        'optimization_candidates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('discount_pct', sa.Float(), nullable=False),
        sa.Column('candidate_price', sa.Float(), nullable=False),
        sa.Column('predicted_demand', sa.Float(), nullable=True),
        sa.Column('stockout_risk', sa.Float(), nullable=True),
        sa.Column('unit_margin', sa.Float(), nullable=True),
        sa.Column('estimated_revenue', sa.Float(), nullable=True),
        sa.Column('estimated_gross_profit', sa.Float(), nullable=True),
        sa.Column('risk_adjusted_profit', sa.Float(), nullable=True),
        sa.Column('policy_passed', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('rejection_reasons', sa.String(length=500), nullable=True),
        sa.Column('score_details', portable_json, nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['optimization_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_optimization_candidates_run_id'), 'optimization_candidates', ['run_id'], unique=False)

    # 5. recommendations
    op.create_table(
        'recommendations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='PENDING_APPROVAL', nullable=False),
        sa.Column('submitted_by', sa.Uuid(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_reason', sa.String(length=500), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['optimization_candidates.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['run_id'], ['optimization_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recommendations_run_id'), 'recommendations', ['run_id'], unique=False)
    op.create_index(op.f('ix_recommendations_status'), 'recommendations', ['status'], unique=False)

    # 6. approval_events
    op.create_table(
        'approval_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('recommendation_id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('previous_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recommendation_id'], ['recommendations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_events_actor_id'), 'approval_events', ['actor_id'], unique=False)
    op.create_index(op.f('ix_approval_events_created_at'), 'approval_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_approval_events_recommendation_id'), 'approval_events', ['recommendation_id'], unique=False)

    # 7. audit_events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=False),
        sa.Column('details_json', portable_json, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_events_actor_id'), 'audit_events', ['actor_id'], unique=False)
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_events_event_type'), 'audit_events', ['event_type'], unique=False)

    # 8. report_artifacts
    op.create_table(
        'report_artifacts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('run_id', sa.Uuid(), nullable=False),
        sa.Column('artifact_type', sa.String(length=50), nullable=False),
        sa.Column('relative_path', sa.String(length=500), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['optimization_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_artifacts_run_id'), 'report_artifacts', ['run_id'], unique=False)


def downgrade() -> None:
    op.drop_table('report_artifacts')
    op.drop_table('audit_events')
    op.drop_table('approval_events')
    op.drop_table('recommendations')
    op.drop_table('optimization_candidates')
    op.drop_table('optimization_runs')
    op.drop_table('refresh_tokens')
    op.drop_table('users')
