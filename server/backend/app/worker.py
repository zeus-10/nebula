# Celery worker entrypoint - initializes Celery app, registers tasks for FFmpeg transcoding

from celery import Celery
import os
import tempfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

celery_app = Celery(
    "nebula_worker",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL")
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600 * 4,  # 4 hour hard limit
    task_soft_time_limit=3600 * 3,  # 3 hour soft limit
)


@celery_app.task
def dummy_task():
    return "Worker is alive"


@celery_app.task(bind=True)
def transcode_video_task(self, job_id: int, file_id: int, target_quality: int):
    """
    Celery task for transcoding a video file

    Args:
        job_id: TranscodingJob ID
        file_id: Source File ID
        target_quality: Target quality (480, 720, 1080)
    """
    from app.core.database import SessionLocal
    from app.core.s3_client import minio_client
    from app.models import File, TranscodingJob
    from app.services.transcode_service import transcode_service

    db = SessionLocal()

    try:
        # Get job and file from database
        job = db.query(TranscodingJob).filter(TranscodingJob.id == job_id).first()
        file = db.query(File).filter(File.id == file_id).first()

        if not job or not file:
            raise ValueError(f"Job {job_id} or File {file_id} not found")

        # Update job status to processing
        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.celery_task_id = self.request.id
        db.commit()

        logger.info(f"Starting transcode job {job_id}: {file.filename} -> {target_quality}p")

        # Create temporary files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download source file from MinIO
            input_path = os.path.join(temp_dir, f"input_{file.filename}")
            logger.info(f"Downloading source file: {file.file_path}")
            minio_client.download_file(file.file_path, input_path)

            # Generate output filename
            base_name = os.path.splitext(file.filename)[0]
            output_filename = f"{base_name}_{target_quality}p.mp4"
            output_path = os.path.join(temp_dir, output_filename)

            # Progress callback to update job
            def update_progress(progress):
                try:
                    job.progress = progress
                    db.commit()
                    # Update Celery task state
                    self.update_state(
                        state="PROGRESS",
                        meta={"progress": progress, "quality": target_quality}
                    )
                except Exception as e:
                    logger.warning(f"Failed to update progress: {e}")

            # Run transcoding
            result = transcode_service.transcode(
                input_path=input_path,
                output_path=output_path,
                target_quality=target_quality,
                progress_callback=update_progress
            )

            # Upload transcoded file to MinIO
            s3_output_path = f"transcoded/{file_id}/{output_filename}"
            logger.info(f"Uploading transcoded file: {s3_output_path}")

            with open(output_path, "rb") as f:
                minio_client.upload_file(
                    file_obj=f,
                    object_name=s3_output_path,
                    file_size=result["output_size"],
                    content_type="video/mp4"
                )

            # Update job as completed
            job.status = "completed"
            job.progress = 100
            job.output_path = s3_output_path
            job.output_size = result["output_size"]
            job.completed_at = datetime.utcnow()
            job.ffmpeg_metadata = {
                "width": result["width"],
                "height": result["height"],
                "bitrate": result["bitrate"],
                "duration": result["duration"],
            }

            # Update file's transcoded_variants
            if not file.transcoded_variants:
                file.transcoded_variants = {}
            file.transcoded_variants[str(target_quality)] = s3_output_path

            db.commit()

            logger.info(f"Transcode job {job_id} completed successfully")

            return {
                "job_id": job_id,
                "status": "completed",
                "output_path": s3_output_path,
                "output_size": result["output_size"],
            }

    except Exception as e:
        logger.error(f"Transcode job {job_id} failed: {e}")

        # Update job as failed
        try:
            job = db.query(TranscodingJob).filter(TranscodingJob.id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception as db_error:
            logger.error(f"Failed to update job status: {db_error}")

        raise

    finally:
        db.close()
