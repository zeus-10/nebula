# File management routes - list files, get file metadata, delete files

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models.file import File
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class FileResponse(BaseModel):
    """Response model for file information"""
    id: int
    filename: str
    file_path: str
    size: int
    mime_type: str
    upload_date: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/files", response_model=List[FileResponse])
async def list_files(
    skip: int = Query(0, ge=0, description="Number of files to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of files to return"),
    db: Session = Depends(get_db)
):
    """
    List all uploaded files with metadata.

    Returns files sorted by upload date (newest first).
    """
    logger.info(f"📋 LISTING FILES - skip: {skip}, limit: {limit}")

    try:
        files = db.query(File).order_by(File.upload_date.desc()).offset(skip).limit(limit).all()

        # Convert to response format
        result = []
        for file in files:
            result.append(FileResponse(
                id=file.id,
                filename=file.filename,
                file_path=file.file_path,
                size=file.size,
                mime_type=file.mime_type,
                upload_date=file.upload_date.isoformat() if file.upload_date else None,
                description=file.description
            ))

        logger.info(f"✅ FOUND {len(result)} FILES")
        return result

    except Exception as e:
        logger.error(f"❌ FILE LISTING FAILED - Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_file_info(file_id: int, db: Session = Depends(get_db)):
    """
    Get detailed information about a specific file.
    """
    logger.info(f"🔍 GETTING FILE INFO - ID: {file_id}")

    try:
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.warning(f"⚠️ FILE NOT FOUND - ID: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        result = FileResponse(
            id=file.id,
            filename=file.filename,
            file_path=file.file_path,
            size=file.size,
            mime_type=file.mime_type,
            upload_date=file.upload_date.isoformat() if file.upload_date else None,
            description=file.description
        )

        logger.info(f"✅ FILE INFO RETRIEVED - {file.filename}")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ FILE INFO RETRIEVAL FAILED - ID: {file_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")



