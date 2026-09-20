"""0009_validation_engine

Revision ID: 0009_validation_engine
Revises: 0008_scheme_drafts
Create Date: 2026-09-06 23:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0009_validation_engine'
down_revision: Union[str, None] = '0008_scheme_drafts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create validation_runs table
    op.create_table(
        'validation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for validation run record'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False, comment='Associated canonical scheme draft identifier'),
        sa.Column('validator_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version of validation engine'),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Specification version of validation schema'),
        sa.Column('canonical_artifact_hash', sa.String(length=64), nullable=False, comment='SHA-256 checksum of canonical.json draft validated in this run'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='VALIDATING', comment='VALIDATING, VALIDATION_PASSED, VALIDATION_REVIEW_REQUIRED, VALIDATION_FAILED, STALE'),
        sa.Column('blocker_count', sa.Integer(), nullable=False, server_default='0', comment='Number of BLOCKER issues detected'),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0', comment='Number of ERROR issues detected'),
        sa.Column('warning_count', sa.Integer(), nullable=False, server_default='0', comment='Number of WARNING issues detected'),
        sa.Column('info_count', sa.Integer(), nullable=False, server_default='0', comment='Number of INFO issues detected'),
        sa.Column('rules_checked_count', sa.Integer(), nullable=False, server_default='0', comment='Total validation rules evaluated in this run'),
        sa.Column('artifact_path', sa.String(length=500), nullable=True, comment='Storage path to validation_report.json artifact'),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Summary diagnostic metrics and performance info'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, comment='Execution start timestamp'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Execution finish timestamp'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='End-to-end validation latency in milliseconds'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_validation_runs_id', 'validation_runs', ['id'])
    op.create_index('ix_validation_runs_scheme_draft_id', 'validation_runs', ['scheme_draft_id'])
    op.create_index('ix_validation_runs_status', 'validation_runs', ['status'])
    op.create_index('ix_validation_runs_canonical_artifact_hash', 'validation_runs', ['canonical_artifact_hash'])
    op.create_index('ix_validation_runs_draft_status', 'validation_runs', ['scheme_draft_id', 'status'])
    op.create_index('ix_validation_runs_draft_hash', 'validation_runs', ['scheme_draft_id', 'canonical_artifact_hash'])

    # 2. Create validation_issues table
    op.create_table(
        'validation_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for validation issue finding'),
        sa.Column('validation_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('validation_runs.id', ondelete='CASCADE'), nullable=False, comment='Associated validation execution run'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False, comment='Associated canonical scheme draft'),
        sa.Column('rule_code', sa.String(length=64), nullable=False, comment='Stable validation rule identifier, e.g. AGE_RANGE_INVALID'),
        sa.Column('severity', sa.String(length=20), nullable=False, comment='INFO, WARNING, ERROR, BLOCKER'),
        sa.Column('field_path', sa.String(length=255), nullable=True, comment='Dot-notation path to the invalid field'),
        sa.Column('message', sa.Text(), nullable=False, comment='Precise description of the validation failure or anomaly'),
        sa.Column('actual_value', sa.Text(), nullable=True, comment='Stringified actual extracted value causing the issue'),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='List of evidence IDs linked to this condition'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='OPEN', comment='OPEN, ACKNOWLEDGED, RESOLVED, IGNORED_WITH_REASON'),
        sa.Column('resolution_notes', sa.Text(), nullable=True, comment='Reviewer notes or reason for resolution'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_validation_issues_id', 'validation_issues', ['id'])
    op.create_index('ix_validation_issues_validation_run_id', 'validation_issues', ['validation_run_id'])
    op.create_index('ix_validation_issues_scheme_draft_id', 'validation_issues', ['scheme_draft_id'])
    op.create_index('ix_validation_issues_rule_code', 'validation_issues', ['rule_code'])
    op.create_index('ix_validation_issues_severity', 'validation_issues', ['severity'])
    op.create_index('ix_validation_issues_status', 'validation_issues', ['status'])
    op.create_index('ix_validation_issues_draft_rule', 'validation_issues', ['scheme_draft_id', 'rule_code'])
    op.create_index('ix_validation_issues_draft_severity', 'validation_issues', ['scheme_draft_id', 'severity'])


def downgrade() -> None:
    op.drop_table('validation_issues')
    op.drop_table('validation_runs')
