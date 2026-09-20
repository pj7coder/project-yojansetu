"""0011_human_review

Revision ID: 0011_human_review
Revises: 0010_evidence_verification
Create Date: 2026-09-07 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0011_human_review'
down_revision: Union[str, None] = '0010_evidence_verification'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create human_review_sessions table
    op.create_table(
        'human_review_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique session identifier'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False, comment='Target canonical scheme draft'),
        sa.Column('reviewer_id', sa.String(length=64), nullable=False, server_default='DEV_REVIEWER', comment='Reviewer identifier'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='NOT_STARTED', comment='NOT_STARTED, IN_PROGRESS, BLOCKED, COMPLETED, REJECTED, STALE'),
        sa.Column('canonical_artifact_sha256', sa.String(length=64), nullable=False, comment='Checksum of canonical artifact when review initiated'),
        sa.Column('validation_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('validation_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('evidence_verification_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evidence_verification_runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('review_version', sa.Integer(), nullable=False, server_default='1', comment='Version counter for optimistic concurrency control'),
        sa.Column('notes', sa.Text(), nullable=True, comment='High-level session notes'),
        sa.Column('summary_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Review progress breakdown'),
        sa.Column('verified_artifact_path', sa.String(length=500), nullable=True, comment='Storage path to final verified JSON'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_review_sessions_draft_id', 'human_review_sessions', ['scheme_draft_id'])
    op.create_index('ix_review_sessions_status', 'human_review_sessions', ['status'])
    op.create_index('ix_review_sess_draft_status', 'human_review_sessions', ['scheme_draft_id', 'status'])

    # 2. Create human_review_items table
    op.create_table(
        'human_review_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique item identifier'),
        sa.Column('review_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('human_review_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('fact_id', sa.String(length=64), nullable=False, comment='Atomic fact identifier, e.g. FACT-001'),
        sa.Column('field_path', sa.String(length=255), nullable=False, comment='Canonical dot-notation field path'),
        sa.Column('item_type', sa.String(length=40), nullable=False, comment='IDENTITY, SCOPE, ELIGIBILITY, etc.'),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='NORMAL', comment='CRITICAL, HIGH, NORMAL, LOW'),
        sa.Column('statement', sa.Text(), nullable=False, comment='Human-readable claim'),
        sa.Column('original_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('current_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=True),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('evidence_text', sa.Text(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('block_id', sa.String(length=64), nullable=True),
        sa.Column('decision', sa.String(length=30), nullable=False, server_default='PENDING', comment='PENDING, APPROVED, EDITED, REJECTED, NOT_APPLICABLE'),
        sa.Column('reviewer_comment', sa.Text(), nullable=True),
        sa.Column('edit_reason', sa.Text(), nullable=True),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('validation_issues_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('verification_result', sa.String(length=30), nullable=True),
        sa.Column('verification_reason_code', sa.String(length=64), nullable=True),
        sa.Column('ocr_risk', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_by', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_review_items_session_id', 'human_review_items', ['review_session_id'])
    op.create_index('ix_review_items_draft_id', 'human_review_items', ['scheme_draft_id'])
    op.create_index('ix_review_items_fact_id', 'human_review_items', ['fact_id'])
    op.create_index('ix_review_items_decision', 'human_review_items', ['decision'])
    op.create_index('ix_review_item_session_decision', 'human_review_items', ['review_session_id', 'decision'])
    op.create_index('ix_review_item_draft_decision', 'human_review_items', ['scheme_draft_id', 'decision'])

    # 3. Create review_audit_events table
    op.create_table(
        'review_audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('review_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('human_review_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reviewer_id', sa.String(length=64), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('field_path', sa.String(length=255), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('before_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_review_audit_session_id', 'review_audit_events', ['review_session_id'])
    op.create_index('ix_review_audit_draft_id', 'review_audit_events', ['scheme_draft_id'])
    op.create_index('ix_review_audit_action_type', 'review_audit_events', ['action_type'])
    op.create_index('ix_review_audit_draft_action', 'review_audit_events', ['scheme_draft_id', 'action_type'])


def downgrade() -> None:
    op.drop_table('review_audit_events')
    op.drop_table('human_review_items')
    op.drop_table('human_review_sessions')
