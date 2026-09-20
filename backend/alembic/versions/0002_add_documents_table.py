"""0002_add_documents_table

Revision ID: 0002_add_documents_table
Revises: 0001_initial_scheme_tables
Create Date: 2026-09-06 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002_add_documents_table'
down_revision: Union[str, None] = '0001_initial_scheme_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('document_code', sa.String(length=64), nullable=False, comment='Unique internal document identifier'),
        sa.Column('original_filename', sa.String(length=500), nullable=False, comment='Preserved original filename including Unicode and spaces'),
        sa.Column('stored_filename', sa.String(length=255), nullable=False, server_default='original.pdf', comment='Standard internal stored filename'),
        sa.Column('file_extension', sa.String(length=16), nullable=False, server_default='.pdf', comment='Normalized file extension'),
        sa.Column('mime_type', sa.String(length=100), nullable=False, server_default='application/pdf', comment='Detected MIME content type'),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, comment='File size in bytes'),
        sa.Column('storage_path', sa.String(length=1000), nullable=False, comment='Relative path from storage root to preserved file'),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='SET NULL'), nullable=True, comment='Associated Day 3 government source if known'),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), nullable=True, comment='Associated source URL identifier if crawler-driven'),
        sa.Column('ingestion_method', sa.String(length=32), nullable=False, comment='MANUAL_UPLOAD, FOLDER_WATCHER, WEB_MONITOR, API'),
        sa.Column('processing_status', sa.String(length=32), nullable=False, server_default='RECEIVED', comment='RECEIVED, VALIDATING, READY_FOR_DUPLICATE_CHECK, INVALID, FAILED'),
        sa.Column('sha256', sa.String(length=64), nullable=True, comment='SHA-256 hash digest (non-unique in Day 4)'),
        sa.Column('title', sa.String(length=500), nullable=True, comment='Optional human-readable title'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='Sanitized failure reason if validation or ingestion failed'),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when upload/receipt was initiated'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_documents_document_code', 'documents', ['document_code'], unique=True)
    op.create_index('ix_documents_processing_status', 'documents', ['processing_status'])
    op.create_index('ix_documents_ingestion_method', 'documents', ['ingestion_method'])
    op.create_index('ix_documents_source_id', 'documents', ['source_id'])
    op.create_index('ix_documents_sha256', 'documents', ['sha256'])
    op.create_index('ix_documents_created_at', 'documents', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_documents_created_at', table_name='documents')
    op.drop_index('ix_documents_sha256', table_name='documents')
    op.drop_index('ix_documents_source_id', table_name='documents')
    op.drop_index('ix_documents_ingestion_method', table_name='documents')
    op.drop_index('ix_documents_processing_status', table_name='documents')
    op.drop_index('ix_documents_document_code', table_name='documents')
    op.drop_table('documents')
