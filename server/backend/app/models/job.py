# Job model - tracks transcoding tasks (status, input file, output file, progress, errors)

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class TranscodingJob(Base):
    """Transcoding job model for tracking video conversion tasks"""

    __tablename__ = "transcoding_jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Source file reference
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)

    # Target quality (480, 720, 1080)
    target_quality = Column(Integer, nullable=False)  # e.g., 480, 720, 1080

    # Job status: pending, processing, completed, failed
    status = Column(String(50), nullable=False, default="pending", index=True)

    # Progress tracking (0-100)
    progress = Column(Float, default=0.0)

    # Output file path in MinIO (set when complete)
    output_path = Column(String(500), nullable=True)

    # Output file size in bytes (set when complete)
    output_size = Column(Integer, nullable=True)

    # Error message if failed
    error_message = Column(Text, nullable=True)

    # FFmpeg metadata (codec, bitrate, etc.)
    ffmpeg_metadata = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Celery task ID for tracking
    celery_task_id = Column(String(255), nullable=True)

    def __repr__(self):
        return f"<TranscodingJob(id={self.id}, file_id={self.file_id}, quality={self.target_quality}p, status={self.status})>"
