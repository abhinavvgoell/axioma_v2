from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from axioma_api.contracts import JobStatus
from axioma_api.models import Job, JobEvent


MAX_JOB_ATTEMPTS = 2
DEFAULT_LEASE_SECONDS = 180


def claim_next_job(
    session: Session,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Job | None:
    """Atomically claim the oldest queued job; PostgreSQL workers skip one another's locks."""
    job = session.scalar(
        select(Job)
        .where(Job.status == JobStatus.QUEUED.value)
        .order_by(Job.created_at, Job.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None

    now = datetime.now(UTC)
    job.status = JobStatus.RUNNING.value
    job.progress_message = "Claimed by analysis worker"
    job.lease_owner = worker_id
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    job.attempt_count += 1
    job.updated_at = now
    session.add(JobEvent(job_id=job.id, status=job.status, message=job.progress_message))
    session.commit()
    session.refresh(job)
    return job


def reap_expired_jobs(session: Session) -> int:
    """Requeue expired work once, then fail it so a broken worker cannot loop forever."""
    now = datetime.now(UTC)
    expired = session.scalars(
        select(Job)
        .where(
            Job.status == JobStatus.RUNNING.value,
            Job.lease_expires_at.is_not(None),
            Job.lease_expires_at <= now,
        )
        .with_for_update(skip_locked=True)
    ).all()
    for job in expired:
        job.lease_owner = None
        job.lease_expires_at = None
        job.updated_at = now
        if job.attempt_count < MAX_JOB_ATTEMPTS:
            job.status = JobStatus.QUEUED.value
            job.progress_message = "Worker lease expired; queued for retry"
        else:
            job.status = JobStatus.FAILED.value
            job.progress_message = "Worker lease expired after the retry limit"
            job.error_code = "worker_lease_expired"
        session.add(JobEvent(job_id=job.id, status=job.status, message=job.progress_message))
    if expired:
        session.commit()
    return len(expired)
