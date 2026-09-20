"""0008_scheme_drafts

Revision ID: 0008_scheme_drafts
Revises: 0007_extraction_runs
Create Date: 2026-09-06 22:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0008_scheme_drafts'
down_revision: Union[str, None] = '0007_extraction_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create normalization_runs table
    op.create_table(
        'normalization_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for normalization run record'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Associated document identifier'),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Canonical schema specification version'),
        sa.Column('normalizer_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version identifier of normalization engine'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='NORMALIZING', comment='NORMALIZING, NORMALIZED, NORMALIZATION_FAILED, NORMALIZATION_REVIEW_REQUIRED, NORMALIZATION_BLOCKED, NO_SCHEME_FOUND'),
        sa.Column('schemes_detected', sa.Integer(), nullable=False, server_default='0', comment='Number of distinct scheme candidates identified'),
        sa.Column('fields_normalized', sa.Integer(), nullable=False, server_default='0', comment='Total count of canonical fields successfully normalized'),
        sa.Column('fields_ambiguous', sa.Integer(), nullable=False, server_default='0', comment='Count of fields marked AMBIGUOUS or REVIEW_REQUIRED'),
        sa.Column('conflicts_detected', sa.Integer(), nullable=False, server_default='0', comment='Count of contradictory values detected'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='End-to-end normalization latency in milliseconds'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='Error message or explanation if normalization failed'),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Summary report and counts'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when normalization started'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when normalization finished'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_index('ix_normalization_runs_document_id', 'normalization_runs', ['document_id'])
    op.create_index('ix_normalization_runs_status', 'normalization_runs', ['status'])
    op.create_index('ix_normalization_runs_created_at', 'normalization_runs', ['created_at'])
    op.create_index('ix_normalization_runs_doc_status', 'normalization_runs', ['document_id', 'status'])

    # 2. Create scheme_drafts table
    op.create_table(
        'scheme_drafts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for canonical scheme draft'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Source document identifier'),
        sa.Column('normalization_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('normalization_runs.id', ondelete='SET NULL'), nullable=True, comment='Associated normalization execution run'),
        sa.Column('internal_scheme_code', sa.String(length=64), unique=True, nullable=False, comment='Stable internal draft identity code (e.g. RJ-DRAFT-<UUID>)'),
        sa.Column('detected_name', sa.String(length=500), nullable=False, comment='Primary scheme name detected from document context'),
        sa.Column('official_name_raw', sa.Text(), nullable=True, comment='Unmodified official scheme name verbatim from government text'),
        sa.Column('official_name_hi', sa.String(length=500), nullable=True, comment='Explicit Hindi scheme name if present'),
        sa.Column('official_name_en', sa.String(length=500), nullable=True, comment='Explicit English scheme name if present'),
        sa.Column('normalized_name_for_matching', sa.String(length=500), nullable=False, comment='Normalized name for candidate matching'),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, comment='Matched Department registry ID if high-confidence deterministic match'),
        sa.Column('department_name_raw', sa.String(length=255), nullable=True, comment='Raw department string from government text'),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Canonical schema specification version'),
        sa.Column('normalizer_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version of normalization engine used'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='READY_FOR_VALIDATION', comment='READY_FOR_VALIDATION, NORMALIZATION_REVIEW_REQUIRED, NORMALIZATION_FAILED, SCHEME_ASSOCIATION_REVIEW_REQUIRED'),
        sa.Column('artifact_path', sa.String(length=500), nullable=False, comment='Relative path to storage/normalized/<doc_id>/<draft_id>/canonical.json'),
        sa.Column('conflict_count', sa.Integer(), nullable=False, server_default='0', comment='Number of unresolved contradictions flagged'),
        sa.Column('unresolved_field_count', sa.Integer(), nullable=False, server_default='0', comment='Number of fields marked AMBIGUOUS or REVIEW_REQUIRED'),
        sa.Column('summary_counts', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Summary metrics breakdown'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    op.create_index('ix_scheme_drafts_document_id', 'scheme_drafts', ['document_id'])
    op.create_index('ix_scheme_drafts_normalization_run_id', 'scheme_drafts', ['normalization_run_id'])
    op.create_index('ix_scheme_drafts_internal_scheme_code', 'scheme_drafts', ['internal_scheme_code'])
    op.create_index('ix_scheme_drafts_matching_name', 'scheme_drafts', ['normalized_name_for_matching'])
    op.create_index('ix_scheme_drafts_department_id', 'scheme_drafts', ['department_id'])
    op.create_index('ix_scheme_drafts_status', 'scheme_drafts', ['status'])
    op.create_index('ix_scheme_drafts_doc_status', 'scheme_drafts', ['document_id', 'status'])
    op.create_index('ix_scheme_drafts_created_at', 'scheme_drafts', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_scheme_drafts_created_at', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_doc_status', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_status', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_department_id', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_matching_name', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_internal_scheme_code', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_normalization_run_id', table_name='scheme_drafts')
    op.drop_index('ix_scheme_drafts_document_id', table_name='scheme_drafts')
    op.drop_table('scheme_drafts')

    op.drop_index('ix_normalization_runs_doc_status', table_name='normalization_runs')
    op.drop_index('ix_normalization_runs_created_at', table_name='normalization_runs')
    op.drop_index('ix_normalization_runs_status', table_name='normalization_runs')
    op.drop_index('ix_normalization_runs_document_id', table_name='normalization_runs')
    op.drop_table('normalization_runs')
