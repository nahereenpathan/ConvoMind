"""Pytest configuration and fixtures for asynchronous testing."""

import os
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///file:testdb?mode=memory&cache=shared&uri=true"
import asyncio
from typing import AsyncGenerator, Generator
import pytest

from httpx import ASGITransport, AsyncClient

from app.core.database import engine, Base
import app.models  # Register all models on Base.metadata
from app.models.user import User
from app.models.workspace import Workspace
from app.main import app





@pytest.fixture(autouse=True)
async def setup_and_dispose_engine():
    """Ensure database tables exist before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield




@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client fixture for endpoint testing."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
async def db_session() -> AsyncGenerator:
    """Async DB session fixture for test execution."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def test_user(db_session) -> User:
    """Fixture to create and return a test user."""
    import uuid
    from app.models.user import User
    from app.core.security import hash_password
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:6]}@convomind.ai",
        full_name="Test User",
        hashed_password=hash_password("Password123!"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_workspace(db_session, test_user) -> Workspace:
    """Fixture to create and return a test workspace with test_user as OWNER."""
    import uuid
    from app.models.workspace import Workspace, WorkspaceMember
    from app.models.enums import WorkspaceRole
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace",
        slug=f"test-ws-{uuid.uuid4().hex[:6]}",
        created_by_id=test_user.id,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    member = WorkspaceMember(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        user_id=test_user.id,
        role=WorkspaceRole.OWNER,
    )
    db_session.add(member)
    await db_session.commit()
    return workspace


@pytest.fixture
def auth_headers(test_user) -> dict:
    """Fixture to return auth headers for test_user."""
    from app.core.security import create_access_token
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}
