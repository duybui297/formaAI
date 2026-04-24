"""
Tests for GET /jobs/{id}/stream (SSE endpoint).

JOB-02: SSE stream yields progress events from Redis pub/sub
JOB-03: SSE stream closes on terminal status
Pitfall #3: pub/sub unsubscribed in finally block (no memory leak)
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pubsub_message(payload: dict) -> dict:
    """Build a dict that looks like a redis-py pub/sub message."""
    return {
        "type": "message",
        "channel": "job:test-job-id",
        "data": json.dumps(payload),
    }


def _make_mock_redis(messages: list[dict]) -> AsyncMock:
    """
    Build a mock Redis client whose pubsub().get_message() returns messages in
    sequence and then None (simulating no more messages).

    Appends a final None after all messages so the loop has a chance to see
    empty result before the terminal-status break fires.
    """
    pubsub = AsyncMock()
    pubsub.subscribe = AsyncMock(return_value=None)
    pubsub.unsubscribe = AsyncMock(return_value=None)
    pubsub.aclose = AsyncMock(return_value=None)

    # Return each message once, then None forever
    call_count = [0]
    raw_sequence = messages + [None]

    async def _get_message(**kwargs):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(raw_sequence):
            return raw_sequence[idx]
        return None

    pubsub.get_message = _get_message

    redis = AsyncMock()
    redis.pubsub = MagicMock(return_value=pubsub)
    return redis, pubsub


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sse_yields_progress_event():
    """
    SSE stream yields an 'event: progress' line when the worker publishes
    a running-status message to the Redis channel.
    """
    progress_msg = {
        "status": "running",
        "stage": "translate",
        "segments_done": 5,
        "segments_total": 20,
        "current_batch": 1,
        "retry_count": 0,
        "last_message": "Translating batch 1/4",
    }
    # After the progress event, yield a terminal message so the stream closes
    terminal_msg = {
        "status": "done",
        "stage": "done",
        "segments_done": 20,
        "segments_total": 20,
        "current_batch": 4,
        "retry_count": 0,
        "last_message": "Done",
    }
    mock_redis, pubsub = _make_mock_redis(
        [
            _make_pubsub_message(progress_msg),
            _make_pubsub_message(terminal_msg),
        ]
    )

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = mock_redis
        app.state.arq_pool = AsyncMock()
        yield

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.api.dependencies import get_redis

        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/jobs/test-job-id/stream",
                headers={"Accept": "text/event-stream"},
            )

        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    body = response.text
    # Should contain at least one "event: progress" line
    assert "event: progress" in body
    # Should contain the progress payload
    assert "segments_done" in body


@pytest.mark.asyncio
async def test_sse_closes_on_terminal_status():
    """
    SSE stream stops yielding events after a terminal status message
    (done/failed/needs_review).
    """
    terminal_msg = {
        "status": "done",
        "stage": "done",
        "segments_done": 10,
        "segments_total": 10,
        "current_batch": 2,
        "retry_count": 0,
        "last_message": "Done",
    }
    mock_redis, pubsub = _make_mock_redis(
        [_make_pubsub_message(terminal_msg)]
    )

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = mock_redis
        app.state.arq_pool = AsyncMock()
        yield

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.api.dependencies import get_redis

        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/jobs/test-job-id/stream",
                headers={"Accept": "text/event-stream"},
            )

        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.text
    # Terminal payload must appear in the stream
    assert "done" in body


@pytest.mark.asyncio
async def test_sse_unsubscribes_in_finally():
    """
    Pitfall #3: pubsub.unsubscribe() is called even when stream terminates
    normally via terminal status message.
    """
    terminal_msg = {
        "status": "failed",
        "stage": "failed",
        "segments_done": 0,
        "segments_total": 10,
        "current_batch": 0,
        "retry_count": 3,
        "last_message": "All retries exhausted",
    }
    mock_redis, pubsub = _make_mock_redis(
        [_make_pubsub_message(terminal_msg)]
    )

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = mock_redis
        app.state.arq_pool = AsyncMock()
        yield

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.api.dependencies import get_redis

        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.get(
                "/jobs/test-job-id/stream",
                headers={"Accept": "text/event-stream"},
            )

        app.dependency_overrides.clear()

    # Pitfall #3: always unsubscribe — must have been called
    pubsub.unsubscribe.assert_awaited_once()
    pubsub.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_sse_response_has_correct_headers():
    """SSE endpoint returns ping=15 and X-Accel-Buffering: no headers."""
    terminal_msg = {
        "status": "done",
        "stage": "done",
        "segments_done": 1,
        "segments_total": 1,
        "current_batch": 1,
        "retry_count": 0,
        "last_message": "Done",
    }
    mock_redis, pubsub = _make_mock_redis(
        [_make_pubsub_message(terminal_msg)]
    )

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.settings = MagicMock(
            database_url=MagicMock(get_secret_value=lambda: "sqlite+aiosqlite:///:memory:"),
            redis_url="redis://localhost:6379/0",
            data_dir="/tmp",
        )
        app.state.engine = MagicMock()
        app.state.redis = mock_redis
        app.state.arq_pool = AsyncMock()
        yield

    with patch("app.main.lifespan", fake_lifespan):
        from app.main import app
        from app.api.dependencies import get_redis

        app.dependency_overrides[get_redis] = lambda: mock_redis

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/jobs/test-job-id/stream",
                headers={"Accept": "text/event-stream"},
            )

        app.dependency_overrides.clear()

    assert response.status_code == 200
    # X-Accel-Buffering disables nginx buffering for SSE
    assert response.headers.get("x-accel-buffering") == "no"
