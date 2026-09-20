"""0003_duplicate_detection

Revision ID: 0003_duplicate_detection
Revises: 0002_add_documents_table
Create Date: 2026-09-06 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0003_duplicate_detection'
down_revision: Union[str, None] = '0002_add_documents_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add duplicate & version detection columns to documents table
    op.add_column('documents', sa.Column('normalized_text_sha256', sa.String(length=64), nullable=True, comment='SHA-256 hash digest of normalized rough text fingerprint'))
    op.add_column('documents', sa.Column('page_count', sa.Integer(), nullable=True, comment='Total pages detected in the PDF document'))
    op.add_column('documents', sa.Column('text_length', sa.Integer(), nullable=True, comment='Character length of extracted normalized rough text'))
    op.add_column('documents', sa.Column('duplicate_status', sa.String(length=32), nullable=True, comment='NEW_DOCUMENT, EXACT_DUPLICATE, CONTENT_DUPLICATE, POSSIBLE_VERSION, POSSIBLE_NEAR_DUPLICATE, REVIEW_REQUIRED, CONFIRMED_VERSION'))
    op.add_column('documents', sa.Column('canonical_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, comment='Resolved root canonical document identifier'))
    op.add_column('documents', sa.Column('duplicate_of_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, comment='Direct matched duplicate document identifier'))
    op.add_column('documents', sa.Column('possible_version_of_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True, comment='Predecessor document of which this is an amendment or version'))
    op.add_column('documents', sa.Column('similarity_score', sa.Float(), nullable=True, comment='Highest shingle similarity score against matched document'))
    op.add_column('documents', sa.Column('duplicate_checked_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when duplicate analysis was completed'))
    op.add_column('documents', sa.Column('duplicate_check_reason', sa.Text(), nullable=True, comment='Detailed classification rationale or text difference summary'))

    # 2. Create indexes on new document columns
    op.create_index('ix_documents_normalized_text_sha256', 'documents', ['normalized_text_sha256'])
    op.create_index('ix_documents_duplicate_status', 'documents', ['duplicate_status'])
    op.create_index('ix_documents_canonical_document_id', 'documents', ['canonical_document_id'])
    op.create_index('ix_documents_duplicate_of_document_id', 'documents', ['duplicate_of_document_id'])
    op.create_index('ix_documents_possible_version_of_document_id', 'documents', ['possible_version_of_document_id'])

    # 3. Create document_relationships audit table
    op.create_table(
        'document_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('related_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(length=64), nullable=False, comment='EXACT_DUPLICATE_OF, CONTENT_DUPLICATE_OF, POSSIBLE_NEAR_DUPLICATE_OF, POSSIBLE_VERSION_OF'),
        sa.Column('similarity_score', sa.Float(), nullable=True, comment='Jaccard shingle similarity score between 0.0 and 1.0'),
        sa.Column('reason', sa.Text(), nullable=True, comment='Detailed classification reason or diff summary'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index('ix_document_relationships_document_id', 'document_relationships', ['document_id'])
    op.create_index('ix_document_relationships_related_document_id', 'document_relationships', ['related_document_id'])
    op.create_index('ix_document_relationships_relationship_type', 'document_relationships', ['relationship_type'])
    op.create_index('ix_doc_rel_pair', 'document_relationships', ['document_id', 'related_document_id'])


def downgrade() -> None:
    op.drop_table('document_relationships')

    op.drop_index('ix_documents_possible_version_of_document_id', table_name='documents')
    op.drop_index('ix_documents_duplicate_of_document_id', table_name='documents')
    op.drop_index('ix_documents_canonical_document_id', table_name='documents')
    op.drop_index('ix_documents_duplicate_status', table_name='documents')
    op.drop_index('ix_documents_normalized_text_sha256', table_name='documents')

    op.drop_column('documents', 'duplicate_check_reason')
    op.drop_column('documents', 'duplicate_checked_at')
    op.drop_column('documents', 'similarity_score')
    op.drop_column('documents', 'possible_version_of_document_id')
    op.drop_column('documents', 'duplicate_of_document_id')
    op.drop_column('documents', 'canonical_document_id')
    op.drop_column('documents', 'duplicate_status')
    op.drop_column('documents', 'text_length')
    op.drop_column('documents', 'page_count')
    op.drop_column('documents', 'normalized_text_sha256')
