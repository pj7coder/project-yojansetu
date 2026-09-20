"""0001_initial_scheme_tables

Revision ID: 0001_initial_scheme_tables
Revises: 
Create Date: 2026-09-06 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001_initial_scheme_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Attempt to enable pgvector extension if available in PostgreSQL installation
    conn = op.get_bind()
    vector_available = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = :ext"),
        {"ext": "vector"},
    ).scalar()
    if vector_available:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Departments table
    op.create_table(
        'departments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=False),
        sa.Column('name_hi', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('official_website', sa.String(length=512), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_departments_code', 'departments', ['code'], unique=True)
    op.create_index('ix_departments_id', 'departments', ['id'], unique=False)

    # 3. Categories table
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(length=32), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=False),
        sa.Column('name_hi', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_categories_code', 'categories', ['code'], unique=True)
    op.create_index('ix_categories_id', 'categories', ['id'], unique=False)

    # 4. Sources table
    op.create_table(
        'sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('base_url', sa.String(length=512), nullable=False),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_type', sa.String(length=64), server_default='PORTAL', nullable=False),
        sa.Column('priority', sa.String(length=32), server_default='TIER_1', nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_sources_id', 'sources', ['id'], unique=False)
    op.create_index('ix_sources_department_id', 'sources', ['department_id'], unique=False)
    op.create_index('ix_sources_source_type', 'sources', ['source_type'], unique=False)
    op.create_index('ix_sources_priority', 'sources', ['priority'], unique=False)

    # 5. Schemes table
    op.create_table(
        'schemes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_code', sa.String(length=64), nullable=False),
        sa.Column('name_en', sa.String(length=255), nullable=False),
        sa.Column('name_hi', sa.String(length=255), nullable=True),
        sa.Column('short_name', sa.String(length=100), nullable=True),
        sa.Column('department_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('departments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), server_default='DRAFT', nullable=False),
        sa.Column('jurisdiction', sa.String(length=32), server_default='RAJASTHAN', nullable=False),
        sa.Column('scheme_origin', sa.String(length=32), server_default='UNKNOWN', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_schemes_id', 'schemes', ['id'], unique=False)
    op.create_index('ix_schemes_scheme_code', 'schemes', ['scheme_code'], unique=True)
    op.create_index('ix_schemes_status', 'schemes', ['status'], unique=False)
    op.create_index('ix_schemes_department_id', 'schemes', ['department_id'], unique=False)
    op.create_index('ix_schemes_category_id', 'schemes', ['category_id'], unique=False)
    op.create_index('ix_schemes_jurisdiction', 'schemes', ['jurisdiction'], unique=False)
    op.create_index('ix_schemes_scheme_origin', 'schemes', ['scheme_origin'], unique=False)

    # 6. Scheme Versions table
    op.create_table(
        'scheme_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scheme_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('schemes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=True),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('source_summary', sa.Text(), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('is_current', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('scheme_id', 'version_number', name='uq_scheme_version_number'),
    )
    op.create_index('ix_scheme_versions_id', 'scheme_versions', ['id'], unique=False)
    op.create_index('ix_scheme_versions_scheme_id', 'scheme_versions', ['scheme_id'], unique=False)
    op.create_index('ix_scheme_versions_is_current', 'scheme_versions', ['is_current'], unique=False)


def downgrade() -> None:
    op.drop_table('scheme_versions')
    op.drop_table('schemes')
    op.drop_table('sources')
    op.drop_table('categories')
    op.drop_table('departments')
