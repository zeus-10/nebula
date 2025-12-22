# Video streaming endpoint - HTTP byte-range requests (206 Partial Content), seeking support

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse, Response
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
    Download a file by ID. Returns full file with Content-Disposition header.
    """
    logger.info(f"📥 DOWNLOAD REQUEST - File ID: {file_id}")

    try:
        # Get file metadata
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.warning(f"⚠️ FILE NOT FOUND - ID: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        logger.info(f"✅ FILE FOUND - {file.filename} ({file.size} bytes)")

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

            logger.info(f"🚀 DOWNLOADING FILE - {file.filename} ({file.mime_type})")
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
    Stream a file with byte-range support for video players.
    Supports seeking and partial content delivery (HTTP 206).
    """
    logger.info(f"🎬 STREAM REQUEST - File ID: {file_id}")

    try:
        # Get file metadata
        file = db.query(File).filter(File.id == file_id).first()
        if not file:
            logger.warning(f"⚠️ FILE NOT FOUND - ID: {file_id}")
            raise HTTPException(status_code=404, detail="File not found")

        file_size = file.size
        
        # Check for Range header
        range_header = request.headers.get("range")
        
        if range_header:
            # Parse range header: "bytes=start-end" or "bytes=start-"
            logger.info(f"🎯 RANGE REQUEST - {range_header}")
            
            try:
                range_spec = range_header.replace("bytes=", "")
                
                if "-" in range_spec:
                    parts = range_spec.split("-")
                    start = int(parts[0]) if parts[0] else 0
                    end = int(parts[1]) if parts[1] else file_size - 1
                else:
                    start = int(range_spec)
                    end = file_size - 1
                
                # Validate range
                if start >= file_size:
                    raise HTTPException(
                        status_code=416,
                        detail="Range not satisfiable",
                        headers={"Content-Range": f"bytes */{file_size}"}
                    )
                
                if end >= file_size:
                    end = file_size - 1
                
                content_length = end - start + 1
                
                logger.info(f"📊 RANGE: bytes {start}-{end}/{file_size} ({content_length} bytes)")
                
                # Get partial file stream from MinIO
                file_stream = minio_client.get_file_stream_range(
                    file.file_path, 
                    offset=start, 
                    length=content_length
                )
                
                # Return 206 Partial Content
                return StreamingResponse(
                    file_stream,
                    status_code=206,
                    media_type=file.mime_type,
                    headers={
                        "Content-Range": f"bytes {start}-{end}/{file_size}",
                        "Content-Length": str(content_length),
                        "Accept-Ranges": "bytes",
                    }
                )
                
            except ValueError as e:
                logger.warning(f"⚠️ INVALID RANGE - {range_header}: {e}")
                # Fall through to full file response
        
        # No range header or invalid range - return full file
        logger.info(f"📦 FULL FILE REQUEST - {file.filename} ({file_size} bytes)")
        
        file_stream = minio_client.get_file_stream(file.file_path)
        
        return StreamingResponse(
            file_stream,
            media_type=file.mime_type,
            headers={
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ STREAM FAILED - File ID: {file_id}, Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stream failed: {str(e)}")
