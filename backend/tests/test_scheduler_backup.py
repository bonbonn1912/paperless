from __future__ import annotations

import tempfile
from pathlib import Path
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.schedule import Schedule
from app.processing.scheduler import scheduler_service
from app.services.backup import backup_service


def test_scheduler_next_run_and_trigger(db_session: Session):
    owner = "user_sched"
    next_dt = scheduler_service.calculate_next_run("03:30", weekdays=[0, 1, 2, 3, 4, 5, 6], tz_name="Europe/Berlin")
    assert next_dt is not None

    sched = Schedule(
        owner=owner,
        job_type="high_res_ocr",
        local_time="03:30",
        weekdays=[0, 1, 2, 3, 4, 5, 6],
        timezone="Europe/Berlin",
        next_run_at=next_dt,
        is_active=True,
    )
    db_session.add(sched)
    db_session.commit()

    # Trigger
    job = scheduler_service.trigger_schedule(db_session, sched)
    assert job is not None
    assert job.job_type == "high_res_ocr"
    assert job.priority == 5
    from app.models.base import to_utc
    assert to_utc(sched.next_run_at) > to_utc(next_dt)


def test_sqlite_online_backup_and_restore():
    from app.db.session import init_db
    init_db()
    with tempfile.TemporaryDirectory() as tmp_backup_dir:
        backup_path = Path(tmp_backup_dir) / "backup_target"
        created_path = backup_service.create_backup(backup_path)
        assert created_path.exists()
        assert (created_path / "app.sqlite3").exists()
        assert (created_path / "manifest.json").exists()

        # Restore test
        backup_service.restore_backup(created_path)
