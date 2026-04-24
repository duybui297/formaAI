"""
Integration tests for GET /languages endpoint.

LANG-01: Verifies that response has dict-shaped entries with code/name/qwen_code keys (B5 fix).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from contextlib import asynccontextmanager


@pytest.fixture
def mock_lifespan():
    """Patch lifespan so tests run without real Redis/DB/arq."""

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(
                get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"
            ),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = AsyncMock()
        app.state.arq_pool = AsyncMock()
        yield

    return fake_lifespan


@pytest.mark.asyncio
async def test_languages_returns_list_of_dicts(mock_lifespan):
    """GET /languages returns a list where every item has code, name, qwen_code."""
    with patch("app.main.lifespan", mock_lifespan):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/languages")

    assert response.status_code == 200
    data = response.json()
    assert "languages" in data
    langs = data["languages"]
    assert isinstance(langs, list)
    assert len(langs) > 0

    # B5 fix: each entry must be a dict with code/name/qwen_code
    for lang in langs:
        assert "code" in lang, f"Missing 'code' in {lang}"
        assert "name" in lang, f"Missing 'name' in {lang}"
        assert "qwen_code" in lang, f"Missing 'qwen_code' in {lang}"


@pytest.mark.asyncio
async def test_languages_contains_priority_languages(mock_lifespan):
    """GET /languages includes the four priority languages + auto-detect."""
    with patch("app.main.lifespan", mock_lifespan):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/languages")

    codes = {lang["code"] for lang in response.json()["languages"]}
    assert "auto" in codes
    assert "vi" in codes
    assert "en" in codes
    assert "ja" in codes
    assert "zh" in codes


@pytest.mark.asyncio
async def test_languages_auto_detect_option(mock_lifespan):
    """GET /languages response includes auto_detect_option field."""
    with patch("app.main.lifespan", mock_lifespan):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/languages")

    data = response.json()
    assert data.get("auto_detect_option") == "auto"


@pytest.mark.asyncio
async def test_languages_vi_qwen_code(mock_lifespan):
    """GET /languages: Vietnamese entry has qwen_code='Vietnamese'."""
    with patch("app.main.lifespan", mock_lifespan):
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/languages")

    vi_lang = next(
        (l for l in response.json()["languages"] if l["code"] == "vi"), None
    )
    assert vi_lang is not None
    assert vi_lang["qwen_code"] == "Vietnamese"
    assert vi_lang["name"] == "Vietnamese"
