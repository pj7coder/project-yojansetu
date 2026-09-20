"""0006_document_chunks

Revision ID: 0006_document_chunks
Revises: 0005_ocr_runs
Create Date: 2026-09-06 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0006_document_chunks'
down_revision: Union[str, None] = '0005_ocr_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for document chunk record'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Document identifier from which this chunk was generated'),
        sa.Column('chunk_id_str', sa.String(length=64), nullable=False, comment='Stable internal chunk identifier, e.g. DOC-XXXX-CHUNK-0001'),
        sa.Column('chunk_index', sa.Integer(), nullable=False, comment='Sequential 0-based order index of chunk in document'),
        sa.Column('section_type', sa.String(length=50), nullable=False, comment='Controlled section category (ELIGIBILITY, BENEFITS, etc.)'),
        sa.Column('section_path', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Hierarchical section path list'),
        sa.Column('chunk_title', sa.String(length=255), nullable=True, comment='Human-readable title or heading of chunk'),
        sa.Column('page_start', sa.Integer(), nullable=False, comment='First physical 1-based page number included in this chunk'),
        sa.Column('page_end', sa.Integer(), nullable=False, comment='Last physical 1-based page number included in this chunk'),
        sa.Column('token_count', sa.Integer(), nullable=False, comment='Calibrated token count estimate for Llama 3.2'),
        sa.Column('contains_table', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='True if chunk contains at least one structured table'),
        sa.Column('contains_ocr', sa.Boolean(), nullable=False, server_default=sa.text('false'), comment='True if chunk contains blocks derived from PaddleOCR fallback'),
        sa.Column('source_block_count', sa.Integer(), nullable=False, server_default='0', comment='Total source block IDs linked to this chunk'),
        sa.Column('artifact_path', sa.String(length=500), nullable=False, comment='Relative path to storage/chunks/<doc_id>/chunks/chunk_XXXX.txt'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Record creation timestamp'),
    )

    # 2. Create indexes
    op.create_index('ix_document_chunks_document_id', 'document_chunks', ['document_id'])
    op.create_index('ix_document_chunks_chunk_id_str', 'document_chunks', ['chunk_id_str'])
    op.create_index('ix_document_chunks_section_type', 'document_chunks', ['section_type'])
    op.create_index('ix_document_chunks_created_at', 'document_chunks', ['created_at'])
    op.create_index('ix_document_chunks_doc_idx', 'document_chunks', ['document_id', 'chunk_index'])
    op.create_index('ix_document_chunks_doc_section', 'document_chunks', ['document_id', 'section_type'])


def downgrade() -> None:
    op.drop_index('ix_document_chunks_doc_section', table_name='document_chunks')
    op.drop_index('ix_document_chunks_doc_idx', table_name='document_chunks')
    op.drop_index('ix_document_chunks_created_at', table_name='document_chunks')
    op.drop_index('ix_document_chunks_section_type', table_name='document_chunks')
    op.drop_index('ix_document_chunks_chunk_id_str', table_name='document_chunks')
    op.drop_index('ix_document_chunks_document_id', table_name='document_chunks')
    op.drop_table('document_chunks')
