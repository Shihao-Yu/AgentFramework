"""
Health check endpoints for Kubernetes probes and monitoring.

Provides:
- /health/live: Liveness probe (always returns 200 if app is running)
- /health/ready: Readiness probe (checks database connection)
- /health/dependencies: Deep health check (checks all external dependencies)
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Literal

from app.core.database import get_session
from app.core.dependencies import (
    get_embedding_client,
    get_inference_client,
)
from app.clients.embedding_client import EmbeddingClient
from app.clients.inference_client import InferenceClient

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    database: Literal["connected", "disconnected"]


class DependencyStatus(BaseModel):
    status: Literal["healthy", "unhealthy"]
    latency_ms: float | None = None
    error: str | None = None


class DependenciesResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    database: DependencyStatus
    embedding_service: DependencyStatus
    llm_service: DependencyStatus


@router.get("/live", response_model=LiveResponse)
async def liveness():
    """
    Liveness probe for Kubernetes.
    
    Always returns 200 if the application is running.
    Used to determine if the container should be restarted.
    """
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def readiness(
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """
    Readiness probe for Kubernetes.
    
    Checks if the application can handle requests by verifying
    database connectivity. Returns 200 if ready, 503 if not.
    """
    try:
        await session.execute(text("SELECT 1"))
        return ReadyResponse(status="ready", database="connected")
    except Exception:
        response.status_code = 503
        return ReadyResponse(status="not_ready", database="disconnected")


@router.get("/dependencies", response_model=DependenciesResponse)
async def dependencies(
    response: Response,
    session: AsyncSession = Depends(get_session),
    embedding_client: EmbeddingClient = Depends(get_embedding_client),
    inference_client: InferenceClient = Depends(get_inference_client),
):
    """
    Deep health check for all external dependencies.
    
    Checks:
    - Database connection
    - Embedding service availability
    - LLM service availability
    
    Returns:
    - healthy (200): All dependencies are available
    - degraded (200): Some non-critical dependencies unavailable
    - unhealthy (503): Critical dependencies (database) unavailable
    """
    import time
    
    # Check database
    db_status = DependencyStatus(status="healthy")
    try:
        start = time.monotonic()
        await session.execute(text("SELECT 1"))
        db_status.latency_ms = (time.monotonic() - start) * 1000
    except Exception as e:
        db_status.status = "unhealthy"
        db_status.error = str(e)
    
    # Check embedding service
    embedding_status = DependencyStatus(status="healthy")
    try:
        start = time.monotonic()
        is_healthy = await embedding_client.health_check()
        embedding_status.latency_ms = (time.monotonic() - start) * 1000
        if not is_healthy:
            embedding_status.status = "unhealthy"
            embedding_status.error = "Health check returned false"
    except Exception as e:
        embedding_status.status = "unhealthy"
        embedding_status.error = str(e)
    
    # Check LLM service
    llm_status = DependencyStatus(status="healthy")
    try:
        start = time.monotonic()
        is_healthy = await inference_client.health_check()
        llm_status.latency_ms = (time.monotonic() - start) * 1000
        if not is_healthy:
            llm_status.status = "unhealthy"
            llm_status.error = "Health check returned false"
    except Exception as e:
        llm_status.status = "unhealthy"
        llm_status.error = str(e)
    
    # Determine overall status and HTTP status code
    if db_status.status == "unhealthy":
        overall = "unhealthy"
        response.status_code = 503
    elif embedding_status.status == "unhealthy" or llm_status.status == "unhealthy":
        overall = "degraded"
        # Degraded is still 200 - service can function without non-critical deps
    else:
        overall = "healthy"
    
    return DependenciesResponse(
        status=overall,
        database=db_status,
        embedding_service=embedding_status,
        llm_service=llm_status,
    )
