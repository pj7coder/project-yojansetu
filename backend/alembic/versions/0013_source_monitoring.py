"""0013_source_monitoring

Revision ID: 0013_source_monitoring
Revises: 0012_scheme_search_embeddings
Create Date: 2026-09-09 10:00:00.000000

"""
import logging
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.migration.0013")

revision: str = '0013_source_monitoring'
down_revision: Union[str, None] = '0012_scheme_search_embeddings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. source_urls table
    op.create_table(
        'source_urls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('sources.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('url_type', sa.String(length=64), server_default='SCHEME_PAGE', nullable=False),
        sa.Column('priority', sa.String(length=32), server_default='TIER_1', nullable=False),
        sa.Column('authority_level', sa.String(length=32), server_default='OFFICIAL_PORTAL', nullable=False),
        sa.Column('check_interval_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('crawl_allowed', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('strategy', sa.String(length=32), server_default='AUTO', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_source_urls_id', 'source_urls', ['id'], unique=False)
    op.create_index('ix_source_urls_source_id', 'source_urls', ['source_id'], unique=False)
    op.create_index('ix_source_urls_url', 'source_urls', ['url'], unique=False)
    op.create_index('ix_source_urls_priority', 'source_urls', ['priority'], unique=False)
    op.create_index('ix_source_urls_enabled_crawl', 'source_urls', ['enabled', 'crawl_allowed'], unique=False)

    # 2. source_monitor_states table
    op.create_table(
        'source_monitor_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_urls.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_change_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_check_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_http_status', sa.Integer(), nullable=True),
        sa.Column('etag', sa.String(length=256), nullable=True),
        sa.Column('last_modified', sa.String(length=256), nullable=True),
        sa.Column('content_length', sa.BigInteger(), nullable=True),
        sa.Column('content_type', sa.String(length=128), nullable=True),
        sa.Column('body_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('link_fingerprint', sa.String(length=64), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), server_default='0', nullable=False),
        sa.Column('consecutive_unchanged', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_interval_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('monitor_status', sa.String(length=32), server_default='NEVER_CHECKED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_source_monitor_states_id', 'source_monitor_states', ['id'], unique=False)
    op.create_index('ix_source_monitor_states_source_url_id', 'source_monitor_states', ['source_url_id'], unique=True)
    op.create_index('ix_source_monitor_states_next_check_at', 'source_monitor_states', ['next_check_at'], unique=False)
    op.create_index('ix_source_monitor_states_monitor_status', 'source_monitor_states', ['monitor_status'], unique=False)
    op.create_index('ix_source_monitor_due_query', 'source_monitor_states', ['next_check_at', 'monitor_status'], unique=False)

    # 3. source_monitor_runs table
    op.create_table(
        'source_monitor_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_urls.id', ondelete='CASCADE'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('http_method', sa.String(length=16), server_default='GET', nullable=False),
        sa.Column('http_status', sa.Integer(), nullable=True),
        sa.Column('result', sa.String(length=32), nullable=False),
        sa.Column('change_signals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=False),
        sa.Column('response_bytes', sa.Integer(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message_safe', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_source_monitor_runs_id', 'source_monitor_runs', ['id'], unique=False)
    op.create_index('ix_source_monitor_runs_source_url_id', 'source_monitor_runs', ['source_url_id'], unique=False)
    op.create_index('ix_source_monitor_runs_result', 'source_monitor_runs', ['result'], unique=False)
    op.create_index('ix_source_monitor_runs_created_at', 'source_monitor_runs', ['created_at'], unique=False)

    # 4. source_change_events table
    op.create_table(
        'source_change_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_url_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_urls.id', ondelete='CASCADE'), nullable=False),
        sa.Column('monitor_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('source_monitor_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_type', sa.String(length=32), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('previous_state_reference', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_state_reference', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('idempotency_key', sa.String(length=128), nullable=False),
        sa.Column('processing_status', sa.String(length=32), server_default='PENDING_ANALYSIS', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_source_change_events_id', 'source_change_events', ['id'], unique=False)
    op.create_index('ix_source_change_events_source_url_id', 'source_change_events', ['source_url_id'], unique=False)
    op.create_index('ix_source_change_events_monitor_run_id', 'source_change_events', ['monitor_run_id'], unique=False)
    op.create_index('ix_source_change_events_idempotency_key', 'source_change_events', ['idempotency_key'], unique=True)
    op.create_index('ix_source_change_events_processing_status', 'source_change_events', ['processing_status'], unique=False)


def downgrade() -> None:
    op.drop_table('source_change_events')
    op.drop_table('source_monitor_runs')
    op.drop_table('source_monitor_states')
    op.drop_table('source_urls')
