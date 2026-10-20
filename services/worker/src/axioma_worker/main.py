import logging
import os
import signal
import threading
import uuid

from axioma_api.database import SessionLocal
from axioma_api.queue import reap_expired_jobs
from axioma_worker.runtime import worker_iteration
from axioma_worker.sandbox import DockerSandbox


logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("axioma.worker")


def main() -> None:
    worker_id = os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:12]}")
    poll_seconds = float(os.getenv("WORKER_POLL_SECONDS", "1"))
    stopping = threading.Event()

    def request_stop(_signum: int, _frame: object) -> None:
        stopping.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    sandbox = DockerSandbox()
    logger.info("Worker %s started", worker_id)

    while not stopping.is_set():
        try:
            did_work = worker_iteration(SessionLocal, worker_id, sandbox)
        except Exception:
            logger.exception("Worker iteration failed")
            with SessionLocal() as session:
                reap_expired_jobs(session)
            did_work = False
        if not did_work:
            stopping.wait(poll_seconds)

    logger.info("Worker %s stopped", worker_id)


if __name__ == "__main__":
    main()
