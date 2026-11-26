"""Pytest fixtures for error handling tests.

Provides an async test client backed by the real FastAPI application
and configures the app to use the test database (APP_ENV=testing).

IMPORTANT: APP_ENV must be set to "testing" BEFORE app.main is imported,
so that pydantic-settings loads TEST_DATABASE_URL instead of DATABASE_URL.
"""

import os

# Must be set before importing app.main so the app connects to the test DB.
os.environ.setdefault("APP_ENV", "testing")

import asyncio
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import engine
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop() -> AsyncGenerator[asyncio.AbstractEventLoop, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client backed by the FastAPI application."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()


@pytest.fixture
async def app_client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client (alias for client)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    await engine.dispose()
