# File upload endpoint - handles multipart uploads, streams to MinIO, saves metadata to DB

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from typing import Optional
import mimetypes

from app.core.database import get_db
from app.services.file_service import upload_file
from app.models.file import File as FileModel

router = APIRouter()


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
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Determine content type
        content_type = file.content_type
        if content_type == "application/octet-stream":
            # Try to guess from filename
            guessed_type, _ = mimetypes.guess_type(file.filename)
            if guessed_type:
                content_type = guessed_type

        # Upload file using service
        file_record = upload_file(
            db=db,
            file_obj=file.file,
            filename=file.filename,
            content_type=content_type,
            description=description,
            user_id=user_id
        )

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
                "user_id": file_record.user_id
            }
        }

    except Exception as e:
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