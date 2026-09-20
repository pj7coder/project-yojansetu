"""0012_scheme_search_and_embeddings

Revision ID: 0012_scheme_search_and_embeddings
Revises: 0011_human_review
Create Date: 2026-09-08 10:00:00.000000

"""
import logging
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.migration.0012")

revision: str = '0012_scheme_search_embeddings'
down_revision: Union[str, None] = '0011_human_review'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Attempt enabling pgvector extension safely without aborting transaction
    conn = op.get_bind()
    vector_available = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    ).scalar()
    if vector_available:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector;"))
        logger.info("Successfully enabled PostgreSQL vector extension")
    else:
        logger.warning("PostgreSQL pgvector extension is not installed in pg_available_extensions. Graceful fallback will be used.")

    # 2. Create scheme_search_metadata table
    op.create_table(
        'scheme_search_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique search metadata ID'),
        sa.Column('scheme_id', sa.String(length=64), nullable=False, unique=True, comment='Canonical scheme identifier'),
        sa.Column('scheme_name', sa.String(length=500), nullable=False, comment='Official scheme name'),
        sa.Column('scheme_name_hi', sa.String(length=500), nullable=True, comment='Hindi official scheme name'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True, server_default='Rajasthan'),
        sa.Column('districts', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('rural_urban', sa.String(length=20), nullable=False, server_default='BOTH'),
        sa.Column('scheme_origin', sa.String(length=40), nullable=False, server_default='RAJASTHAN_STATE'),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('beneficiary_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('occupation_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('search_text', sa.Text(), nullable=False),
        sa.Column('search_text_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_scheme_search_metadata_scheme_id', 'scheme_search_metadata', ['scheme_id'])
    op.create_index('ix_scheme_search_metadata_state', 'scheme_search_metadata', ['state'])
    op.create_index('ix_scheme_search_metadata_rural_urban', 'scheme_search_metadata', ['rural_urban'])
    op.create_index('ix_scheme_search_metadata_scheme_origin', 'scheme_search_metadata', ['scheme_origin'])
    op.create_index('ix_scheme_search_metadata_category', 'scheme_search_metadata', ['category'])
    op.create_index('ix_scheme_search_metadata_valid_dates', 'scheme_search_metadata', ['valid_from', 'valid_until'])
    op.create_index('ix_scheme_search_metadata_active_verified', 'scheme_search_metadata', ['is_active', 'is_verified'])
    op.create_index('ix_scheme_search_metadata_hash', 'scheme_search_metadata', ['search_text_hash'])
    op.create_index('ix_scheme_search_districts_gin', 'scheme_search_metadata', ['districts'], postgresql_using='gin')
    op.create_index('ix_scheme_search_beneficiaries_gin', 'scheme_search_metadata', ['beneficiary_tags'], postgresql_using='gin')
    op.create_index('ix_scheme_search_occupations_gin', 'scheme_search_metadata', ['occupation_tags'], postgresql_using='gin')

    # 3. Create scheme_embeddings table
    op.create_table(
        'scheme_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique embedding record ID'),
        sa.Column('scheme_id', sa.String(length=64), nullable=False, comment='Associated scheme identifier'),
        sa.Column('embedding_model', sa.String(length=100), nullable=False, comment='Model name used for embedding'),
        sa.Column('embedding_version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('search_text_hash', sa.String(length=64), nullable=False, comment='Hash of input text'),
        sa.Column('embedding', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Normalized vector coordinates'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_scheme_embeddings_scheme_id', 'scheme_embeddings', ['scheme_id'])
    op.create_index('ix_scheme_embeddings_hash', 'scheme_embeddings', ['search_text_hash'])
    op.create_index('ix_scheme_embeddings_model', 'scheme_embeddings', ['scheme_id', 'embedding_model'])


def downgrade() -> None:
    op.drop_table('scheme_embeddings')
    op.drop_table('scheme_search_metadata')
