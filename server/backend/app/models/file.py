# File model - stores file metadata (name, size, S3 path, upload date, MIME type)

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class File(Base):
    """File metadata model for tracking uploaded files"""

    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # File identification
    filename = Column(String(255), nullable=False, index=True)  # Original filename
    file_path = Column(String(500), nullable=False)  # S3 path/key

    # File metadata
    size = Column(BigInteger, nullable=False)  # File size in bytes
    mime_type = Column(String(100), nullable=False)  # MIME type (e.g., "video/mp4")
    file_hash = Column(String(128), nullable=True)  # Optional: SHA-256 hash for integrity

    # Video metadata (duration, resolution, codec) - populated after upload for video files
    video_metadata = Column(JSON, nullable=True)

    # Transcoded variants: {"480": "path/to/480p.mp4", "720": "path/to/720p.mp4"}
    transcoded_variants = Column(JSON, nullable=True)

    # Upload information
    upload_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, nullable=True)  # Future: link to user accounts

    # Optional metadata
    description = Column(Text, nullable=True)  # User-provided description
    tags = Column(Text, nullable=True)  # JSON string of tags/categories

    # Relationship to transcoding jobs
    transcoding_jobs = relationship("TranscodingJob", backref="file", lazy="dynamic")

    def __repr__(self):
        return f"<File(id={self.id}, filename='{self.filename}', size={self.size})>"

    def is_video(self) -> bool:
        """Check if file is a video based on MIME type"""
        return self.mime_type.startswith("video/")

    def get_available_qualities(self) -> list:
        """Get list of available transcoded qualities"""
        if not self.transcoded_variants:
            return []
        return sorted([int(q) for q in self.transcoded_variants.keys()])