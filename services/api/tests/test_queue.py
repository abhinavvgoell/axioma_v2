from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from axioma_api.contracts import JobCreate, JobMode, JobStatus
from axioma_api.jobs import create_job
from axioma_api.models import Base
from axioma_api.queue import claim_next_job, reap_expired_jobs


def make_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_worker_claims_job_with_a_lease_and_reaper_retries_once() -> None:
    with make_session() as session:
        job, _ = create_job(
            session,
            JobCreate(mode=JobMode.DSA_ANALYSIS, language="python", input={"code": "pass"}),
        )
        claimed = claim_next_job(session, "worker-1", lease_seconds=1)
        assert claimed is not None
        assert claimed.id == job.id
        assert claimed.lease_owner == "worker-1"
        assert claimed.attempt_count == 1

        claimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        assert reap_expired_jobs(session) == 1
        session.refresh(claimed)
        assert claimed.status == JobStatus.QUEUED.value

        claimed = claim_next_job(session, "worker-2", lease_seconds=1)
        assert claimed is not None
        claimed.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
        assert reap_expired_jobs(session) == 1
        session.refresh(claimed)
        assert claimed.status == JobStatus.FAILED.value
        assert claimed.error_code == "worker_lease_expired"
