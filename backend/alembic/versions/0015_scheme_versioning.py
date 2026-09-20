"""0015_scheme_versioning

Revision ID: 0015_scheme_versioning
Revises: 0014_source_change_analysis
Create Date: 2026-09-09 18:00:00.000000

"""
import logging
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.migration.0015")

revision: str = '0015_scheme_versioning'
down_revision: Union[str, None] = '0014_source_change_analysis'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend scheme_versions
    op.add_column('scheme_versions', sa.Column('version_label', sa.String(length=64), nullable=True))
    op.add_column('scheme_versions', sa.Column('status', sa.String(length=32), server_default='DRAFT', nullable=False))
    op.add_column('scheme_versions', sa.Column('effective_date', sa.Date(), nullable=True))
    op.add_column('scheme_versions', sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True))
    op.add_column('scheme_versions', sa.Column('supersedes_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_versions.id', ondelete='SET NULL'), nullable=True))
    op.add_column('scheme_versions', sa.Column('created_from_relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document_relationships.id', ondelete='SET NULL'), nullable=True))
    op.add_column('scheme_versions', sa.Column('canonical_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('scheme_versions', sa.Column('artifact_path', sa.String(length=512), nullable=True))
    op.add_column('scheme_versions', sa.Column('artifact_sha256', sa.String(length=64), nullable=True))

    op.create_index('ix_scheme_versions_status', 'scheme_versions', ['status'])
    op.create_index('ix_scheme_versions_source_document_id', 'scheme_versions', ['source_document_id'])
    op.create_index('ix_scheme_versions_supersedes_version_id', 'scheme_versions', ['supersedes_version_id'])

    # 2. Extend document_relationships
    op.add_column('document_relationships', sa.Column('detection_method', sa.String(length=32), server_default='DETERMINISTIC_METADATA', nullable=False))
    op.add_column('document_relationships', sa.Column('relationship_status', sa.String(length=32), server_default='CANDIDATE', nullable=False))
    op.add_column('document_relationships', sa.Column('effective_date', sa.Date(), nullable=True))
    op.add_column('document_relationships', sa.Column('evidence_text', sa.Text(), nullable=True))
    op.add_column('document_relationships', sa.Column('evidence_page', sa.Integer(), nullable=True))
    op.add_column('document_relationships', sa.Column('evidence_block_ids', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False))
    op.add_column('document_relationships', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    op.create_index('ix_doc_rel_status', 'document_relationships', ['relationship_status'])
    op.create_index('ix_doc_rel_method', 'document_relationships', ['detection_method'])

    # 3. Create scheme_change_sets
    op.create_table(
        'scheme_change_sets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schemes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('base_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('document_relationships.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='DETECTED', nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('publication_date', sa.Date(), nullable=True),
        sa.Column('changes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('critical_changes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('conflict_reason', sa.String(length=256), nullable=True),
        sa.Column('change_set_hash', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scheme_change_sets_scheme_id', 'scheme_change_sets', ['scheme_id'])
    op.create_index('ix_scheme_change_sets_base_version_id', 'scheme_change_sets', ['base_version_id'])
    op.create_index('ix_scheme_change_sets_source_document_id', 'scheme_change_sets', ['source_document_id'])
    op.create_index('ix_scheme_change_sets_status', 'scheme_change_sets', ['status'])
    op.create_index('ix_scheme_change_sets_hash', 'scheme_change_sets', ['change_set_hash'])

    # 4. Create scheme_change_items
    op.create_table(
        'scheme_change_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_set_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_change_sets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('field_path', sa.String(length=256), nullable=False),
        sa.Column('change_type', sa.String(length=32), nullable=False),
        sa.Column('old_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('risk_level', sa.String(length=32), server_default='NORMAL', nullable=False),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('clause_reference', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_scheme_change_items_change_set_id', 'scheme_change_items', ['change_set_id'])
    op.create_index('ix_scheme_change_items_field_path', 'scheme_change_items', ['field_path'])
    op.create_index('ix_scheme_change_items_risk_level', 'scheme_change_items', ['risk_level'])

    # 5. Create scheme_document_links
    op.create_table(
        'scheme_document_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schemes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('link_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='AUTO_LINKED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('scheme_id', 'document_id', 'link_type', name='uq_scheme_doc_link')
    )
    op.create_index('ix_scheme_doc_links_scheme_id', 'scheme_document_links', ['scheme_id'])
    op.create_index('ix_scheme_doc_links_document_id', 'scheme_document_links', ['document_id'])


def downgrade() -> None:
    op.drop_table('scheme_document_links')
    op.drop_table('scheme_change_items')
    op.drop_table('scheme_change_sets')

    op.drop_index('ix_doc_rel_method', table_name='document_relationships')
    op.drop_index('ix_doc_rel_status', table_name='document_relationships')
    op.drop_column('document_relationships', 'updated_at')
    op.drop_column('document_relationships', 'evidence_block_ids')
    op.drop_column('document_relationships', 'evidence_page')
    op.drop_column('document_relationships', 'evidence_text')
    op.drop_column('document_relationships', 'effective_date')
    op.drop_column('document_relationships', 'relationship_status')
    op.drop_column('document_relationships', 'detection_method')

    op.drop_index('ix_scheme_versions_supersedes_version_id', table_name='scheme_versions')
    op.drop_index('ix_scheme_versions_source_document_id', table_name='scheme_versions')
    op.drop_index('ix_scheme_versions_status', table_name='scheme_versions')
    op.drop_column('scheme_versions', 'artifact_sha256')
    op.drop_column('scheme_versions', 'artifact_path')
    op.drop_column('scheme_versions', 'canonical_data')
    op.drop_column('scheme_versions', 'created_from_relationship_id')
    op.drop_column('scheme_versions', 'supersedes_version_id')
    op.drop_column('scheme_versions', 'source_document_id')
    op.drop_column('scheme_versions', 'effective_date')
    op.drop_column('scheme_versions', 'status')
    op.drop_column('scheme_versions', 'version_label')
