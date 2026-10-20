import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from axioma_api.contracts import JobCreate, JobStatus
from axioma_api.models import Job, JobEvent


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.FAILED},
    JobStatus.RUNNING: {
        JobStatus.QUEUED,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}


def canonical_hash(value: dict) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def request_fingerprint(request: JobCreate) -> str:
    return canonical_hash(
        {"mode": request.mode.value, "language": request.language, "input": request.input}
    )


def create_job(session: Session, request: JobCreate) -> tuple[Job, bool]:
    owner_key = "local"
    fingerprint = request_fingerprint(request)
    if request.idempotency_key:
        existing = session.scalar(
            select(Job).where(
                Job.owner_key == owner_key,
                Job.idempotency_key == request.idempotency_key,
            )
        )
        if existing:
            if existing.input_hash != fingerprint:
                raise ValueError("Idempotency-Key was already used for a different request")
            return existing, False

    now = datetime.now(UTC)
    job = Job(
        id=str(uuid4()),
        owner_key=owner_key,
        idempotency_key=request.idempotency_key,
        mode=request.mode.value,
        language=request.language,
        status=JobStatus.QUEUED.value,
        input_hash=fingerprint,
        input_payload=request.input,
        progress_message="Waiting for an analysis worker",
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    session.flush()
    session.add(JobEvent(job_id=job.id, status=job.status, message=job.progress_message))
    session.commit()
    return job, True


def transition_job(session: Session, job: Job, new_status: JobStatus, message: str) -> Job:
    current = JobStatus(job.status)
    if new_status not in ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"Invalid job transition: {current.value} -> {new_status.value}")
    job.status = new_status.value
    job.progress_message = message
    job.updated_at = datetime.now(UTC)
    session.add(JobEvent(job_id=job.id, status=job.status, message=message))
    session.commit()
    session.refresh(job)
    return job
