"""0010_evidence_verification

Revision ID: 0010_evidence_verification
Revises: 0009_validation_engine
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic. Length must be <= 32 chars for alembic_version table
revision: str = '0010_evidence_verification'
down_revision: Union[str, None] = '0009_validation_engine'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create evidence_verification_runs table
    op.create_table(
        'evidence_verification_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for evidence verification run'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False, comment='Associated canonical scheme draft identifier'),
        sa.Column('canonical_artifact_sha256', sa.String(length=64), nullable=False, comment='SHA-256 checksum of canonical.json draft verified in this run'),
        sa.Column('status', sa.String(length=40), nullable=False, server_default='VERIFYING', comment='VERIFYING, EVIDENCE_VERIFIED, EVIDENCE_REVIEW_REQUIRED, EVIDENCE_VERIFICATION_FAILED, STALE'),
        sa.Column('facts_total', sa.Integer(), nullable=False, server_default='0', comment='Total atomic facts evaluated in this run'),
        sa.Column('facts_supported', sa.Integer(), nullable=False, server_default='0', comment='Total facts verified as SUPPORTED'),
        sa.Column('facts_contradicted', sa.Integer(), nullable=False, server_default='0', comment='Total facts verified as CONTRADICTED'),
        sa.Column('facts_insufficient', sa.Integer(), nullable=False, server_default='0', comment='Total facts classified as NOT_ENOUGH_EVIDENCE'),
        sa.Column('facts_failed', sa.Integer(), nullable=False, server_default='0', comment='Total facts that failed verification due to technical or model errors'),
        sa.Column('critical_issues_count', sa.Integer(), nullable=False, server_default='0', comment='Number of critical-risk facts with CONTRADICTED or NOT_ENOUGH_EVIDENCE'),
        sa.Column('verifier_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Version of verification engine'),
        sa.Column('prompt_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Evidence verification prompt template version'),
        sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0', comment='Specification version of verification schema'),
        sa.Column('artifact_path', sa.String(length=500), nullable=True, comment='Storage path to verification run artifact JSON'),
        sa.Column('diagnostics', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Summary diagnostic metrics, risk breakdowns, and timing breakdown'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, comment='Execution start timestamp'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True, comment='Execution finish timestamp'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='End-to-end verification latency in milliseconds'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_evidence_verification_runs_id', 'evidence_verification_runs', ['id'])
    op.create_index('ix_evidence_verification_runs_scheme_draft_id', 'evidence_verification_runs', ['scheme_draft_id'])
    op.create_index('ix_evidence_verification_runs_status', 'evidence_verification_runs', ['status'])
    op.create_index('ix_evid_verif_runs_draft_status', 'evidence_verification_runs', ['scheme_draft_id', 'status'])
    op.create_index('ix_evid_verif_runs_draft_hash', 'evidence_verification_runs', ['scheme_draft_id', 'canonical_artifact_sha256'])

    # 2. Create fact_verifications table
    op.create_table(
        'fact_verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, comment='Unique identifier for fact verification record'),
        sa.Column('verification_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('evidence_verification_runs.id', ondelete='CASCADE'), nullable=False, comment='Associated evidence verification run'),
        sa.Column('scheme_draft_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('scheme_drafts.id', ondelete='CASCADE'), nullable=False, comment='Associated canonical scheme draft'),
        sa.Column('fact_id', sa.String(length=64), nullable=False, comment='Stable atomic fact identifier, e.g. FACT-001'),
        sa.Column('field_path', sa.String(length=255), nullable=False, comment='Dot-notation path to target canonical field'),
        sa.Column('fact_type', sa.String(length=50), nullable=False, comment='ELIGIBILITY, LOGICAL_CONNECTOR, EXCLUSION, BENEFIT, DOCUMENT, APPLICATION, DATE, DEFINITION, IDENTITY'),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='NORMAL', comment='CRITICAL, HIGH, NORMAL, LOW'),
        sa.Column('statement', sa.Text(), nullable=False, comment='Human-readable fact assertion being challenged against evidence'),
        sa.Column('canonical_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured dictionary of the canonical claim values'),
        sa.Column('evidence_text', sa.Text(), nullable=True, comment='Verbatim text of the supporting government evidence'),
        sa.Column('result', sa.String(length=30), nullable=False, comment='SUPPORTED, CONTRADICTED, NOT_ENOUGH_EVIDENCE, VERIFICATION_FAILED, VERIFICATION_BLOCKED'),
        sa.Column('reason_code', sa.String(length=64), nullable=False, comment='Stable reason code'),
        sa.Column('explanation', sa.Text(), nullable=True, comment='Concise explanation for debugging and human review'),
        sa.Column('verification_method', sa.String(length=30), nullable=False, server_default='DETERMINISTIC', comment='DETERMINISTIC, LLM, COMBINED'),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='List of evidence IDs cited by this fact'),
        sa.Column('ocr_risk', sa.Boolean(), nullable=False, server_default=sa.false(), comment='True if supporting evidence originates from low-confidence OCR'),
        sa.Column('model_provider', sa.String(length=50), nullable=True, comment='LLM provider used (e.g. ollama)'),
        sa.Column('model_name', sa.String(length=50), nullable=True, comment='Model identifier (e.g. llama3.2:3b)'),
        sa.Column('duration_ms', sa.Integer(), nullable=True, comment='Verification latency for this individual fact'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('ix_fact_verifications_id', 'fact_verifications', ['id'])
    op.create_index('ix_fact_verifications_verification_run_id', 'fact_verifications', ['verification_run_id'])
    op.create_index('ix_fact_verifications_scheme_draft_id', 'fact_verifications', ['scheme_draft_id'])
    op.create_index('ix_fact_verifications_fact_id', 'fact_verifications', ['fact_id'])
    op.create_index('ix_fact_verifications_result', 'fact_verifications', ['result'])
    op.create_index('ix_fact_verif_draft_result', 'fact_verifications', ['scheme_draft_id', 'result'])
    op.create_index('ix_fact_verif_draft_risk', 'fact_verifications', ['scheme_draft_id', 'risk_level'])
    op.create_index('ix_fact_verif_draft_type', 'fact_verifications', ['scheme_draft_id', 'fact_type'])


def downgrade() -> None:
    op.drop_table('fact_verifications')
    op.drop_table('evidence_verification_runs')
