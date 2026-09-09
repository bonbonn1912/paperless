from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from typing import Optional
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.models.job import Job
from app.processing.pipeline import PipelineExecutionError, pipeline
from app.processing.queue import job_queue
from app.processing.scheduler import scheduler_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Worker] %(message)s")
logger = logging.getLogger("worker")

_stop_event = threading.Event()


def signal_handler(signum: int, frame: object) -> None:
    logger.info("Received termination signal. Shutting down worker gracefully...")
    _stop_event.set()


class Worker:
    def __init__(self) -> None:
        self.current_job_id: Optional[str] = None
        self.current_claim_token: Optional[str] = None

    def run(self) -> None:
        logger.info("Starting Paperless background worker (HEAVY_JOB_CONCURRENCY=1)...")
        init_db()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        last_scheduler_check = 0.0

        while not _stop_event.is_set():
            now = time.time()
            # Check scheduler every 30 seconds
            if now - last_scheduler_check > 30.0:
                with SessionLocal() as db:
                    scheduler_service.check_due_schedules(db)
                last_scheduler_check = now

            # Claim next job from SQLite queue
            with SessionLocal() as db:
                claimed = job_queue.claim_next_job(db)

            if not claimed:
                # Queue empty, idle sleep
                time.sleep(1.0)
                continue

            job_id, claim_token = claimed
            self.current_job_id = job_id
            self.current_claim_token = claim_token
            logger.info("Claimed job %s with token %s", job_id, claim_token[:6])

            # Start heartbeat timer thread
            hb_stop = threading.Event()
            hb_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(job_id, claim_token, hb_stop),
                daemon=True,
            )
            hb_thread.start()

            try:
                with SessionLocal() as db:
                    job = db.query(Job).filter(Job.id == job_id).first()
                    if job:
                        if job.job_type in ("base_pipeline", "high_res_ocr"):
                            pipeline.execute_base_pipeline(
                                db,
                                job,
                                claim_token,
                                heartbeat_callback=lambda: self._do_single_heartbeat(job_id, claim_token),
                            )
                        elif job.job_type == "reindex":
                            from app.services.search import search_service
                            if job.document_id:
                                search_service.update_document_index(db, job.document_id, job.owner)
                            job.step = "succeeded"

                        job_queue.mark_succeeded(db, job_id, claim_token)
                        logger.info("Job %s succeeded", job_id)

            except PipelineExecutionError as e:
                logger.error("Job %s failed with code %s: %s", job_id, e.code, e.message)
                with SessionLocal() as db:
                    job_queue.mark_failed(db, job_id, claim_token, e.code, e.message)
            except Exception as e:
                logger.exception("Unexpected error executing job %s: %s", job_id, e)
                with SessionLocal() as db:
                    job_queue.mark_failed(db, job_id, claim_token, "unexpected_error", str(e))
            finally:
                hb_stop.set()
                hb_thread.join(timeout=2.0)
                self.current_job_id = None
                self.current_claim_token = None

        logger.info("Worker stopped cleanly.")

    def _heartbeat_loop(self, job_id: str, claim_token: str, stop_event: threading.Event) -> None:
        while not stop_event.wait(timeout=10.0):
            self._do_single_heartbeat(job_id, claim_token)

    def _do_single_heartbeat(self, job_id: str, claim_token: str) -> None:
        try:
            with SessionLocal() as db:
                success = job_queue.heartbeat(db, job_id, claim_token)
                if not success:
                    logger.warning("Heartbeat failed for job %s (lease lost)", job_id)
        except Exception as e:
            logger.warning("Exception during heartbeat for job %s: %s", job_id, e)


def main() -> None:
    worker = Worker()
    worker.run()


if __name__ == "__main__":
    main()
