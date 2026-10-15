"""ConvoMind FastAPI Application entrypoint."""

from contextlib import asynccontextmanager
import logging
import os
import sys
from typing import AsyncGenerator, Dict, Any
from fastapi import FastAPI, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import get_db, engine
from app.core.rate_limit import limiter, is_testing

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    logger.info("Starting up ConvoMind API service...")
    if "sqlite" in str(engine.url):
        import app.models  # Ensure models are registered
        from app.core.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("Shutting down ConvoMind API service, disposing database connections...")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register slowapi rate limiter state and exception handler
limiter.enabled = not is_testing
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include modular API v1 router
app.include_router(api_v1_router)


@app.get("/", summary="Root Endpoint")
async def root() -> Dict[str, str]:
    """Root endpoint returning service status and metadata."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health", summary="Shallow Application Health Check")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Application health check endpoint verifying database connectivity."""
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "convomind-api",
                "database": db_status,
            },
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "service": "convomind-api",
            "database": db_status,
        },
    )


@app.get("/health/deep", summary="Deep Infrastructure Health Check")
async def deep_health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Comprehensive health check probing PostgreSQL database & Redis cache connections."""
    health_status: Dict[str, Any] = {
        "status": "healthy",
        "components": {
            "postgres": "unknown",
            "redis": "unknown",
        },
    }
    is_healthy = True

    # 1. Probe PostgreSQL Database
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["postgres"] = "healthy"
    except Exception as exc:
        logger.error(f"PostgreSQL deep health check failed: {exc}")
        health_status["components"]["postgres"] = f"unhealthy: {str(exc)}"
        is_healthy = False

    # 2. Probe Redis Cache
    try:
        r = aioredis.from_url(settings.REDIS_URL)
        pong = await r.ping()
        await r.aclose()
        if pong:
            health_status["components"]["redis"] = "healthy"
        else:
            health_status["components"]["redis"] = "unhealthy: ping returned False"
            is_healthy = False
    except Exception as exc:
        logger.error(f"Redis deep health check failed: {exc}")
        health_status["components"]["redis"] = f"unhealthy: {str(exc)}"
        is_healthy = False

    if not is_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=health_status)

    return JSONResponse(status_code=status.HTTP_200_OK, content=health_status)
