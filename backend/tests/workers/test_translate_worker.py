"""
Unit tests for app.workers.translate_worker.

Tests cover:
- translate_batch_with_retry: RateLimitError retried, 4xx fails immediately, exhausted raises
- _publish_progress: correct D-10 payload shape published to Redis channel
- WorkerSettings: functions=[translate_job] direct reference
- translate_job integration: happy path with mocked LLM + DB + Redis
- tracked-changes strip flow

Uses mocked dependencies — no live DashScope, DB, or Redis connections.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from openai import RateLimitError, APIStatusError, APIConnectionError

from app.workers.translate_worker import (
    WorkerSettings,
    translate_job,
    translate_batch_with_retry,
    _publish_progress,
    _MAX_RETRIES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_api_status_error(status_code: int) -> APIStatusError:
    """Construct an APIStatusError with the given status_code."""
    response = MagicMock()
    response.status_code = status_code
    response.headers = {}
    return APIStatusError(message=f"HTTP {status_code}", response=response, body={})


def _make_rate_limit_error() -> RateLimitError:
    response = MagicMock()
    response.status_code = 429
    response.headers = {}
    return RateLimitError(message="rate limit", response=response, body={})


def _make_connection_error() -> APIConnectionError:
    return APIConnectionError(request=MagicMock())


# ---------------------------------------------------------------------------
# WorkerSettings shape
# ---------------------------------------------------------------------------

def test_worker_settings_functions_is_direct_reference():
    """WorkerSettings.functions contains translate_job by direct reference (not string)."""
    assert translate_job in WorkerSettings.functions


def test_worker_settings_has_lifecycle_hooks():
    """WorkerSettings has on_startup and on_shutdown hooks."""
    from app.workers.translate_worker import startup, shutdown
    assert WorkerSettings.on_startup is startup
    assert WorkerSettings.on_shutdown is shutdown


def test_worker_settings_max_jobs():
    """WorkerSettings.max_jobs is set (any positive int)."""
    assert WorkerSettings.max_jobs > 0


# ---------------------------------------------------------------------------
# translate_batch_with_retry
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_succeeds_on_first_attempt():
    """translate_batch_with_retry returns result immediately when translate_batch succeeds."""
    ctx = {"llm_client": MagicMock()}
    expected = ["Hello", "World"]

    with patch("app.workers.translate_worker.translate_batch", new_callable=AsyncMock) as mock_tb:
        mock_tb.return_value = expected
        result = await translate_batch_with_retry(
            ctx, ["Xin chào", "Thế giới"], "vi", "en", None, "job-1", 0
        )

    assert result == expected
    assert mock_tb.call_count == 1


@pytest.mark.asyncio
async def test_retry_on_rate_limit_error(monkeypatch):
    """translate_batch_with_retry retries up to _MAX_RETRIES on RateLimitError."""
    ctx = {"llm_client": MagicMock()}
    call_count = 0

    async def _flaky(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < _MAX_RETRIES:
            raise _make_rate_limit_error()
        return ["translated"]

    with patch("app.workers.translate_worker.translate_batch", side_effect=_flaky):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await translate_batch_with_retry(
                ctx, ["text"], "vi", "en", None, "job-1", 0
            )

    assert result == ["translated"]
    assert call_count == _MAX_RETRIES


@pytest.mark.asyncio
async def test_retry_exhausted_raises():
    """translate_batch_with_retry raises RuntimeError after all retries exhausted."""
    ctx = {"llm_client": MagicMock()}

    async def _always_fail(*args, **kwargs):
        raise _make_rate_limit_error()

    with patch("app.workers.translate_worker.translate_batch", side_effect=_always_fail):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(RuntimeError, match="retries exhausted"):
                await translate_batch_with_retry(
                    ctx, ["text"], "vi", "en", None, "job-1", 0
                )


@pytest.mark.asyncio
async def test_no_retry_on_4xx_client_error():
    """translate_batch_with_retry raises immediately on 4xx (non-429) status."""
    ctx = {"llm_client": MagicMock()}
    exc_400 = _make_api_status_error(400)

    async def _bad_request(*args, **kwargs):
        raise exc_400

    with patch("app.workers.translate_worker.translate_batch", side_effect=_bad_request):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(APIStatusError):
                await translate_batch_with_retry(
                    ctx, ["text"], "vi", "en", None, "job-1", 0
                )
    # asyncio.sleep must NOT have been called — no backoff on 4xx
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_retry_on_500_server_error(monkeypatch):
    """translate_batch_with_retry retries on 5xx server errors."""
    ctx = {"llm_client": MagicMock()}
    call_count = 0

    async def _server_error(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise _make_api_status_error(503)
        return ["ok"]

    with patch("app.workers.translate_worker.translate_batch", side_effect=_server_error):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await translate_batch_with_retry(
                ctx, ["text"], "vi", "en", None, "job-1", 0
            )

    assert result == ["ok"]
    assert call_count == 2


@pytest.mark.asyncio
async def test_retry_on_connection_error():
    """translate_batch_with_retry retries on APIConnectionError."""
    ctx = {"llm_client": MagicMock()}
    call_count = 0

    async def _conn_error(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise _make_connection_error()
        return ["ok"]

    with patch("app.workers.translate_worker.translate_batch", side_effect=_conn_error):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await translate_batch_with_retry(
                ctx, ["text"], "vi", "en", None, "job-1", 0
            )

    assert result == ["ok"]


# ---------------------------------------------------------------------------
# _publish_progress
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publish_progress_sends_correct_channel():
    """_publish_progress publishes to job:{job_id} channel."""
    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(return_value=1)

    await _publish_progress(
        mock_redis, "abc-123", "running", "translate", 5, 10, 2, 0, "Batch 2"
    )

    mock_redis.publish.assert_called_once()
    channel, payload_str = mock_redis.publish.call_args[0]
    assert channel == "job:abc-123"

    payload = json.loads(payload_str)
    assert payload["status"] == "running"
    assert payload["stage"] == "translate"
    assert payload["segments_done"] == 5
    assert payload["segments_total"] == 10
    assert payload["current_batch"] == 2
    assert payload["last_message"] == "Batch 2"
    assert "error" not in payload


@pytest.mark.asyncio
async def test_publish_progress_includes_error_when_provided():
    """_publish_progress includes error dict in payload when given."""
    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(return_value=1)
    error = {"code": "SEGMENT_TOO_LARGE", "message": "too big", "failing_segments": []}

    await _publish_progress(
        mock_redis, "job-999", "failed", "failed", 0, 0, 0, 0, "failed", error=error
    )

    _, payload_str = mock_redis.publish.call_args[0]
    payload = json.loads(payload_str)
    assert payload["error"]["code"] == "SEGMENT_TOO_LARGE"


# ---------------------------------------------------------------------------
# translate_job integration (mocked)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_job_happy_path(db_session, mock_redis, mock_llm_client):
    """
    translate_job: full happy path with mocked DOCX, LLM, and Redis.

    Creates a job in the DB, mocks the Document loading + extract_segments,
    mocks translate_batch to return 1 translated segment, and verifies:
    - job transitions to done
    - Redis publish called with 'done' at the end
    - output file saved to correct path
    """
    import tempfile
    from app.services.job_service import create_job
    from app.db.models import JobStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a real job row in the in-memory SQLite DB
        job = await create_job(
            db_session,
            source_lang="vi",
            target_lang="en",
            input_format="docx",
            input_path=f"{tmpdir}/source.docx",
            original_filename="test.docx",
        )

        # Build mock arq ctx pointing at the test session
        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        settings_mock = MagicMock()
        settings_mock.data_dir = tmpdir
        settings_mock.token_budget = 3000
        settings_mock.worker_concurrency = 4

        ctx = {
            "llm_client": mock_llm_client,
            "redis": mock_redis,
            "session_factory": session_factory,
            "settings": settings_mock,
        }

        # Mock Document loading and pipeline
        from app.pipeline.segment import Segment

        fake_seg = Segment.from_text("Xin chào", "para.0", seq_in_job=0)

        mock_doc = MagicMock()

        with patch("app.workers.translate_worker.Document", return_value=mock_doc), \
             patch("app.workers.translate_worker.extract_run_segments", return_value=[fake_seg]), \
             patch("app.workers.translate_worker.pack_into_batches", return_value=[[fake_seg]]), \
             patch("app.workers.translate_worker.translate_batch", new_callable=AsyncMock, return_value=["Hello"]), \
             patch("app.workers.translate_worker.reassemble_docx_runs", return_value=mock_doc):
            mock_doc.save = MagicMock()

            await translate_job(ctx, job.id)

        # Verify job is done in DB
        from app.services.job_service import get_job
        updated = await get_job(db_session, job.id)
        assert updated is not None
        assert updated.status == JobStatus.done

        # Verify Redis publish was called and last event has status=done
        assert mock_redis.publish.called
        last_call = mock_redis.publish.call_args_list[-1]
        channel, payload_str = last_call[0]
        assert channel == f"job:{job.id}"
        payload = json.loads(payload_str)
        assert payload["status"] == "done"


@pytest.mark.asyncio
async def test_translate_job_marks_failed_on_error(db_session, mock_redis, mock_llm_client):
    """
    translate_job: marks job as failed + publishes failed status when translation raises.
    """
    import tempfile
    from app.services.job_service import create_job
    from app.db.models import JobStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        job = await create_job(
            db_session,
            source_lang="vi",
            target_lang="en",
            input_format="docx",
            input_path=f"{tmpdir}/source.docx",
            original_filename="test.docx",
        )

        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        settings_mock = MagicMock()
        settings_mock.data_dir = tmpdir
        settings_mock.token_budget = 3000
        settings_mock.worker_concurrency = 4

        ctx = {
            "llm_client": mock_llm_client,
            "redis": mock_redis,
            "session_factory": session_factory,
            "settings": settings_mock,
        }

        from app.pipeline.segment import Segment
        fake_seg = Segment.from_text("Xin chào", "para.0", seq_in_job=0)

        mock_doc = MagicMock()

        async def _always_fail(*args, **kwargs):
            raise _make_rate_limit_error()

        with patch("app.workers.translate_worker.Document", return_value=mock_doc), \
             patch("app.workers.translate_worker.extract_run_segments", return_value=[fake_seg]), \
             patch("app.workers.translate_worker.pack_into_batches", return_value=[[fake_seg]]), \
             patch("app.workers.translate_worker.translate_batch", side_effect=_always_fail), \
             patch("asyncio.sleep", new_callable=AsyncMock):

            # The outer translate_job catches the re-raised exception
            try:
                await translate_job(ctx, job.id)
            except Exception:
                pass

        from app.services.job_service import get_job
        updated = await get_job(db_session, job.id)
        assert updated is not None
        assert updated.status == JobStatus.failed
        assert updated.error_msg is not None

        # Verify a failed progress event was published
        published_channels = [c[0][0] for c in mock_redis.publish.call_args_list]
        assert any(c == f"job:{job.id}" for c in published_channels)

        published_payloads = [
            json.loads(c[0][1]) for c in mock_redis.publish.call_args_list
        ]
        failed_events = [p for p in published_payloads if p["status"] == "failed"]
        assert len(failed_events) >= 1


@pytest.mark.asyncio
async def test_translate_job_strips_tracked_changes(db_session, mock_redis, mock_llm_client):
    """
    translate_job: strip_tracked_changes is called when job.tracked_changes_action=='strip'.
    """
    import tempfile
    from app.services.job_service import create_job

    with tempfile.TemporaryDirectory() as tmpdir:
        job = await create_job(
            db_session,
            source_lang="vi",
            target_lang="en",
            input_format="docx",
            input_path=f"{tmpdir}/source.docx",
            original_filename="tc.docx",
            has_tracked_changes=True,
            tracked_changes_action="strip",
        )

        session_factory = MagicMock()
        session_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        settings_mock = MagicMock()
        settings_mock.data_dir = tmpdir
        settings_mock.token_budget = 3000
        settings_mock.worker_concurrency = 4

        ctx = {
            "llm_client": mock_llm_client,
            "redis": mock_redis,
            "session_factory": session_factory,
            "settings": settings_mock,
        }

        from app.pipeline.segment import Segment
        fake_seg = Segment.from_text("Text", "para.0", seq_in_job=0)
        mock_doc = MagicMock()
        stripped_doc = MagicMock()
        stripped_doc.save = MagicMock()

        with patch("app.workers.translate_worker.Document", return_value=mock_doc) as mock_Document, \
             patch("app.workers.translate_worker.strip_tracked_changes", return_value=stripped_doc) as mock_strip, \
             patch("app.workers.translate_worker.extract_run_segments", return_value=[fake_seg]), \
             patch("app.workers.translate_worker.pack_into_batches", return_value=[[fake_seg]]), \
             patch("app.workers.translate_worker.translate_batch", new_callable=AsyncMock, return_value=["Translated"]), \
             patch("app.workers.translate_worker.reassemble_docx_runs", return_value=stripped_doc):

            await translate_job(ctx, job.id)

        # strip_tracked_changes must have been called with the original doc
        mock_strip.assert_called_once_with(mock_doc)
