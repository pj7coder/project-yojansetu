"""0004_parsed_documents

Revision ID: 0004_parsed_documents
Revises: 0003_duplicate_detection
Create Date: 2026-09-06 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0004_parsed_documents'
down_revision: Union[str, None] = '0003_duplicate_detection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create parsed_documents table
    op.create_table(
        'parsed_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for parsed document record'),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, comment='Document identifier being parsed'),
        sa.Column('parser_name', sa.String(length=50), nullable=False, server_default='mineru', comment='Parser engine name (mineru, builtin, etc.)'),
        sa.Column('parser_version', sa.String(length=50), nullable=True, comment='Version string of parser engine'),
        sa.Column('parse_status', sa.String(length=40), nullable=False, server_default='PARSED', comment='PARSED, PARSING_FAILED, REQUIRES_MANUAL_REVIEW'),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0', comment='Total pages parsed in PDF'),
        sa.Column('pages_with_text', sa.Integer(), nullable=False, server_default='0', comment='Pages containing extractable digital text'),
        sa.Column('pages_without_text', sa.Integer(), nullable=False, server_default='0', comment='Zero-text pages (indicates scanned pages needing OCR)'),
        sa.Column('pages_low_text', sa.Integer(), nullable=False, server_default='0', comment='Low-text pages (< 100 characters)'),
        sa.Column('total_text_characters', sa.Integer(), nullable=False, server_default='0', comment='Sum of text characters across all blocks'),
        sa.Column('total_blocks', sa.Integer(), nullable=False, server_default='0', comment='Total structured blocks'),
        sa.Column('total_tables', sa.Integer(), nullable=False, server_default='0', comment='Total structured tables preserved'),
        sa.Column('output_path', sa.String(length=500), nullable=False, comment='Relative path to storage/parsed/<doc_id>/ directory'),
        sa.Column('artifact_sha256', sa.String(length=64), nullable=True, comment='SHA-256 digest of normalized document.json artifact'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Parse execution time in milliseconds'),
        sa.Column('failure_reason', sa.Text(), nullable=True, comment='Detailed error or timeout message if parse failed'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when parsing commenced'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when parsing finished'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, comment='Record creation timestamp'),
    )

    # 2. Create indexes
    op.create_index('ix_parsed_documents_document_id', 'parsed_documents', ['document_id'])
    op.create_index('ix_parsed_documents_parse_status', 'parsed_documents', ['parse_status'])
    op.create_index('ix_parsed_documents_created_at', 'parsed_documents', ['created_at'])
    op.create_index('ix_parsed_documents_doc_status', 'parsed_documents', ['document_id', 'parse_status'])


def downgrade() -> None:
    op.drop_index('ix_parsed_documents_doc_status', table_name='parsed_documents')
    op.drop_index('ix_parsed_documents_created_at', table_name='parsed_documents')
    op.drop_index('ix_parsed_documents_parse_status', table_name='parsed_documents')
    op.drop_index('ix_parsed_documents_document_id', table_name='parsed_documents')
    op.drop_table('parsed_documents')
