"""
TASK-3.7: API-level entitlement enforcement tests.

Subtasks and their -k selectors (function names include selector):
  3.7-b  -k licenses_me
  3.7-c  -k upload_requires_license
  3.7-d  -k per_tier_file_size
  3.7-e  -k monthly_quota
  3.7-f  -k ocr_glossary_gated

All tests use SQLite in-memory DB, mocked arq/redis, no JWT — auth is bypassed
via dependency_overrides using controlled User objects.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ---------------------------------------------------------------------------
# Minimal DOCX helper
# ---------------------------------------------------------------------------

def _make_docx() -> bytes:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""
    word_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body>
</w:document>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/_rels/document.xml.rels", word_rels)
        zf.writestr("word/document.xml", document)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Base app fixture — no auth override; each test injects its own user.
# ---------------------------------------------------------------------------

@pytest.fixture
async def _base_app(tmp_path):
    from app.db.models import Base
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_settings
    from app.main import app

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_arq = AsyncMock()
    mock_arq.enqueue_job = AsyncMock(return_value=MagicMock())

    mock_settings = MagicMock(
        database_url=MagicMock(get_secret_value=lambda: TEST_DB_URL),
        redis_url="redis://localhost:6379/0",
        data_dir=str(tmp_path),
        ocr_text_density_threshold=0.05,
    )

    app.state.settings = mock_settings
    app.state.arq_pool = mock_arq
    app.state.redis = AsyncMock()
    app.state.engine = engine

    async def override_get_session():
        async with session_factory() as session:
            yield session

    def override_get_arq_pool(request=None):
        return mock_arq

    def override_get_settings(request=None):
        return mock_settings

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings

    yield app, session_factory, mock_arq

    app.dependency_overrides.clear()
    try:
        del app.state.settings
        del app.state.arq_pool
        del app.state.redis
        del app.state.engine
    except AttributeError:
        pass
    await engine.dispose()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _new_user(is_superuser: bool = False) -> "User":  # noqa: F821
    from app.db.models import User
    return User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=is_superuser,
    )


async def _seed_user(session: AsyncSession, user) -> object:
    session.add(user)
    await session.commit()
    return user


async def _seed_license(session: AsyncSession, user, tier, status):
    from app.db.models import License
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


async def _seed_job(session: AsyncSession, user_id: str, created_at: datetime | None = None):
    from app.db.models import Job
    from sqlalchemy import update
    job = Job(
        id=str(uuid.uuid4()),
        status="queued",
        source_lang="en",
        target_lang="vi",
        input_format="docx",
        input_path="/tmp/test.docx",
        original_filename="test.docx",
        user_id=user_id,
    )
    session.add(job)
    await session.flush()
    if created_at is not None:
        await session.execute(
            update(Job).where(Job.id == job.id).values(created_at=created_at)
        )
    await session.commit()
    return job


def _inject_user(app, user) -> None:
    from app.api.deps import get_current_active_user
    app.dependency_overrides[get_current_active_user] = lambda: user


# ===========================================================================
# 3.7-b: GET /licenses/me  (-k licenses_me)
# ===========================================================================

@pytest.mark.asyncio
async def test_licenses_me_no_active_license(_base_app):
    """User with no license: has_active=false, null limit fields, 200."""
    app, session_factory, _ = _base_app
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/licenses/me")

    assert r.status_code == 200
    body = r.json()
    assert body["has_active"] is False
    assert body["tier"] is None
    assert body["max_file_bytes"] is None
    assert body["monthly_quota"] is None
    assert body["quota_used"] == 0
    assert body["ocr_allowed"] is None
    assert body["glossary_allowed"] is None


@pytest.mark.asyncio
async def test_licenses_me_trial(_base_app):
    """Active TRIAL license returns correct entitlement values."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/licenses/me")

    assert r.status_code == 200
    body = r.json()
    assert body["has_active"] is True
    assert body["tier"] == "TRIAL"
    assert body["max_file_bytes"] == 5 * 1024 * 1024
    assert body["monthly_quota"] == 10
    assert body["ocr_allowed"] is False
    assert body["glossary_allowed"] is False


