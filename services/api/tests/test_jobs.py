from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from axioma_api.contracts import JobCreate, JobMode, JobStatus
from axioma_api.jobs import create_job, transition_job
from axioma_api.models import Base, JobEvent


def make_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_job_creation_is_idempotent_and_records_initial_event() -> None:
    with make_session() as session:
        request = JobCreate(
            mode=JobMode.DSA_ANALYSIS,
            language="python",
            input={"code": "pass"},
            idempotency_key="same-request",
        )
        first, created = create_job(session, request)
        second, created_again = create_job(session, request)

        assert created is True
        assert created_again is False
        assert second.id == first.id
        assert len(session.query(JobEvent).filter_by(job_id=first.id).all()) == 1


def test_job_state_machine_rejects_terminal_transition() -> None:
    with make_session() as session:
        job, _ = create_job(
            session,
            JobCreate(mode=JobMode.DSA_ANALYSIS, language="java", input={"code": "class Main {}"}),
        )
        transition_job(session, job, JobStatus.CANCELLED, "Cancelled by user")

        try:
            transition_job(session, job, JobStatus.RUNNING, "Worker started")
        except ValueError as exc:
            assert "Invalid job transition" in str(exc)
        else:
            raise AssertionError("terminal job accepted a transition")
