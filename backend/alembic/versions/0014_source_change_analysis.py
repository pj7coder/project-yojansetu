"""0014_source_change_analysis

Revision ID: 0014_source_change_analysis
Revises: 0013_source_monitoring
Create Date: 2026-09-09 12:00:00.000000

"""
import logging
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.migration.0014")

revision: str = '0014_source_change_analysis'
down_revision: Union[str, None] = '0013_source_monitoring'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. source_change_analyses table
    op.create_table(
        'source_change_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_change_events.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('status', sa.String(length=32), server_default='ANALYSIS_CLAIMED', nullable=False),
        sa.Column('render_method', sa.String(length=32), server_default='HTTP', nullable=False),
        sa.Column('previous_snapshot_path', sa.String(length=512), nullable=True),
        sa.Column('current_snapshot_path', sa.String(length=512), nullable=True),
        sa.Column('cleaned_snapshot_path', sa.String(length=512), nullable=True),
        sa.Column('diff_summary_path', sa.String(length=512), nullable=True),
        sa.Column('diff_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('text_changes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('links_added_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('links_removed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('links_changed_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('numeric_changes_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('has_high_priority_change', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('relevant_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('uncertain_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('irrelevant_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('fetched_resources_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('ingested_documents_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message_safe', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_source_change_analyses_id', 'source_change_analyses', ['id'], unique=False)
    op.create_index('ix_source_change_analyses_change_event_id', 'source_change_analyses', ['change_event_id'], unique=True)
    op.create_index('ix_source_change_analyses_status', 'source_change_analyses', ['status'], unique=False)

    # 2. discovered_resources table
    op.create_table(
        'discovered_resources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_urls.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('normalized_url', sa.String(length=2048), nullable=False),
        sa.Column('anchor_text', sa.String(length=512), nullable=True),
        sa.Column('context_text', sa.Text(), nullable=True),
        sa.Column('resource_type', sa.String(length=32), server_default='PDF', nullable=False),
        sa.Column('discovery_reason', sa.String(length=64), server_default='NEW_LINK', nullable=False),
        sa.Column('relevance_status', sa.String(length=32), server_default='UNCERTAIN', nullable=False),
        sa.Column('relevance_reason', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('fetch_status', sa.String(length=32), server_default='PENDING', nullable=False),
        sa.Column('fetch_error', sa.Text(), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('change_event_id', 'normalized_url', name='uq_discovered_resource_event_url'),
    )
    op.create_index('ix_discovered_resources_id', 'discovered_resources', ['id'], unique=False)
    op.create_index('ix_discovered_resources_change_event_id', 'discovered_resources', ['change_event_id'], unique=False)
    op.create_index('ix_discovered_resources_source_url_id', 'discovered_resources', ['source_url_id'], unique=False)
    op.create_index('ix_discovered_resources_normalized_url', 'discovered_resources', ['normalized_url'], unique=False)
    op.create_index('ix_discovered_resources_resource_type', 'discovered_resources', ['resource_type'], unique=False)
    op.create_index('ix_discovered_resources_relevance_status', 'discovered_resources', ['relevance_status'], unique=False)
    op.create_index('ix_discovered_resources_fetch_status', 'discovered_resources', ['fetch_status'], unique=False)
    op.create_index('ix_discovered_resources_document_id', 'discovered_resources', ['document_id'], unique=False)
    op.create_index('ix_discovered_res_event_rel', 'discovered_resources', ['change_event_id', 'relevance_status'], unique=False)

    # 3. web_content_artifacts table
    op.create_table(
        'web_content_artifacts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_urls.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_event_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_change_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('source_url', sa.String(length=2048), nullable=False),
        sa.Column('cleaned_content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('cleaned_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=64), server_default='READY_FOR_WEB_CONTENT_PROCESSING', nullable=False),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_web_content_artifacts_id', 'web_content_artifacts', ['id'], unique=False)
    op.create_index('ix_web_content_artifacts_source_url_id', 'web_content_artifacts', ['source_url_id'], unique=False)
    op.create_index('ix_web_content_artifacts_change_event_id', 'web_content_artifacts', ['change_event_id'], unique=False)
    op.create_index('ix_web_content_artifacts_status', 'web_content_artifacts', ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('web_content_artifacts')
    op.drop_table('discovered_resources')
    op.drop_table('source_change_analyses')
