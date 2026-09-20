"""0016_admin_ops_heartbeats

Revision ID: 0016_admin_ops_heartbeats
Revises: 0015_scheme_versioning
Create Date: 2026-09-10 12:00:00.000000

"""
import logging
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

logger = logging.getLogger("alembic.migration.0016")

revision: str = '0016_admin_ops_heartbeats'
down_revision: Union[str, None] = '0015_scheme_versioning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create worker_heartbeats table
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('worker_type', sa.String(length=64), nullable=False),
        sa.Column('worker_instance_id', sa.String(length=128), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('status', sa.String(length=32), server_default='HEALTHY', nullable=False),
        sa.Column('metadata_safe', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('worker_type', 'worker_instance_id', name='uq_worker_heartbeats_type_instance'),
    )
    op.create_index('ix_worker_heartbeats_type', 'worker_heartbeats', ['worker_type'])
    op.create_index('ix_worker_heartbeats_instance', 'worker_heartbeats', ['worker_instance_id'])
    op.create_index('ix_worker_heartbeats_last_seen', 'worker_heartbeats', ['last_seen_at'])
    op.create_index('ix_worker_heartbeats_status', 'worker_heartbeats', ['status'])
    op.create_index('ix_worker_heartbeats_type_seen', 'worker_heartbeats', ['worker_type', 'last_seen_at'])

    # 2. Create admin_operation_events table
    op.create_table(
        'admin_operation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('actor_id', sa.String(length=64), server_default='DEV_REVIEWER', nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('target_type', sa.String(length=64), nullable=False),
        sa.Column('target_id', sa.String(length=128), nullable=True),
        sa.Column('metadata_safe', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_admin_op_actor', 'admin_operation_events', ['actor_id'])
    op.create_index('ix_admin_op_action', 'admin_operation_events', ['action_type'])
    op.create_index('ix_admin_op_target_type', 'admin_operation_events', ['target_type'])
    op.create_index('ix_admin_op_target_id', 'admin_operation_events', ['target_id'])
    op.create_index('ix_admin_op_created', 'admin_operation_events', ['created_at'])
    op.create_index('ix_admin_op_action_created', 'admin_operation_events', ['action_type', 'created_at'])


def downgrade() -> None:
    op.drop_table('admin_operation_events')
    op.drop_table('worker_heartbeats')
