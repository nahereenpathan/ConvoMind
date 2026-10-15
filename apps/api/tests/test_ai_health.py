"""Unit and integration test suite for AI Engine infrastructure health system."""

import uuid
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.models.user import User
from app.services.ai_health_service import AiHealthService


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session


async def _get_auth_headers(client: AsyncClient) -> dict:
    email = f"health_user_{uuid.uuid4().hex[:6]}@example.com"
    reg_res = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "name": "Health User"
    })
    assert reg_res.status_code == 201

    login_res = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_get_ai_engine_health_authenticated(client: AsyncClient, db: AsyncSession):
    """Verify GET /api/v1/system/ai-health returns 200 OK with valid schema for authenticated users."""
    AiHealthService.reset_cache()
    headers = await _get_auth_headers(client)

    res = await client.get("/api/v1/system/ai-health", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    data = res.json()
    assert "overall_status" in data
    assert data["overall_status"] in ("operational", "degraded", "down", "not_configured")
    assert "checked_at" in data
    assert "components" in data

    components = data["components"]
    expected_components = ["whisper", "diarization", "ai_intelligence", "rag", "celery", "redis", "postgresql"]
    for comp in expected_components:
        assert comp in components, f"Missing component {comp} in response"
        assert "status" in components[comp]
        assert "details" in components[comp]
        assert components[comp]["status"] in ("operational", "degraded", "down", "not_configured")


@pytest.mark.asyncio
async def test_get_ai_engine_health_unauthenticated(client: AsyncClient):
    """Verify GET /api/v1/system/ai-health returns 401 Unauthorized for unauthenticated requests."""
    res = await client.get("/api/v1/system/ai-health")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_no_secrets_leaked_in_health_response(client: AsyncClient, db: AsyncSession):
    """Assert zero infrastructure secrets (API keys, passwords, connection strings) are present in health payload."""
    AiHealthService.reset_cache()
    headers = await _get_auth_headers(client)

    res = await client.get("/api/v1/system/ai-health", headers=headers)
    assert res.status_code == 200

    raw_text = res.text.lower()

    # Secret keywords that must NEVER be returned to clients
    forbidden_terms = [
        "secret",
        "password",
        "postgres://",
        "postgresql://",
        "redis://",
        "bearer ",
        "token=",
        "key=",
        "stacktrace",
        "traceback",
    ]

    for term in forbidden_terms:
        assert term not in raw_text, f"Forbidden term '{term}' detected in AI health response!"


@pytest.mark.asyncio
async def test_overall_status_calculation():
    """Verify status matrix rules for overall status computation."""
    from app.schemas.system import ComponentHealthStatus

    # All operational
    c_all_op = {
        "postgresql": ComponentHealthStatus(status="operational", details="ok"),
        "redis": ComponentHealthStatus(status="operational", details="ok"),
        "celery": ComponentHealthStatus(status="operational", details="ok"),
        "whisper": ComponentHealthStatus(status="operational", details="ok"),
        "ai_intelligence": ComponentHealthStatus(status="operational", details="ok"),
        "diarization": ComponentHealthStatus(status="operational", details="ok"),
        "rag": ComponentHealthStatus(status="operational", details="ok"),
    }
    assert AiHealthService._calculate_overall_status(c_all_op) == "operational"

    # Optional service degraded (e.g. diarization down or not_configured)
    c_degraded = dict(c_all_op)
    c_degraded["diarization"] = ComponentHealthStatus(status="not_configured", details="HF token missing")
    assert AiHealthService._calculate_overall_status(c_degraded) == "degraded"

    # Critical service down (e.g. redis down)
    c_down = dict(c_all_op)
    c_down["redis"] = ComponentHealthStatus(status="down", details="redis down")
    assert AiHealthService._calculate_overall_status(c_down) == "down"
