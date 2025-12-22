# File model - stores file metadata (name, size, S3 path, upload date, MIME type)

from sqlalchemy import Column, Integer, String, DateTime, BigInteger, Text
from sqlalchemy.sql import func
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

    # Upload information
    upload_date = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    user_id = Column(Integer, nullable=True)  # Future: link to user accounts

    # Optional metadata
    description = Column(Text, nullable=True)  # User-provided description
    tags = Column(Text, nullable=True)  # JSON string of tags/categories

    def __repr__(self):
        return f"<File(id={self.id}, filename='{self.filename}', size={self.size})>"