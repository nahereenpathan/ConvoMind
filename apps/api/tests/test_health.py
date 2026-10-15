"""Tests for health check and root endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    """Verify the /health endpoint returns 200 and healthy status."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    assert res_data["service"] == "convomind-api"


@pytest.mark.asyncio
async def test_root_endpoint() -> None:
    """Verify the root / endpoint returns API service metadata."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "ConvoMind API",
        "version": "1.0.0",
        "status": "running",
    }


@pytest.mark.asyncio
async def test_v1_health_endpoint() -> None:
    """Verify the /api/v1/health endpoint returns 200 and service identifier."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "convomind-api",
    }
