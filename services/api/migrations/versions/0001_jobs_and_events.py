"""Create initial jobs, events, and evidence-ledger tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_jobs_events"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("owner_key", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128)),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("progress_message", sa.String(length=300)),
        sa.Column("lease_owner", sa.String(length=100)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_key", "idempotency_key", name="uq_job_idempotency"),
    )
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"])
    op.create_table(
        "job_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_events_job_id_id", "job_events", ["job_id", "id"])
    op.create_table(
        "evidence_claims",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("evidence_type", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("artifact_ids", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "evidence_type IN ('executed', 'static', 'statistical', 'model', 'unverified')",
            name="ck_evidence_claim_type",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')", name="ck_evidence_claim_confidence"
        ),
    )
    op.create_index("ix_evidence_claims_job_id", "evidence_claims", ["job_id"])
    op.create_table(
        "test_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed', 'skipped')", name="ck_test_case_outcome"
        ),
    )
    op.create_index("ix_test_cases_job_id", "test_cases", ["job_id"])
    op.create_table(
        "complexity_results",
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("method", sa.String(length=80), nullable=False),
        sa.Column("estimate", sa.String(length=120), nullable=False),
        sa.Column("confidence", sa.String(length=8), nullable=False),
        sa.Column("methods_disagree", sa.Boolean(), nullable=False),
        sa.Column("explanation", sa.Text()),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')", name="ck_complexity_confidence"
        ),
    )
    op.create_table(
        "verification_gates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=36),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gate_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("evidence_claim_ids", sa.JSON(), nullable=False),
        sa.UniqueConstraint("job_id", "gate_order", name="uq_verification_gate_order"),
        sa.CheckConstraint(
            "state IN ('passed', 'failed', 'not_run')", name="ck_verification_gate_state"
        ),
    )


def downgrade() -> None:
    op.drop_table("verification_gates")
    op.drop_table("complexity_results")
    op.drop_index("ix_test_cases_job_id", table_name="test_cases")
    op.drop_table("test_cases")
    op.drop_index("ix_evidence_claims_job_id", table_name="evidence_claims")
    op.drop_table("evidence_claims")
    op.drop_index("ix_job_events_job_id_id", table_name="job_events")
    op.drop_table("job_events")
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_table("jobs")
