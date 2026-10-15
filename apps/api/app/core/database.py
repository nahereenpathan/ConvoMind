"""Database connection and session management with SQLAlchemy 2 async."""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

import logging
import os
import socket
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}
if os.getenv("TESTING") == "1" or getattr(settings, "ENVIRONMENT", "") == "testing":
    from sqlalchemy.pool import StaticPool
    engine_kwargs["poolclass"] = StaticPool
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True

db_url = settings.DATABASE_URL

# Compute standard dev.db path in apps/api/dev.db
_api_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_dev_db_path = os.path.join(_api_dir, "dev.db")

def _is_port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    if host in ("postgres", "redis") and os.name == "nt":
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

if "postgresql" in db_url:
    pg_host = "postgres" if "@postgres:" in db_url else "localhost"
    pg_port = 5432
    if "@postgres:5432" in db_url:
        if _is_port_open("postgres", pg_port, timeout=0.2):
            pass
        elif _is_port_open("localhost", pg_port, timeout=0.2):
            db_url = db_url.replace("@postgres:5432", "@localhost:5432")
        elif os.path.exists(_dev_db_path):
            logger.warning(
                "PostgreSQL unreachable at %s:%s. Falling back to local SQLite database: %s",
                pg_host, pg_port, _dev_db_path,
            )
            db_url = f"sqlite+aiosqlite:///{_dev_db_path.replace(os.sep, '/')}"
    else:
        if not _is_port_open(pg_host, pg_port, timeout=0.2) and os.path.exists(_dev_db_path):
            logger.warning(
                "PostgreSQL unreachable at %s:%s. Falling back to local SQLite database: %s",
                pg_host, pg_port, _dev_db_path,
            )
            db_url = f"sqlite+aiosqlite:///{_dev_db_path.replace(os.sep, '/')}"

if "sqlite" in db_url:
    if "connect_args" not in engine_kwargs:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    if "///dev.db" in db_url and os.path.exists(_dev_db_path):
        db_url = f"sqlite+aiosqlite:///{_dev_db_path.replace(os.sep, '/')}"

# Create asynchronous engine
engine: AsyncEngine = create_async_engine(
    db_url,
    **engine_kwargs,
)


# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all SQLAlchemy models with async attribute support."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for obtaining an asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
