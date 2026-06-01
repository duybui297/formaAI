"""
TASK-3.7-h: Worker OCR gate — auto-detected scanned PDF blocked for TRIAL tier.

Behavior under test:
- A scanned_pdf job owned by a TRIAL user → worker does NOT call OCR extractor,
  fails the job with FEATURE_NOT_IN_PLAN / feature="ocr", matching the upload-time
  403 error shape so the FE shows the same "OCR requires Pro" message.
- A scanned_pdf job owned by a PRO user → OCR extractor IS called.
- A scanned_pdf job with null user_id (legacy pre-auth) → OCR runs as before
  (no owner to gate against; keep existing behaviour).

All external dependencies (OCR extractor, DB, Redis) are mocked — no real
PaddleOCR, Postgres, or DashScope connections.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Job, JobStatus, License, LicenseStatus, LicenseTier, User
from app.services.job_service import create_job


# ---------------------------------------------------------------------------
# Helpers — mirrors _make_user / _seed_license from test_entitlements.py
# ---------------------------------------------------------------------------

def _make_user(is_superuser: bool = False) -> User:
    return User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=is_superuser,
    )


async def _seed_license(
    session: AsyncSession,
    user: User,
    tier: LicenseTier,
    status: LicenseStatus = LicenseStatus.ACTIVE,
) -> License:
    lic = License(
        id=str(uuid.uuid4()),
        key_hash=str(uuid.uuid4()),
        tier=tier,
        status=status,
        customer_id=str(user.id),
        max_devices=1,
    )
    session.add(lic)
    await session.commit()
    return lic


async def _seed_job(
    session: AsyncSession,
    user_id: str | None,
    input_format: str = "scanned_pdf",
) -> Job:
    """Create and persist a minimal scanned_pdf Job row."""
    job = Job(
        id=str(uuid.uuid4()),
        status=JobStatus.queued,
        source_lang="vi",
        target_lang="en",
        input_format=input_format,
        input_path="/tmp/fake.pdf",
        original_filename="test.pdf",
        user_id=user_id,
        glossary_id=None,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# Fixtures — build a complete mock arq ctx (settings + session + redis)
# ---------------------------------------------------------------------------

def _make_mock_settings(tmp_path_str: str = "/tmp") -> MagicMock:
    """Minimal Settings mock for the worker."""
    s = MagicMock()
    s.data_dir = tmp_path_str
    s.token_budget = 3000
    s.worker_concurrency = 1
    s.ocr_page_dpi = 72
    s.ocr_text_density_threshold = 50.0
    s.expansion_thresholds_dict = {}
    return s


def _make_arq_ctx(session: AsyncSession, redis: AsyncMock, settings: MagicMock) -> dict:
    """Build a ctx dict that injects the test session into session_factory."""
    session_factory = MagicMock()
    session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
    session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    llm = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock()]
    mock_resp.choices[0].message.content = "Translated"
    mock_resp.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
    llm.chat.completions.create = AsyncMock(return_value=mock_resp)

    return {
        "llm_client": llm,
        "redis": redis,
        "session_factory": session_factory,
        "settings": settings,
        "ocr_pipeline": MagicMock(),  # won't be reached for TRIAL
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_worker_blocks_ocr_for_trial(db_session: AsyncSession):
    """
    TASK-3.7-h: scanned_pdf job owned by a TRIAL user → worker fails the job
    with FEATURE_NOT_IN_PLAN / feature="ocr" without calling extract_scanned_pdf_segments.
    """
    # Arrange — TRIAL user + scanned_pdf job
    user = _make_user()
    db_session.add(user)
    await db_session.flush()
    await _seed_license(db_session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    job = await _seed_job(db_session, user_id=str(user.id))

    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    ctx = _make_arq_ctx(db_session, redis, _make_mock_settings())

    with patch(
        "app.pipeline.scanned_pdf.extractor.extract_scanned_pdf_segments",
        new_callable=AsyncMock,
    ) as mock_ocr, patch(
        "app.workers.translate_worker.append_error_log"
    ):
        from app.workers.translate_worker import _run_translation
        await _run_translation(ctx, db_session, job.id)

    # OCR extractor must NOT have been called
    mock_ocr.assert_not_called()

    # Job must be FAILED in the DB
    await db_session.refresh(job)
    assert job.status == JobStatus.failed

    # error_msg must name the plan gate
    assert job.error_msg is not None
    assert "not available" in job.error_msg.lower() or "plan" in job.error_msg.lower()

    # Redis progress publish must include FEATURE_NOT_IN_PLAN error
    assert redis.publish.called
    import json
    published_payloads = [
        json.loads(call.args[1])
        for call in redis.publish.call_args_list
        if len(call.args) >= 2
    ]
    failed_events = [p for p in published_payloads if p.get("status") == "failed"]
    assert failed_events, "Expected at least one 'failed' SSE event"
    last_fail = failed_events[-1]
    assert last_fail.get("error", {}).get("error") == "FEATURE_NOT_IN_PLAN"
    assert last_fail.get("error", {}).get("feature") == "ocr"


@pytest.mark.asyncio
async def test_worker_allows_ocr_for_pro(db_session: AsyncSession):
    """
    TASK-3.7-h: scanned_pdf job owned by a PRO user → OCR extractor IS called.
    """
    user = _make_user()
    db_session.add(user)
    await db_session.flush()
    await _seed_license(db_session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
    job = await _seed_job(db_session, user_id=str(user.id))

    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)

    # Mock OCR extractor to return an empty segment list (avoids full pipeline).
    # pymupdf.open is imported inside the match case, so patch the module-level name.
    # The mock doc needs __len__ so the worker can call len(_pdf_doc).
    _mock_doc = MagicMock()
    _mock_doc.__len__ = MagicMock(return_value=1)
    with patch(
        "app.pipeline.scanned_pdf.extractor.extract_scanned_pdf_segments",
        new_callable=AsyncMock,
        return_value=([], []),
    ) as mock_ocr, patch(
        "pymupdf.open", return_value=_mock_doc
    ), patch(
        "os.makedirs"
    ):
        ctx = _make_arq_ctx(db_session, redis, _make_mock_settings())
        from app.workers.translate_worker import _run_translation
        await _run_translation(ctx, db_session, job.id)

    # OCR extractor MUST have been called (gate passed)
    mock_ocr.assert_called_once()


@pytest.mark.asyncio
async def test_worker_allows_ocr_for_null_user_id(db_session: AsyncSession):
    """
    TASK-3.7-h: scanned_pdf job with null user_id (legacy pre-auth job) →
    OCR runs as before. Gate does not fire when owner cannot be resolved.
    """
    job = await _seed_job(db_session, user_id=None)

    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)

    _mock_doc = MagicMock()
    _mock_doc.__len__ = MagicMock(return_value=1)
    with patch(
        "app.pipeline.scanned_pdf.extractor.extract_scanned_pdf_segments",
        new_callable=AsyncMock,
        return_value=([], []),
    ) as mock_ocr, patch(
        "pymupdf.open", return_value=_mock_doc
    ), patch(
        "os.makedirs"
    ):
        ctx = _make_arq_ctx(db_session, redis, _make_mock_settings())
        from app.workers.translate_worker import _run_translation
        await _run_translation(ctx, db_session, job.id)

    # OCR extractor MUST have been called (no gate for null owner)
    mock_ocr.assert_called_once()
