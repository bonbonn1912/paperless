from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db.session import get_db
from app.models.job import Job, JobEvent
from app.schemas.job import JobEventResponse, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=List[JobResponse])
def list_jobs(
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[JobResponse]:
    jobs = (
        db.query(Job)
        .filter(Job.owner == user)
        .order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [JobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = db.query(Job).filter(Job.id == job_id, Job.owner == user).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobResponse.model_validate(job)


@router.get("/{job_id}/events", response_model=List[JobEventResponse])
def get_job_events(
    job_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> List[JobEventResponse]:
    job = db.query(Job).filter(Job.id == job_id, Job.owner == user).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    events = db.query(JobEvent).filter(JobEvent.job_id == job_id).order_by(JobEvent.id).all()
    return [JobEventResponse.model_validate(e) for e in events]


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id, Job.owner == user).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if job.state in ("succeeded", "failed", "cancelled"):
        return {"message": f"Job already in terminal state {job.state}"}

    old_state = job.state
    if job.state == "running":
        job.state = "cancelling"
    else:
        job.state = "cancelled"

    db.add(JobEvent(
        job_id=job.id,
        from_state=old_state,
        to_state=job.state,
        step=job.step,
        reason="User requested cancellation",
    ))
    db.commit()
    return {"message": "Job cancellation initiated", "state": job.state}


@router.post("/{job_id}/retry")
def retry_job(
    job_id: str,
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> dict:
    job = db.query(Job).filter(Job.id == job_id, Job.owner == user).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    import uuid
    new_job = Job(
        owner=user,
        document_id=job.document_id,
        run_id=str(uuid.uuid4()),
        job_type=job.job_type,
        state="queued",
        step="queued",
        priority=8,
    )
    db.add(new_job)
    db.commit()
    return {"message": "Job re-queued for execution", "job_id": new_job.id}