@pytest.mark.asyncio
async def test_licenses_me_pro(_base_app):
    """Active PRO license returns correct entitlement values."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/licenses/me")

    assert r.status_code == 200
    body = r.json()
    assert body["has_active"] is True
    assert body["tier"] == "PRO"
    assert body["max_file_bytes"] == 50 * 1024 * 1024
    assert body["monthly_quota"] is None
    assert body["ocr_allowed"] is True
    assert body["glossary_allowed"] is True


@pytest.mark.asyncio
async def test_licenses_me_superuser_gets_enterprise(_base_app):
    """Superuser: has_active=true with ENTERPRISE (no license row needed)."""
    app, session_factory, _ = _base_app
    async with session_factory() as session:
        user = await _seed_user(session, _new_user(is_superuser=True))
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/licenses/me")

    assert r.status_code == 200
    body = r.json()
    assert body["has_active"] is True
    assert body["tier"] == "ENTERPRISE"
    assert body["max_file_bytes"] == 100 * 1024 * 1024
    assert body["monthly_quota"] is None
    assert body["ocr_allowed"] is True
    assert body["glossary_allowed"] is True


@pytest.mark.asyncio
async def test_licenses_me_quota_used_counts_current_month(_base_app):
    """quota_used reflects jobs created this calendar month (UTC)."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
        now = datetime.now(timezone.utc)
        await _seed_job(session, user.id, created_at=now)
        await _seed_job(session, user.id, created_at=now)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/licenses/me")

    assert r.status_code == 200
    assert r.json()["quota_used"] == 2


# ===========================================================================
# 3.7-c: POST /upload requires license  (-k upload_requires_license)
# ===========================================================================

@pytest.mark.asyncio
async def test_upload_requires_license_no_license_returns_403(_base_app):
    """User with no active license → 403 LICENSE_REQUIRED."""
    app, session_factory, _ = _base_app
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 403
    detail = r.json().get("detail", {})
    assert detail.get("error") == "LICENSE_REQUIRED"


@pytest.mark.asyncio
async def test_upload_requires_license_superuser_exempt(_base_app):
    """Superuser has no license row but upload succeeds (202)."""
    app, session_factory, _ = _base_app
    async with session_factory() as session:
        user = await _seed_user(session, _new_user(is_superuser=True))
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 202


@pytest.mark.asyncio
async def test_upload_requires_license_active_license_proceeds(_base_app):
    """User with active TRIAL license → upload succeeds (202)."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 202


# ===========================================================================
# 3.7-d: Per-tier file size  (-k per_tier_file_size)
# ===========================================================================

@pytest.mark.asyncio
async def test_per_tier_file_size_trial_just_over_5mb_returns_413(_base_app):
    """TRIAL: 5MB + 1 byte → 413 with tier limit in message."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    oversized = b"x" * (5 * 1024 * 1024 + 1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("big.docx", oversized, "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 413
    assert "5" in r.json().get("detail", "")


@pytest.mark.asyncio
async def test_per_tier_file_size_trial_under_limit_ok(_base_app):
    """TRIAL: valid DOCX well under 5MB → 202."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 202


@pytest.mark.asyncio
async def test_per_tier_file_size_pro_allows_over_5mb(_base_app):
    """PRO: 6MB file (> TRIAL 5MB limit) is NOT rejected with 413."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("medium.docx", b"x" * (6 * 1024 * 1024), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code != 413


@pytest.mark.asyncio
async def test_per_tier_file_size_trial_content_length_fast_path(_base_app):
    """TRIAL: Content-Length > 5MB → fast-path 413 before body is read."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", b"x", "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
            headers={"content-length": str(6 * 1024 * 1024)},
        )

    assert r.status_code == 413


# ===========================================================================
# 3.7-e: Monthly quota  (-k monthly_quota)
# ===========================================================================

@pytest.mark.asyncio
async def test_monthly_quota_trial_11th_upload_rejected(_base_app):
    """TRIAL user with 10 jobs this month → 11th upload → 403 QUOTA_EXCEEDED."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
        now = datetime.now(timezone.utc)
        for _ in range(10):
            await _seed_job(session, user.id, created_at=now)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 403
    detail = r.json().get("detail", {})
    assert detail.get("error") == "QUOTA_EXCEEDED"


