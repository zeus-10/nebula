# File operations - upload to MinIO, retrieve from MinIO, delete files, list files

from typing import BinaryIO, List, Dict, Optional, Any
from sqlalchemy.orm import Session
import uuid
import os
import hashlib
from datetime import datetime
import logging

from app.core.s3_client import minio_client
from app.models.file import File

logger = logging.getLogger(__name__)


def generate_file_key(filename: str) -> str:
    """
    Generate a unique S3 key for the file

    Args:
        filename: Original filename

    Returns:
        str: Unique S3 object key
    """
    # Generate unique identifier
    unique_id = str(uuid.uuid4())

    # Get file extension
    _, ext = os.path.splitext(filename)

    # Create key: uploads/YYYY/MM/filename_uuid.ext
    now = datetime.now()
    key = f"uploads/{now.year}/{now.month:02d}/{unique_id}{ext}"

    return key


def calculate_file_hash(file_obj: BinaryIO, chunk_size: int = 1024 * 1024) -> str:
    """
    Calculate SHA-256 hash of file content

    Args:
        file_obj: File-like object
        chunk_size: Size of chunks to read

    Returns:
        str: Hexadecimal hash
    """
    hash_obj = hashlib.sha256()
    file_obj.seek(0)  # Reset to beginning

    while chunk := file_obj.read(chunk_size):
        hash_obj.update(chunk)

    file_obj.seek(0)  # Reset for further use
    return hash_obj.hexdigest()


def upload_file(
    db: Session,
    file_obj: BinaryIO,
    filename: str,
    content_type: str = "application/octet-stream",
    description: str = None,
    user_id: int = None
) -> File:
    """
    Upload file to MinIO and save metadata to database

    Args:
        db: Database session
        file_obj: File-like object to upload
        filename: Original filename
        content_type: MIME type
        description: Optional description
        user_id: Optional user ID

    Returns:
        File: Created file record
    """
    upload_id = f"upload_{id(file_obj)}"  # Track this specific upload
    logger.info(f"[{upload_id}] 🔄 STARTING FILE SERVICE - File: {filename}, Type: {content_type}")

    # Get file size
    file_obj.seek(0, 2)  # Seek to end
    file_size = file_obj.tell()
    file_obj.seek(0)  # Reset to beginning

    logger.info(f"[{upload_id}] 📏 FILE SIZE - {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")

    # Generate unique S3 key
    s3_key = generate_file_key(filename)
    logger.info(f"[{upload_id}] 🔑 GENERATED S3 KEY - {s3_key}")

    # Calculate file hash (optional, for integrity checking)
    logger.info(f"[{upload_id}] 🔐 CALCULATING FILE HASH...")
    file_hash = calculate_file_hash(file_obj)
    logger.info(f"[{upload_id}] ✅ HASH CALCULATED - {file_hash[:16]}...")

    # Upload to MinIO
    logger.info(f"[{upload_id}] ☁️  STARTING MINIO UPLOAD...")
    try:
        minio_client.upload_file(
            file_obj=file_obj,
            object_name=s3_key,
            file_size=file_size,
            content_type=content_type
        )
        logger.info(f"[{upload_id}] ✅ MINIO UPLOAD SUCCESSFUL - Object: {s3_key}")

        # Verify upload
        verify_info = minio_client.get_file_info(s3_key)
        if verify_info:
            logger.info(f"[{upload_id}] 🔍 VERIFICATION - Size: {verify_info['size']}, Type: {verify_info['content_type']}")
        else:
            logger.warning(f"[{upload_id}] ⚠️  VERIFICATION FAILED - Could not retrieve file info")

    except Exception as e:
        logger.error(f"[{upload_id}] ❌ MINIO UPLOAD FAILED - Error: {e}", exc_info=True)
        raise Exception(f"Failed to upload file to storage: {e}")

    # Save metadata to database
    logger.info(f"[{upload_id}] 💾 SAVING METADATA TO DATABASE...")
    try:
        file_record = File(
            filename=filename,
            file_path=s3_key,
            size=file_size,
            mime_type=content_type,
            file_hash=file_hash,
            description=description,
            user_id=user_id
        )

        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        logger.info(f"[{upload_id}] ✅ DATABASE SAVE SUCCESSFUL - File ID: {file_record.id}")
        return file_record

    except Exception as e:
        logger.error(f"[{upload_id}] ❌ DATABASE SAVE FAILED - Error: {e}", exc_info=True)
        # If database save fails, try to clean up MinIO file
        try:
            logger.info(f"[{upload_id}] 🧹 CLEANING UP MINIO FILE - {s3_key}")
            minio_client.delete_file(s3_key)
            logger.info(f"[{upload_id}] ✅ MINIO CLEANUP COMPLETED")
        except Exception as cleanup_error:
            logger.error(f"[{upload_id}] ❌ MINIO CLEANUP FAILED - {cleanup_error}")

        raise Exception(f"Failed to save file metadata: {e}")


def download_file(file_id: int, db: Session) -> Optional[BinaryIO]:
    """
    Get file stream from MinIO

    Args:
        file_id: File record ID
        db: Database session

    Returns:
        BinaryIO: File stream or None if not found
    """
    # Get file record from database
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        return None

    # Get file stream from MinIO
    try:
        return minio_client.get_file_stream(file_record.file_path)
    except Exception:
        return None


def delete_file(file_id: int, db: Session) -> bool:
    """
    Delete file from both MinIO and database

    Args:
        file_id: File record ID
        db: Database session

    Returns:
        bool: True if deleted successfully
    """
    # Get file record
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        return False

    # Delete from MinIO
    try:
        minio_client.delete_file(file_record.file_path)
    except Exception:
        # Continue with database deletion even if MinIO fails
        pass

    # Delete from database
    try:
        db.delete(file_record)
        db.commit()
        return True
    except Exception:
        return False


def get_file_info(file_id: int, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get file information

    Args:
        file_id: File record ID
        db: Database session

    Returns:
        Dict with file info or None if not found
    """
    file_record = db.query(File).filter(File.id == file_id).first()
    if not file_record:
        return None

    # Get MinIO metadata
    minio_info = minio_client.get_file_info(file_record.file_path)

    return {
        "id": file_record.id,
        "filename": file_record.filename,
        "file_path": file_record.file_path,
        "size": file_record.size,
        "mime_type": file_record.mime_type,
        "file_hash": file_record.file_hash,
        "upload_date": file_record.upload_date,
        "description": file_record.description,
        "user_id": file_record.user_id,
        "minio_info": minio_info
    }


def list_files(db: Session, user_id: Optional[int] = None, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """
    List files with pagination

    Args:
        db: Database session
        user_id: Optional filter by user
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        List of file info dicts
    """
    query = db.query(File)

    if user_id is not None:
        query = query.filter(File.user_id == user_id)

    query = query.order_by(File.upload_date.desc()).limit(limit).offset(offset)

    files = query.all()

    return [
        {
            "id": file.id,
            "filename": file.filename,
            "size": file.size,
            "mime_type": file.mime_type,
            "upload_date": file.upload_date,
            "description": file.description
        }
        for file in files
    ]


def get_file_by_id(file_id: int, db: Session) -> Optional[File]:
    """
    Get file record by ID

    Args:
        file_id: File record ID
        db: Database session

    Returns:
        File record or None
    """
    return db.query(File).filter(File.id == file_id).first()