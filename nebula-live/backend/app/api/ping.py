# Health check endpoint - returns "Pong" for connectivity testing (Phase 1)

from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/health")
async def health_check():
    # Logic to check battery or system stats
    return {"status": "online", "message": "Nebula Engine is humming."}