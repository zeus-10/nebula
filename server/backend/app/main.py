# FastAPI application entrypoint - initializes app, mounts routers, starts server

from fastapi import FastAPI
from app.api import ping, upload, files, stream, transcode
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
    # Large file upload configuration
    # Individual files can be up to 10GB+
    # Total request size limits handled by server configuration
)

app.include_router(ping.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["files"])
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(stream.router, prefix="/api", tags=["streaming"])
app.include_router(transcode.router, prefix="/api", tags=["transcoding"])

@app.get("/")
def read_root():
    return {"system": "Nebula", "status": "online", "version": "1.0.0-alpha"}

@app.get("/health")
def health_check():
    """
    Comprehensive system health check with detailed specs.
    """
    import psutil
    import platform
    from datetime import datetime

    try:
        # Database status
        db_status = "configured" if os.getenv("DATABASE_URL") else "missing"

        # Battery status
        power_path = "/host_power/BAT0/capacity"
        battery_level = "unknown"

        if os.path.exists(power_path):
            with open(power_path, "r") as f:
                battery_level = f"{f.read().strip()}%"
        else:
            # Try alternative battery paths
            alt_paths = ["/sys/class/power_supply/BAT0/capacity", "/sys/class/power_supply/BAT1/capacity"]
            for path in alt_paths:
                if os.path.exists(path):
                    with open(path, "r") as f:
                        battery_level = f"{f.read().strip()}%"
                    break

        # System information
        system_info = {
            "platform": platform.system(),
            "platform_version": platform.release(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
            "hostname": platform.node()
        }

        # CPU information
        cpu_info = {
            "cores_physical": psutil.cpu_count(logical=False),
            "cores_logical": psutil.cpu_count(logical=True),
            "usage_percent": psutil.cpu_percent(interval=0.1)
        }

        # Memory information
        memory = psutil.virtual_memory()
        memory_info = {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent
        }

        # Disk information
        disk = psutil.disk_usage('/')
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }

        # Network information
        net = psutil.net_io_counters()
        network_info = {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv
        }

        # Process information
        process_info = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "num_processes": len(psutil.pids())
        }

        # Overall status determination
        status = "healthy"
        issues = []

        if cpu_info["usage_percent"] > 90:
            status = "degraded"
            issues.append("High CPU usage")

        if memory_info["percent"] > 90:
            status = "degraded"
            issues.append("High memory usage")

        if disk_info["percent"] > 95:
            status = "degraded"
            issues.append("Low disk space")

        if db_status != "configured":
            status = "degraded"
            issues.append("Database not configured")

        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "issues": issues if issues else None,
            "system": system_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "processes": process_info,
            "services": {
                "database": db_status,
                "battery": battery_level,
                "worker": "ready"  # TODO: Check actual worker status
            }
        }

    except Exception as e:
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "services": {
                "database": "configured" if os.getenv("DATABASE_URL") else "missing",
                "battery": battery_level if 'battery_level' in locals() else "unknown",
                "worker": "unknown"
            }
        }

