"""0005_ocr_runs

Revision ID: 0005_ocr_runs
Revises: 0004_parsed_documents
Create Date: 2026-09-06 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0005_ocr_runs'
down_revision: Union[str, None] = '0004_parsed_documents'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ocr_runs table
    op.create_table(
        'ocr_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for OCR run record'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Document identifier associated with this OCR run'),
        sa.Column('ocr_engine', sa.String(length=50), nullable=False, server_default='paddleocr', comment='OCR engine name (paddleocr, mock, etc.)'),
        sa.Column('ocr_version', sa.String(length=50), nullable=True, comment='Version string of OCR engine'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='COMPLETED', comment='COMPLETED, FAILED, PARTIAL_FAILURE, REVIEW_REQUIRED, SKIPPED_NOT_NEEDED'),
        sa.Column('pages_total', sa.Integer(), nullable=False, server_default='0', comment='Total pages in the document'),
        sa.Column('pages_checked', sa.Integer(), nullable=False, server_default='0', comment='Total pages evaluated for OCR requirement'),
        sa.Column('pages_ocr_required', sa.Integer(), nullable=False, server_default='0', comment='Number of pages detected as needing OCR'),
        sa.Column('pages_ocr_success', sa.Integer(), nullable=False, server_default='0', comment='Number of pages where OCR successfully ran and merged'),
        sa.Column('pages_ocr_failed', sa.Integer(), nullable=False, server_default='0', comment='Number of pages where OCR failed'),
        sa.Column('low_confidence_numeric_regions', sa.Integer(), nullable=False, server_default='0', comment='Count of numeric regions below confidence threshold'),
        sa.Column('output_path', sa.String(length=500), nullable=True, comment='Relative path to storage/ocr/<doc_id>/merged_document.json if OCR performed'),
        sa.Column('chunking_source_path', sa.String(length=500), nullable=False, comment='Selected source path for Day 8 chunking'),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured diagnostics including page decisions and per-page metrics'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when OCR process commenced'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when OCR process finished'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Total duration in milliseconds'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='Sanitized failure reason or error message if OCR failed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Record creation timestamp'),
    )

    # 2. Create indexes
    op.create_index('ix_ocr_runs_document_id', 'ocr_runs', ['document_id'])
    op.create_index('ix_ocr_runs_status', 'ocr_runs', ['status'])
    op.create_index('ix_ocr_runs_created_at', 'ocr_runs', ['created_at'])
    op.create_index('ix_ocr_runs_doc_status', 'ocr_runs', ['document_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_ocr_runs_doc_status', table_name='ocr_runs')
    op.drop_index('ix_ocr_runs_created_at', table_name='ocr_runs')
    op.drop_index('ix_ocr_runs_status', table_name='ocr_runs')
    op.drop_index('ix_ocr_runs_document_id', table_name='ocr_runs')
    op.drop_table('ocr_runs')
