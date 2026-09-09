from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.job import Job
from app.models.schedule import Schedule
from app.processing.scheduler import scheduler_service
from app.schemas.schedule import (
    ScheduleCreate,
    SchedulePreviewResponse,
    ScheduleResponse,
    ScheduleUpdate,
)

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=List[ScheduleResponse])
def list_schedules(
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> List[ScheduleResponse]:
    scheds = db.query(Schedule).filter(Schedule.owner == user).all()
    return [ScheduleResponse.model_validate(s) for s in scheds]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ScheduleResponse)
def create_schedule(
    req: ScheduleCreate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    next_run = None
    if req.mode == "scheduled":
        next_run = scheduler_service.calculate_next_run(
            local_time_str=req.local_time,
            weekdays=req.weekdays,
            tz_name=req.timezone,
        )

    sched = Schedule(
        owner=user,
        job_type=req.job_type,
        filter_config=req.filter_config,
        mode=req.mode,
        weekdays=req.weekdays,
        local_time=req.local_time,
        timezone=req.timezone,
        window_minutes=req.window_minutes,
        limits=req.limits,
        next_run_at=next_run,
        is_active=True,
    )
    db.add(sched)
    db.commit()
    return ScheduleResponse.model_validate(sched)


@router.patch("/{schedule_id}", response_model=ScheduleResponse)
def update_schedule(
    schedule_id: str,
    update: ScheduleUpdate,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> ScheduleResponse:
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.owner == user).first()
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    if update.filter_config is not None:
        sched.filter_config = update.filter_config
    if update.mode is not None:
        sched.mode = update.mode
    if update.weekdays is not None:
        sched.weekdays = update.weekdays
    if update.local_time is not None:
        sched.local_time = update.local_time
    if update.timezone is not None:
        sched.timezone = update.timezone
    if update.window_minutes is not None:
        sched.window_minutes = update.window_minutes
    if update.limits is not None:
        sched.limits = update.limits
    if update.is_active is not None:
        sched.is_active = update.is_active

    if sched.mode == "scheduled" and sched.is_active:
        sched.next_run_at = scheduler_service.calculate_next_run(
            local_time_str=sched.local_time,
            weekdays=sched.weekdays,
            tz_name=sched.timezone,
        )
    else:
        sched.next_run_at = None

    db.commit()
    return ScheduleResponse.model_validate(sched)


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.owner == user).first()
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    db.delete(sched)
    db.commit()
    return {"message": "Schedule deleted"}


@router.post("/{schedule_id}/run-now")
def run_schedule_now(
    schedule_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.owner == user).first()
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    job = scheduler_service.trigger_schedule(db, sched)
    return {"message": "Schedule execution triggered", "job_id": job.id if job else None}


@router.post("/{schedule_id}/preview", response_model=SchedulePreviewResponse)
def preview_schedule(
    schedule_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> SchedulePreviewResponse:
    sched = db.query(Schedule).filter(Schedule.id == schedule_id, Schedule.owner == user).first()
    if not sched:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")

    preview_data = scheduler_service.preview_schedule(db, sched)
    return SchedulePreviewResponse(**preview_data)
