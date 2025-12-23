# System management API - logs, restart, container status

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import subprocess
import os
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Container names as defined in docker-compose.yml
CONTAINERS = {
    "api": "nebula-api",
    "worker": "nebula-worker", 
    "db": "nebula-db",
    "s3": "nebula-s3",
    "queue": "nebula-queue"
}


@router.get("/system/logs/{service}")
def get_service_logs(
    service: str,
    lines: int = Query(100, ge=1, le=1000, description="Number of log lines to fetch"),
    follow: bool = Query(False, description="Not supported via API, use CLI")
):
    """
    Get logs for a specific service.
    
    Services: api, worker, db, s3, queue
    """
    if service not in CONTAINERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}. Must be one of: {list(CONTAINERS.keys())}"
        )
    
    container_name = CONTAINERS[service]
    
    try:
        # Get logs from docker container
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Docker logs go to stderr for some containers
        logs = result.stdout if result.stdout else result.stderr
        
        return {
            "service": service,
            "container": container_name,
            "lines": lines,
            "logs": logs
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Log fetch timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Docker command not found")
    except Exception as e:
        logger.error(f"Failed to get logs for {service}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get("/system/logs")
def get_all_logs(
    lines: int = Query(50, ge=1, le=500, description="Number of log lines per service")
):
    """
    Get recent logs from all services.
    """
    all_logs = {}
    errors = []
    
    for service, container_name in CONTAINERS.items():
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), container_name],
                capture_output=True,
                text=True,
                timeout=15
            )
            logs = result.stdout if result.stdout else result.stderr
            all_logs[service] = logs
        except Exception as e:
            errors.append(f"{service}: {str(e)}")
            all_logs[service] = f"Error fetching logs: {str(e)}"
    
    return {
        "lines_per_service": lines,
        "logs": all_logs,
        "errors": errors if errors else None
    }


@router.post("/system/restart/{service}")
def restart_service(service: str):
    """
    Restart a specific service container.
    
    Services: api, worker, db, s3, queue
    
    WARNING: Restarting 'api' will disconnect you temporarily.
    """
    if service not in CONTAINERS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service: {service}. Must be one of: {list(CONTAINERS.keys())}"
        )
    
    container_name = CONTAINERS[service]
    
    # Safety warning for critical services
    if service == "db":
        logger.warning("Database restart requested - this may cause data loss if transactions are in progress")
    
    try:
        logger.info(f"Restarting container: {container_name}")
        
        result = subprocess.run(
            ["docker", "restart", container_name],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Restart failed: {result.stderr}"
            )
        
        return {
            "service": service,
            "container": container_name,
            "status": "restarted",
            "message": f"Container {container_name} restarted successfully"
        }
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Restart timed out")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Docker command not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restart {service}: {e}")
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")


@router.post("/system/restart")
def restart_all_services():
    """
    Restart all Nebula services.
    
    WARNING: This will cause a brief outage.
    """
    results = {}
    errors = []
    
    # Restart in order: worker first, then api (to minimize disruption)
    restart_order = ["worker", "queue", "s3", "db", "api"]
    
    for service in restart_order:
        container_name = CONTAINERS[service]
        try:
            logger.info(f"Restarting container: {container_name}")
            result = subprocess.run(
                ["docker", "restart", container_name],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                results[service] = "restarted"
            else:
                results[service] = f"failed: {result.stderr}"
                errors.append(service)
        except Exception as e:
            results[service] = f"error: {str(e)}"
            errors.append(service)
    
    return {
        "status": "completed" if not errors else "partial",
        "results": results,
        "errors": errors if errors else None
    }


@router.get("/system/status")
def get_system_status():
    """
    Get status of all Docker containers.
    """
    statuses = {}
    
    for service, container_name in CONTAINERS.items():
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            status = result.stdout.strip() if result.returncode == 0 else "unknown"
            statuses[service] = {
                "container": container_name,
                "status": status
            }
        except Exception as e:
            statuses[service] = {
                "container": container_name,
                "status": "error",
                "error": str(e)
            }
    
    # Overall health
    all_running = all(s.get("status") == "running" for s in statuses.values())
    
    return {
        "overall": "healthy" if all_running else "degraded",
        "services": statuses
    }


