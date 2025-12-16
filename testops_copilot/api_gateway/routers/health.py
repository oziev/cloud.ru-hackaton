
from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy import text
from shared.utils.database import engine
from shared.utils.redis_client import redis_client
router = APIRouter(tags=["Health"])
class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str = "1.0.0"
    issues: Optional[List[str]] = None
class ReadyResponse(BaseModel):
    ready: bool
    services: dict
@router.get("/health", response_model=HealthResponse)
async def health_check():
    issues = []
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        issues.append(f"PostgreSQL unavailable: {str(e)}")
    try:
        redis_client.queue.ping()
    except Exception as e:
        issues.append(f"Redis connection failed: {str(e)}")
    if issues:
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            issues=issues
        )
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow()
    )
@router.get("/ready", response_model=ReadyResponse)
async def readiness_check():
    services = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services["postgresql"] = "connected"
    except Exception:
        services["postgresql"] = "disconnected"
    try:
        redis_client.queue.ping()
        services["redis"] = "connected"
    except Exception:
        services["redis"] = "disconnected"
    try:
        redis_client.queue.ping()
        services["celery"] = "running"
    except Exception:
        services["celery"] = "stopped"
    ready = all(
        status in ["connected", "running"]
        for status in services.values()
    )
    return ReadyResponse(
        ready=ready,
        services=services
    )