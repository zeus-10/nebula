# FastAPI application entrypoint - initializes app, mounts routers, starts server

from fastapi import FastAPI
from app.api import ping, upload, files, stream
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure FastAPI for large file uploads
app = FastAPI(
    title="Nebula Cloud",
    # File size limits for video uploads
    # max_request_size: 10GB (supports large video files)
    # Individual files can be up to this size
)

app.include_router(ping.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["files"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(stream.router, prefix="/api", tags=["streaming"])

@app.get("/")
def read_root():
    return {"system": "Nebula", "status": "online", "version": "1.0.0-alpha"}

@app.get("/health")
def health_check():
    """
    Phase 1 Connectivity Check
    Verifies that the API is running and can read config.
    """
    # Check Database Config
    db_status = "configured" if os.getenv("DATABASE_URL") else "missing"
    
    # Check Battery Status (Mock for Phase 1)
    power_path = "/host_power/BAT0/capacity" # Check BAT0 or BAT1 on your laptop
    battery_level = "unknown"
    
    if os.path.exists(power_path):
        with open(power_path, "r") as f:
            battery_level = f"{f.read().strip()}%"

    return {
        "status": "healthy", 
        "database": db_status,
        "battery": battery_level,
        "worker": "ready"
    }

