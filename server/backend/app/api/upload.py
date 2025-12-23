# File upload endpoint - handles multipart uploads, streams to MinIO, saves metadata to DB

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form, Query
from sqlalchemy.orm import Session
from typing import Optional
import mimetypes
import logging

from app.core.database import get_db
from pydantic import BaseModel

from app.services.file_service import upload_file, generate_file_key
from app.models.file import File as FileModel
from app.core.s3_client import minio_client

router = APIRouter()
logger = logging.getLogger(__name__)


class PresignUploadRequest(BaseModel):
    filename: str
    content_type: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[int] = None


class PresignUploadResponse(BaseModel):
    success: bool
    object_key: str
    upload_url: str


class CompleteUploadRequest(BaseModel):
    object_key: str
    filename: str
    content_type: Optional[str] = None
    description: Optional[str] = None
    user_id: Optional[int] = None
    file_hash: Optional[str] = None


@router.post("/upload/presign", response_model=PresignUploadResponse)
async def presign_upload(
    body: PresignUploadRequest,
    network: str | None = Query(default=None, description="Presign network hint: local|remote|auto"),
):
    """
    Create a presigned PUT URL to upload directly to MinIO (bypasses API data path).
    Client must call /api/upload/complete after uploading to register metadata in DB.
    """
    if not body.filename:
        raise HTTPException(status_code=400, detail="filename is required")

    # Basic content-type guess (client may override)
    content_type = body.content_type
    if not content_type or content_type == "application/octet-stream":
        guessed_type, _ = mimetypes.guess_type(body.filename)
        content_type = guessed_type or "application/octet-stream"

    object_key = generate_file_key(body.filename)
    try:
        upload_url = minio_client.get_presigned_put_url(object_name=object_key, network=network)
        return {"success": True, "object_key": object_key, "upload_url": upload_url}
    except Exception as e:
        logger.error(f"Failed to presign upload url for {object_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create upload url: {str(e)}")


@router.post("/upload/complete")
async def complete_upload(
    body: CompleteUploadRequest,
    db: Session = Depends(get_db),
):
    """
    After a client uploads directly to MinIO via presigned URL, register the file in DB.
    """
    if not body.object_key or not body.filename:
        raise HTTPException(status_code=400, detail="object_key and filename are required")

    # Safety: only allow our upload prefix
    if not body.object_key.startswith("uploads/"):
        raise HTTPException(status_code=400, detail="Invalid object_key")

    # Verify object exists in MinIO and obtain size/content-type
    info = minio_client.get_file_info(body.object_key)
    if not info:
        raise HTTPException(status_code=404, detail="Uploaded object not found in storage")

    size = int(info["size"])
    content_type = body.content_type
    if not content_type or content_type == "application/octet-stream":
        content_type = info.get("content_type") or (mimetypes.guess_type(body.filename)[0] or "application/octet-stream")

    try:
        file_record = FileModel(
            filename=body.filename,
            file_path=body.object_key,
            size=size,
            mime_type=content_type,
            file_hash=body.file_hash,
            description=body.description,
            user_id=body.user_id,
        )
        db.add(file_record)
        db.commit()
        db.refresh(file_record)

        return {
            "success": True,
            "file": {
                "id": file_record.id,
                "filename": file_record.filename,
                "file_path": file_record.file_path,
                "size": file_record.size,
                "mime_type": file_record.mime_type,
                "upload_date": file_record.upload_date.isoformat(),
                "description": file_record.description,
                "user_id": file_record.user_id,
            },
        }
    except Exception as e:
        logger.error(f"Failed to save metadata for {body.object_key}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save file metadata: {str(e)}")


@router.post("/upload")
async def upload_file_endpoint(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload file to MinIO storage and save metadata to database

    - **file**: The file to upload
    - **description**: Optional description for the file
    - **user_id**: Optional user ID (for future authentication)

    Returns file information including ID, filename, size, etc.
    """
    request_id = f"upload_{id(file)}"  # Unique request ID for tracking
    logger.info(f"[{request_id}] 🚀 STARTING UPLOAD - File: {file.filename}")

    try:
        # Validate file
        if not file.filename:
            logger.error(f"[{request_id}] ❌ VALIDATION FAILED - No filename provided")
            raise HTTPException(status_code=400, detail="No filename provided")

        logger.info(f"[{request_id}] ✅ VALIDATION PASSED - Filename: {file.filename}")

        # Determine content type
        content_type = file.content_type
        logger.info(f"[{request_id}] 📋 CONTENT TYPE - Original: {content_type}")

        if content_type == "application/octet-stream":
            # Try to guess from filename
            guessed_type, _ = mimetypes.guess_type(file.filename)
            if guessed_type:
                content_type = guessed_type
                logger.info(f"[{request_id}] 🔍 CONTENT TYPE - Guessed: {content_type}")

        logger.info(f"[{request_id}] 📋 FINAL CONFIG - Content-Type: {content_type}, Description: {description}, User-ID: {user_id}")

        # Upload file using service
        logger.info(f"[{request_id}] 🔄 CALLING UPLOAD SERVICE...")
        file_record = upload_file(
            db=db,
            file_obj=file.file,
            filename=file.filename,
            content_type=content_type,
            description=description,
            user_id=user_id
        )

        logger.info(f"[{request_id}] ✅ UPLOAD COMPLETE - File ID: {file_record.id}, Path: {file_record.file_path}, Size: {file_record.size} bytes")

        response_data = {
            "success": True,
            "file": {
                "id": file_record.id,
                "filename": file_record.filename,
                "file_path": file_record.file_path,
                "size": file_record.size,
                "mime_type": file_record.mime_type,
                "upload_date": file_record.upload_date.isoformat(),
                "description": file_record.description,
                "user_id": file_record.user_id
            }
        }

        logger.info(f"[{request_id}] 📤 RESPONSE SENT - Success: {response_data['success']}")
        return response_data

    except Exception as e:
        logger.error(f"[{request_id}] 💥 UPLOAD FAILED - Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/files")
async def list_files_endpoint(
    user_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    List uploaded files

    - **user_id**: Optional filter by user
    - **limit**: Maximum number of results (default: 50)
    - **offset**: Pagination offset (default: 0)
    """
    try:
        from app.services.file_service import list_files
        files = list_files(db=db, user_id=user_id, limit=limit, offset=offset)

        return {
            "success": True,
            "files": files,
            "count": len(files)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/files/{file_id}")
async def get_file_info_endpoint(
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific file

    - **file_id**: The file ID to retrieve
    """
    try:
        from app.services.file_service import get_file_info
        file_info = get_file_info(file_id=file_id, db=db)

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        return {
            "success": True,
            "file": file_info
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get file info: {str(e)}")


@router.delete("/files/{file_id}")
async def delete_file_endpoint(
    file_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a file from storage and database

    - **file_id**: The file ID to delete
    """
    try:
        from app.services.file_service import delete_file
        success = delete_file(file_id=file_id, db=db)

        if not success:
            raise HTTPException(status_code=404, detail="File not found or deletion failed")

        return {
            "success": True,
            "message": f"File {file_id} deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")