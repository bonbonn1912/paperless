from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from app.models.base import utc_now
from app.models.job import Job, JobEvent


class JobQueue:
    def __init__(self, lease_duration_seconds: int = 60, heartbeat_interval_seconds: int = 10):
        self.lease_duration = lease_duration_seconds
        self.heartbeat_interval = heartbeat_interval_seconds

    def claim_next_job(self, db: Session) -> Optional[Tuple[str, str]]:
        """
        Claim the next eligible job using a short transaction.
        Returns: (job_id, claim_token) or None.
        """
        now = utc_now()
        # Recover expired leases first
        self._recover_expired_leases(db, now)

        # Select next candidate
        job = (
            db.query(Job)
            .filter(
                Job.state.in_(["queued", "retry_wait"]),
                or_(Job.not_before.is_(None), Job.not_before <= now),
            )
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .with_for_update()
            .first()
        )

        if not job:
            return None

        claim_token = secrets.token_hex(16)
        job.state = "running"
        job.claim_token = claim_token
        job.lease_expires_at = now + timedelta(seconds=self.lease_duration)
        job.heartbeat_at = now
        job.attempts += 1

        db.add(JobEvent(
            job_id=job.id,
            from_state="queued",
            to_state="running",
            step=job.step,
            reason=f"Claimed with token {claim_token[:6]} (attempt {job.attempts})",
        ))
        db.commit()
        return job.id, claim_token

    def heartbeat(self, db: Session, job_id: str, claim_token: str) -> bool:
        """Extend lease for a running job."""
        now = utc_now()
        job = db.query(Job).filter(Job.id == job_id, Job.claim_token == claim_token, Job.state == "running").first()
        if not job:
            return False

        job.heartbeat_at = now
        job.lease_expires_at = now + timedelta(seconds=self.lease_duration)
        db.commit()
        return True

    def mark_succeeded(self, db: Session, job_id: str, claim_token: str) -> bool:
        job = db.query(Job).filter(Job.id == job_id, Job.claim_token == claim_token).first()
        if not job:
            return False

        job.state = "succeeded"
        job.step = "succeeded"
        job.claim_token = None
        job.lease_expires_at = None

        db.add(JobEvent(
            job_id=job.id,
            from_state="running",
            to_state="succeeded",
            step="succeeded",
            reason="Job completed successfully",
        ))
        db.commit()
        return True

    def mark_failed(self, db: Session, job_id: str, claim_token: str, error_code: str, error_message: str) -> bool:
        job = db.query(Job).filter(Job.id == job_id, Job.claim_token == claim_token).first()
        if not job:
            return False

        now = utc_now()
        job.error_code = error_code
        job.error_message = error_message[:500]

        if job.attempts < job.max_attempts and error_code not in ("corrupt_file", "unsupported_format", "cancelled"):
            # Exponential backoff: 10s, 20s, 40s
            backoff_seconds = 10 * (2 ** (job.attempts - 1))
            job.state = "retry_wait"
            job.not_before = now + timedelta(seconds=backoff_seconds)
            job.claim_token = None
            job.lease_expires_at = None

            db.add(JobEvent(
                job_id=job.id,
                from_state="running",
                to_state="retry_wait",
                step=job.step,
                reason=f"Failed with {error_code}: retry in {backoff_seconds}s",
            ))
        else:
            job.state = "failed"
            job.claim_token = None
            job.lease_expires_at = None

            db.add(JobEvent(
                job_id=job.id,
                from_state="running",
                to_state="failed",
                step=job.step,
                reason=f"Failed permanently: {error_code} - {error_message}",
            ))

        db.commit()
        return True

    def _recover_expired_leases(self, db: Session, now: datetime) -> None:
        """Reset jobs with expired worker leases to retry_wait."""
        expired = (
            db.query(Job)
            .filter(
                Job.state == "running",
                Job.lease_expires_at < now,
            )
            .all()
        )
        for job in expired:
            job.state = "retry_wait"
            job.not_before = now + timedelta(seconds=15)
            job.claim_token = None
            job.lease_expires_at = None
            db.add(JobEvent(
                job_id=job.id,
                from_state="running",
                to_state="retry_wait",
                step=job.step,
                reason="Lease expired (worker lost), scheduled for retry",
            ))
        if expired:
            db.commit()


job_queue = JobQueue()
