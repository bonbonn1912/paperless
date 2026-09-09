from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.models.base import generate_uuid, utc_now
from app.models.document import Document
from app.models.job import Job, JobEvent
from app.models.schedule import Schedule

logger = logging.getLogger("scheduler")


class SchedulerService:
    def calculate_next_run(
        self,
        local_time_str: str,
        weekdays: List[int],
        tz_name: str = "Europe/Berlin",
        after_dt: Optional[datetime] = None,
    ) -> datetime:
        """Calculate next execution datetime respecting timezone and daylight saving time."""
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")

        now_utc = after_dt or utc_now()
        now_local = now_utc.astimezone(tz)

        hour, minute = map(int, local_time_str.split(":"))

        # Look forward up to 8 days to find the next matching weekday and time
        for day_offset in range(8):
            candidate_date = (now_local + timedelta(days=day_offset)).date()
            candidate_local = datetime(
                candidate_date.year,
                candidate_date.month,
                candidate_date.day,
                hour,
                minute,
                tzinfo=tz,
            )
            # Check weekday (Python weekday(): 0=Mon, 6=Sun)
            if candidate_local.weekday() in weekdays:
                if candidate_local > now_local:
                    return candidate_local.astimezone(timezone.utc)

        # Fallback: tomorrow at target time
        fallback = (now_local + timedelta(days=1)).replace(hour=hour, minute=minute, second=0)
        return fallback.astimezone(timezone.utc)

    def check_due_schedules(self, db: Session) -> None:
        """Find and trigger due schedules."""
        now = utc_now()
        due_schedules = (
            db.query(Schedule)
            .filter(
                Schedule.is_active == True,
                Schedule.mode == "scheduled",
                Schedule.next_run_at <= now,
            )
            .all()
        )

        for sched in due_schedules:
            try:
                self.trigger_schedule(db, sched)
            except Exception as e:
                logger.error("Error triggering schedule %s: %s", sched.id, e)

    def trigger_schedule(self, db: Session, sched: Schedule) -> Optional[Job]:
        """Trigger a schedule execution and compute its next run time."""
        now = utc_now()
        run_id = generate_uuid()

        job = Job(
            owner=sched.owner,
            document_id=None,
            run_id=run_id,
            job_type=sched.job_type,
            state="queued",
            step="queued",
            priority=5,  # Scheduled tasks have priority 5
            schedule_id=sched.id,
        )
        db.add(job)
        db.flush()

        db.add(JobEvent(
            job_id=job.id,
            from_state="none",
            to_state="queued",
            step="queued",
            reason=f"Triggered by schedule {sched.id} ({sched.job_type})",
        ))

        from app.models.base import to_utc
        sched.last_run_at = now
        next_run_utc = to_utc(sched.next_run_at)
        base_dt = max(now, next_run_utc or now) + timedelta(minutes=1)
        sched.next_run_at = self.calculate_next_run(
            local_time_str=sched.local_time,
            weekdays=sched.weekdays,
            tz_name=sched.timezone,
            after_dt=base_dt,
        )
        db.commit()
        logger.info("Schedule %s triggered job %s; next run at %s", sched.id, job.id, sched.next_run_at)
        return job

    def preview_schedule(self, db: Session, sched: Schedule) -> Dict[str, Any]:
        """Return preview metrics of affected documents for the schedule."""
        q = db.query(Document).filter(
            Document.owner == sched.owner,
            Document.deleted_at.is_(None),
        )

        filter_cfg = sched.filter_config or {}
        if filter_cfg.get("folder_id"):
            from app.models.folder import DocumentFolder
            q = q.join(DocumentFolder, DocumentFolder.document_id == Document.id).filter(
                DocumentFolder.folder_id == filter_cfg["folder_id"]
            )

        if filter_cfg.get("tag_ids"):
            from app.models.tag import DocumentTag
            q = q.join(DocumentTag, DocumentTag.document_id == Document.id).filter(
                DocumentTag.tag_id.in_(filter_cfg["tag_ids"])
            )

        count = q.distinct().count()
        return {
            "schedule_id": sched.id,
            "affected_documents_count": count,
            "next_run_at": sched.next_run_at,
        }


scheduler_service = SchedulerService()
