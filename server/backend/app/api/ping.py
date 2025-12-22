# Health check endpoint - returns "Pong" for connectivity testing (Phase 1)

from fastapi import APIRouter
import os

router = APIRouter()

@router.get("/ping")
async def ping():
    return {"status": "online", "message": "Pong"}
