"""
Integration tests for GET /api/v1/health endpoint.

Uses httpx.AsyncClient + ASGITransport with the FastAPI app.
All infrastructure (DB, Redis, arq) is mocked — tests run without Docker.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_app_state():
    """Patch lifespan so we can test without real Redis/DB/arq."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = AsyncMock()
        app.state.redis.ping = AsyncMock(return_value=True)
        app.state.arq_pool = AsyncMock()
        yield

    return fake_lifespan


@pytest.mark.asyncio
async def test_health_returns_ok(mock_app_state):
    """GET /health returns 200 with status=ok."""
    with patch("app.main.lifespan", mock_app_state):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_cors_header(mock_app_state):
    """GET /api/v1/health responds to CORS preflight from localhost:3000."""
    with patch("app.main.lifespan", mock_app_state):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

    # CORS preflight must not be 4xx
    assert response.status_code in (200, 204)
