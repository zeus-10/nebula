# Transcoding API endpoints - trigger transcoding, check status, list jobs

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models import File, TranscodingJob
from app.worker import transcode_video_task

router = APIRouter()


# Pydantic models for request/response
class TranscodeRequest(BaseModel):
    file_id: int
    qualities: List[int] = [480, 720]  # Default to 480p and 720p


class TranscodeJobResponse(BaseModel):
    id: int
    file_id: int
    filename: str
    target_quality: int
    status: str
    progress: float
    output_path: Optional[str]
    output_size: Optional[int]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TranscodeStatusResponse(BaseModel):
    file_id: int
    filename: str
    original_size: int
    is_video: bool
    jobs: List[TranscodeJobResponse]
    available_qualities: List[int]


@router.post("/transcode")
def trigger_transcode(request: TranscodeRequest, db: Session = Depends(get_db)):
    """
    Trigger transcoding for a video file

    Creates transcoding jobs for each requested quality level.
    Jobs run in background via Celery worker.
    """
    # Validate file exists
    file = db.query(File).filter(File.id == request.file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail=f"File {request.file_id} not found")

    # Validate file is a video
    if not file.is_video():
        raise HTTPException(
            status_code=400,
            detail=f"File {request.file_id} is not a video. MIME type: {file.mime_type}"
        )

    # Validate requested qualities
    valid_qualities = [480, 720, 1080]
    for quality in request.qualities:
        if quality not in valid_qualities:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid quality: {quality}. Must be one of {valid_qualities}"
            )

    # Check for existing jobs (avoid duplicates)
    existing_jobs = db.query(TranscodingJob).filter(
        TranscodingJob.file_id == request.file_id,
        TranscodingJob.status.in_(["pending", "processing"])
    ).all()

    existing_qualities = {job.target_quality for job in existing_jobs}

    # Create new jobs
    created_jobs = []
    for quality in request.qualities:
        # Skip if already processing this quality
        if quality in existing_qualities:
            continue

        # Check if already transcoded
        if file.transcoded_variants and str(quality) in file.transcoded_variants:
            continue

        # Create job record
        job = TranscodingJob(
            file_id=request.file_id,
            target_quality=quality,
            status="pending",
            progress=0.0
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Queue Celery task
        task = transcode_video_task.delay(
            job_id=job.id,
            file_id=request.file_id,
            target_quality=quality
        )

        # Store task ID
        job.celery_task_id = task.id
        db.commit()

        created_jobs.append({
            "job_id": job.id,
            "quality": quality,
            "status": "queued",
            "celery_task_id": task.id
        })

    if not created_jobs:
        return {
            "message": "No new transcoding jobs created",
            "reason": "All requested qualities are already transcoded or in progress",
            "file_id": request.file_id,
            "existing_qualities": list(existing_qualities),
            "transcoded_qualities": list(file.transcoded_variants.keys()) if file.transcoded_variants else []
        }

    return {
        "message": f"Transcoding started for {len(created_jobs)} quality level(s)",
        "file_id": request.file_id,
        "jobs": created_jobs
    }


@router.get("/transcode/{file_id}", response_model=TranscodeStatusResponse)
def get_transcode_status(file_id: int, db: Session = Depends(get_db)):
    """
    Get transcoding status for a file

    Returns all transcoding jobs and available qualities.
    """
    file = db.query(File).filter(File.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")

    # Get all jobs for this file
    jobs = db.query(TranscodingJob).filter(
        TranscodingJob.file_id == file_id
    ).order_by(TranscodingJob.created_at.desc()).all()

    job_responses = []
    for job in jobs:
        job_responses.append(TranscodeJobResponse(
            id=job.id,
            file_id=job.file_id,
            filename=file.filename,
            target_quality=job.target_quality,
            status=job.status,
            progress=job.progress or 0,
            output_path=job.output_path,
            output_size=job.output_size,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at
        ))

    return TranscodeStatusResponse(
        file_id=file_id,
        filename=file.filename,
        original_size=file.size,
        is_video=file.is_video(),
        jobs=job_responses,
        available_qualities=file.get_available_qualities()
    )


@router.get("/transcode/job/{job_id}")
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get status of a specific transcoding job
    """
    job = db.query(TranscodingJob).filter(TranscodingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    file = db.query(File).filter(File.id == job.file_id).first()

    return {
        "job_id": job.id,
        "file_id": job.file_id,
        "filename": file.filename if file else "unknown",
        "target_quality": job.target_quality,
        "status": job.status,
        "progress": job.progress or 0,
        "output_path": job.output_path,
        "output_size": job.output_size,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "celery_task_id": job.celery_task_id,
        "ffmpeg_metadata": job.ffmpeg_metadata
    }


@router.get("/transcode/jobs/all")
def list_all_jobs(
    status: Optional[str] = Query(None, description="Filter by status: pending, processing, completed, failed"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all transcoding jobs with optional filtering
    """
    query = db.query(TranscodingJob)

    if status:
        query = query.filter(TranscodingJob.status == status)

    total = query.count()
    jobs = query.order_by(TranscodingJob.created_at.desc()).offset(skip).limit(limit).all()

    job_list = []
    for job in jobs:
        file = db.query(File).filter(File.id == job.file_id).first()
        job_list.append({
            "job_id": job.id,
            "file_id": job.file_id,
            "filename": file.filename if file else "unknown",
            "target_quality": job.target_quality,
            "status": job.status,
            "progress": job.progress or 0,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
        })

    return {
        "total": total,
        "jobs": job_list,
        "limit": limit,
        "skip": skip
    }


@router.delete("/transcode/job/{job_id}")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """
    Cancel a pending or processing transcoding job
    """
    job = db.query(TranscodingJob).filter(TranscodingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    if job.status in ["completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )

    # Revoke Celery task if exists
    if job.celery_task_id:
        from app.worker import celery_app
        celery_app.control.revoke(job.celery_task_id, terminate=True)

    job.status = "cancelled"
    job.error_message = "Cancelled by user"
    job.completed_at = datetime.utcnow()
    db.commit()

    return {"message": f"Job {job_id} cancelled", "status": "cancelled"}

