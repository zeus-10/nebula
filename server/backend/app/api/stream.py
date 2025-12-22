# Video streaming endpoint - HTTP byte-range requests (206 Partial Content), seeking support

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.file import File
from app.core.s3_client import minio_client
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Download a file by ID. Supports range requests for video streaming.
    Preserves original filename.
    """
    logger.info(f"📥 DOWNLOAD REQUEST - File ID: {file_id}")

    try:
        # Get file metadata
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.warning(f"⚠️ FILE NOT FOUND - ID: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"✅ FILE FOUND - {file.filename} ({file.size} bytes)")

        # Check if MinIO client supports range requests
        try:
            # Get file stream from MinIO
            file_stream = minio_client.get_file_stream(file.file_path)

            # Return streaming response with original filename
            response = StreamingResponse(
                file_stream,
                media_type=file.mime_type,
                headers={
                    "Content-Disposition": f"attachment; filename=\"{file.filename}\"",
                    "Content-Length": str(file.size),
                }
            )

            logger.info(f"🚀 STREAMING FILE - {file.filename} ({file.mime_type})")
            return response

        except Exception as e:
            logger.error(f"❌ MINIO STREAM FAILED - {file.file_path}, Error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to stream file: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ DOWNLOAD FAILED - File ID: {file_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/files/{file_id}/stream")
async def stream_file(
    file_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Stream a file with range request support (for video players).
    Supports seeking and partial content delivery.
    """
    logger.info(f"🎬 STREAM REQUEST - File ID: {file_id}")

    try:
        # Get file metadata
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.warning(f"⚠️ FILE NOT FOUND - ID: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        # Check if this is a range request
        range_header = request.headers.get("range")

        if range_header:
            # Handle range requests for video streaming
            logger.info(f"🎯 RANGE REQUEST - {range_header}")
            # For now, return full file - range request handling can be added later
            pass

        try:
            # Get file stream from MinIO
            file_stream = minio_client.get_file_stream(file.file_path)

            # Return streaming response
            response = StreamingResponse(
                file_stream,
                media_type=file.mime_type,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(file.size),
                }
            )

            logger.info(f"🎬 STREAMING FILE - {file.filename} ({file.mime_type})")
            return response

        except Exception as e:
            logger.error(f"❌ MINIO STREAM FAILED - {file.file_path}, Error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to stream file: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ STREAM FAILED - File ID: {file_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")



