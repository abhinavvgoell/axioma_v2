import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from axioma_api.contracts import JobCreate, JobMode
from axioma_api.jobs import create_job
from axioma_api.models import Job
from axioma_api.queue import claim_next_job


@pytest.mark.skipif(
    not os.getenv("AXIOMA_TEST_DATABASE_URL"),
    reason="set AXIOMA_TEST_DATABASE_URL to run PostgreSQL integration checks",
)
def test_postgres_worker_skips_a_locked_queued_job() -> None:
    engine = create_engine(os.environ["AXIOMA_TEST_DATABASE_URL"])

    def session_factory() -> Session:
        return Session(engine, expire_on_commit=False)

    prefix = f"postgres-queue-{uuid4()}"
    job_ids: list[str] = []

    try:
        with session_factory() as session:
            for index in range(2):
                job, _ = create_job(
                    session,
                    JobCreate(
                        mode=JobMode.DSA_ANALYSIS,
                        language="python",
                        input={"code": "pass"},
                        idempotency_key=f"{prefix}-{index}",
                    ),
                )
                job_ids.append(job.id)

        with session_factory() as lock_holder, session_factory() as worker:
            locked_job = lock_holder.scalar(
                select(Job)
                .where(Job.id.in_(job_ids))
                .order_by(Job.created_at, Job.id)
                .limit(1)
                .with_for_update()
            )
            assert locked_job is not None

            claimed = claim_next_job(worker, "postgres-worker")

            assert claimed is not None
            assert claimed.id != locked_job.id
    finally:
        with session_factory() as cleanup:
            for job in cleanup.scalars(select(Job).where(Job.id.in_(job_ids))).all():
                cleanup.delete(job)
            cleanup.commit()
        engine.dispose()
