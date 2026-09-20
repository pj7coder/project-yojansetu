"""0007_extraction_runs

Revision ID: 0007_extraction_runs
Revises: 0006_document_chunks
Create Date: 2026-09-06 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0007_extraction_runs'
down_revision: Union[str, None] = '0006_document_chunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create extraction_runs table
    op.create_table(
        'extraction_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for extraction run record'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Associated document identifier'),
        sa.Column('chunk_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document_chunks.id', ondelete='CASCADE'), nullable=False, comment='Associated semantic chunk identifier'),
        sa.Column('chunk_id_str', sa.String(length=64), nullable=False, comment='Stable chunk identifier string'),
        sa.Column('model_provider', sa.String(length=50), nullable=False, server_default='ollama', comment='LLM provider name (ollama, mock, etc.)'),
        sa.Column('model_name', sa.String(length=100), nullable=False, server_default='llama3.2:3b', comment='Exact LLM model name used for extraction'),
        sa.Column('prompt_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version identifier of extraction system/prompt template'),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version identifier of output extraction schema'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='QUEUED', comment='QUEUED, EXTRACTING, EXTRACTED, EXTRACTION_FAILED, EXTRACTION_REVIEW_REQUIRED'),
        sa.Column('artifact_path', sa.String(length=500), nullable=False, comment='Relative path to storage/extracted/<doc_id>/<chunk_id>/extraction.json'),
        sa.Column('input_token_estimate', sa.Integer(), nullable=False, server_default='0', comment='Estimated prompt token count'),
        sa.Column('output_tokens', sa.Integer(), nullable=True, comment='Actual output token count reported by provider'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Total end-to-end extraction latency in milliseconds'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='Error message or violation explanation if extraction failed'),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured validation diagnostics'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when model inference started'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when extraction finished'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )

    # 2. Create performance & query indexes
    op.create_index('ix_extraction_runs_document_id', 'extraction_runs', ['document_id'])
    op.create_index('ix_extraction_runs_chunk_id', 'extraction_runs', ['chunk_id'])
    op.create_index('ix_extraction_runs_chunk_id_str', 'extraction_runs', ['chunk_id_str'])
    op.create_index('ix_extraction_runs_status', 'extraction_runs', ['status'])
    op.create_index('ix_extraction_runs_created_at', 'extraction_runs', ['created_at'])
    op.create_index('ix_extraction_runs_doc_chunk', 'extraction_runs', ['document_id', 'chunk_id'])


def downgrade() -> None:
    op.drop_index('ix_extraction_runs_doc_chunk', table_name='extraction_runs')
    op.drop_index('ix_extraction_runs_created_at', table_name='extraction_runs')
    op.drop_index('ix_extraction_runs_status', table_name='extraction_runs')
    op.drop_index('ix_extraction_runs_chunk_id_str', table_name='extraction_runs')
    op.drop_index('ix_extraction_runs_chunk_id', table_name='extraction_runs')
    op.drop_index('ix_extraction_runs_document_id', table_name='extraction_runs')
    op.drop_table('extraction_runs')
