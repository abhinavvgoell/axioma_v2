from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("owner_key", "idempotency_key", name="uq_job_idempotency"),
        Index("ix_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_key: Mapped[str] = mapped_column(String(80), nullable=False, default="local")
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(300))
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    events: Mapped[list["JobEvent"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobEvent(Base):
    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job_id_id", "job_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    job: Mapped[Job] = relationship(back_populates="events")


class EvidenceClaimRecord(Base):
    __tablename__ = "evidence_claims"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('executed', 'static', 'statistical', 'model', 'unverified')",
            name="ck_evidence_claim_type",
        ),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low')", name="ck_evidence_claim_confidence"
        ),
        Index("ix_evidence_claims_job_id", "job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifact_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class TestCaseRecord(Base):
    __tablename__ = "test_cases"
    __table_args__ = (
        CheckConstraint("outcome IN ('passed', 'failed', 'skipped')", name="ck_test_case_outcome"),
        Index("ix_test_cases_job_id", "job_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class InputSnapshotRecord(Base):
    __tablename__ = "input_snapshots"
    __table_args__ = (
        UniqueConstraint("job_id", "snapshot_key", name="uq_input_snapshot_job_key"),
        Index("ix_input_snapshots_job_origin", "job_id", "origin"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    source_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("input_snapshots.id", ondelete="SET NULL")
    )
    snapshot_key: Mapped[str] = mapped_column(String(160), nullable=False)
    origin: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    problem_pack_identity: Mapped[dict | None] = mapped_column(JSON)
    input_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    generator_version: Mapped[str | None] = mapped_column(String(80))
    generator_artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    seed: Mapped[int | None] = mapped_column(Integer)
    size_path: Mapped[str | None] = mapped_column(String(120))
    strategy: Mapped[str | None] = mapped_column(String(80))
    runtime_configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class ComplexityRecord(Base):
    __tablename__ = "complexity_results"
    __table_args__ = (
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="ck_complexity_confidence"),
    )

    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    estimate: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[str] = mapped_column(String(8), nullable=False)
    methods_disagree: Mapped[bool] = mapped_column(nullable=False, default=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class VerificationGateRecord(Base):
    __tablename__ = "verification_gates"
    __table_args__ = (
        UniqueConstraint("job_id", "gate_order", name="uq_verification_gate_order"),
        CheckConstraint(
            "state IN ('passed', 'failed', 'not_run')", name="ck_verification_gate_state"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    gate_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(8), nullable=False)
    evidence_claim_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