@pytest.mark.asyncio
async def test_monthly_quota_trial_10th_upload_allowed(_base_app):
    """TRIAL user with 9 jobs this month → 10th upload → 202."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
        now = datetime.now(timezone.utc)
        for _ in range(9):
            await _seed_job(session, user.id, created_at=now)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 202


@pytest.mark.asyncio
async def test_monthly_quota_pro_never_blocked(_base_app):
    """PRO: unlimited quota → never blocked even with 50 jobs."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
        now = datetime.now(timezone.utc)
        for _ in range(50):
            await _seed_job(session, user.id, created_at=now)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    assert r.status_code == 202


@pytest.mark.asyncio
async def test_monthly_quota_last_month_jobs_dont_count(_base_app):
    """10 jobs from last month don't count toward this month's quota."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
        now = datetime.now(timezone.utc)
        # First of this month minus 1 day = last month
        last_month = (now.replace(day=1) - timedelta(days=1)).replace(tzinfo=timezone.utc)
        for _ in range(10):
            await _seed_job(session, user.id, created_at=last_month)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )

    # Last month's jobs quota_used=0 this month → allowed
    assert r.status_code == 202


# ===========================================================================
# 3.7-f: OCR and glossary feature gates  (-k ocr_glossary_gated)
# ===========================================================================

@pytest.mark.asyncio
async def test_ocr_glossary_gated_trial_ocr_returns_403(_base_app):
    """TRIAL + is_scanned_override=True → 403 FEATURE_NOT_IN_PLAN (feature=ocr)."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
            data={"source_lang": "en", "target_lang": "vi", "is_scanned_override": "true"},
        )

    assert r.status_code == 403
    detail = r.json().get("detail", {})
    assert detail.get("error") == "FEATURE_NOT_IN_PLAN"
    assert detail.get("feature") == "ocr"


@pytest.mark.asyncio
async def test_ocr_glossary_gated_pro_ocr_allowed(_base_app):
    """PRO + is_scanned_override=True → not a feature gate 403."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.PRO, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
            data={"source_lang": "en", "target_lang": "vi", "is_scanned_override": "true"},
        )

    if r.status_code == 403:
        assert r.json().get("detail", {}).get("error") != "FEATURE_NOT_IN_PLAN"


@pytest.mark.asyncio
async def test_ocr_glossary_gated_trial_glossary_returns_403(_base_app):
    """TRIAL + glossary_id → 403 FEATURE_NOT_IN_PLAN (feature=glossary)."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.TRIAL, LicenseStatus.ACTIVE)
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi", "glossary_id": str(uuid.uuid4())},
        )

    assert r.status_code == 403
    detail = r.json().get("detail", {})
    assert detail.get("error") == "FEATURE_NOT_IN_PLAN"
    assert detail.get("feature") == "glossary"


@pytest.mark.asyncio
async def test_ocr_glossary_gated_enterprise_glossary_allowed(_base_app):
    """ENTERPRISE + valid glossary_id → not a feature gate 403."""
    app, session_factory, _ = _base_app
    from app.db.models import LicenseTier, LicenseStatus, Glossary
    async with session_factory() as session:
        user = await _seed_user(session, _new_user())
        await _seed_license(session, user, LicenseTier.ENTERPRISE, LicenseStatus.ACTIVE)
        g = Glossary(
            id=str(uuid.uuid4()),
            name="Test",
            source_lang="en",
            target_lang="vi",
        )
        session.add(g)
        await session.commit()
        glossary_id = g.id
    _inject_user(app, user)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("test.docx", _make_docx(), "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi", "glossary_id": glossary_id},
        )

    if r.status_code == 403:
        assert r.json().get("detail", {}).get("feature") != "glossary"
