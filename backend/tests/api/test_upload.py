"""
Integration tests for POST /upload endpoint.

Tests use httpx.AsyncClient + ASGITransport with mocked infrastructure:
- SQLite in-memory DB (real ORM, no Postgres)
- Mocked arq pool (tracks enqueue_job calls)
- Temp directory for file storage

Covers:
- UPLD-03: size limit (413 on > 25 MB)
- UPLD-02: unsupported extension (415) + Phase 1 PPTX/PDF gate (422)
- UPLD-05: successful enqueue via shared arq pool
- T-06a-03: invalid target_lang rejected (422)
- DOCX-04: tracked-changes probe on upload
"""
from __future__ import annotations

import io
import os
import tempfile
import zipfile
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

# ---------------------------------------------------------------------------
# Helpers to create minimal valid DOCX bytes in memory
# ---------------------------------------------------------------------------

_CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
    ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""

_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""

_WORD_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""

_DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
    xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:r><w:t>Hello world</w:t></w:r>
    </w:p>
  </w:body>
</w:document>"""

_DOCUMENT_TRACKED_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p>
      <w:ins w:id="1" w:author="Author" w:date="2024-01-01T00:00:00Z">
        <w:r><w:t>Inserted text</w:t></w:r>
      </w:ins>
    </w:p>
  </w:body>
</w:document>"""


def _make_docx(document_xml: str = _DOCUMENT_XML) -> bytes:
    """Create a minimal valid DOCX zip in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", _RELS_XML)
        zf.writestr("word/_rels/document.xml.rels", _WORD_RELS_XML)
        zf.writestr("word/document.xml", document_xml)
    return buf.getvalue()


def _make_tracked_docx() -> bytes:
    """Create a DOCX with tracked changes (<w:ins> element)."""
    return _make_docx(document_xml=_DOCUMENT_TRACKED_XML)


# ---------------------------------------------------------------------------
# App fixture with mocked infrastructure
# ---------------------------------------------------------------------------


@pytest.fixture
async def app_and_tmp(tmp_path):
    """
    Yield a (app, arq_mock) tuple with:
    - SQLite in-memory DB, tables created
    - tmp_path used as data_dir
    - arq_pool mocked (enqueue_job is an AsyncMock)
    - get_current_active_user overridden with a superuser (TASK-3.7: bypasses
      entitlement checks so pre-existing upload tests stay green)

    Uses dependency_overrides for get_session, get_arq_pool, get_settings,
    and get_current_active_user so the app runs without real Redis/DB/arq/JWT.
    """
    import uuid as _uuid
    from app.db.models import Base, User
    from app.db.session import get_session
    from app.api.deps import get_arq_pool, get_current_active_user, get_settings
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

    superuser = User(
        id=str(_uuid.uuid4()),
        email="superuser@test.com",
        hashed_password="x",
        is_active=True,
        is_superuser=True,
    )

    # Set app.state directly so the running app can find settings/arq_pool
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

    def override_get_current_active_user():
        return superuser

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_arq_pool] = override_get_arq_pool
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_current_active_user] = override_get_current_active_user

    yield app, mock_arq

    app.dependency_overrides.clear()
    # Reset state to avoid leaking between test sessions (app is a module-level singleton)
    try:
        del app.state.settings
        del app.state.arq_pool
        del app.state.redis
        del app.state.engine
    except AttributeError:
        pass

    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests: size guard (UPLD-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_oversized_via_content_length(app_and_tmp):
    """413 returned when Content-Length header exceeds the ENTERPRISE ceiling (100 MB).

    TASK-3.7: superuser → ENTERPRISE (100MB limit). Tests use 101MB to exceed.
    """
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("test.docx", b"x", "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "en"},
            headers={"content-length": str(101 * 1024 * 1024)},
        )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_upload_rejects_oversized_streaming(app_and_tmp):
    """413 returned when actual file content exceeds ENTERPRISE ceiling (100 MB).

    TASK-3.7: superuser → ENTERPRISE (100MB limit). Tests use 101MB to exceed.
    """
    app, _ = app_and_tmp
    oversized = b"x" * (101 * 1024 * 1024)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("big.docx", oversized, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 413


# ---------------------------------------------------------------------------
# Tests: type check (UPLD-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_extension(app_and_tmp):
    """415 returned for file with unsupported extension (e.g. .txt)."""
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("doc.txt", b"hello", "text/plain")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 415


@pytest.mark.asyncio
async def test_upload_accepts_pdf_phase3(app_and_tmp):
    """202 returned for .pdf upload — Phase 3 enabled native PDF pipeline."""
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_upload_accepts_pptx_phase3(app_and_tmp):
    """202 returned for .pptx upload — Phase 3 enabled PPTX pipeline."""
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("slide.pptx", b"PK\x03\x04", "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# Tests: language validation (T-06a-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_rejects_invalid_target_lang(app_and_tmp):
    """422 returned for unknown target language code."""
    app, _ = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("test.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "xx-unknown"},
        )
    assert response.status_code == 422
    assert "xx-unknown" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_rejects_auto_as_target(app_and_tmp):
    """422 returned when 'auto' is used as target_lang."""
    app, _ = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("test.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "auto"},
        )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: successful upload + enqueue (UPLD-05)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_success_returns_job_id(app_and_tmp, tmp_path):
    """202 returned with job_id for valid DOCX upload."""
    app, mock_arq = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("test.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "vi"},
        )
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)
    assert len(data["job_id"]) == 36  # UUID4


@pytest.mark.asyncio
async def test_upload_enqueues_translate_job(app_and_tmp):
    """arq_pool.enqueue_job is called with 'translate_job' after successful upload."""
    app, mock_arq = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("test.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "en", "target_lang": "vi"},
        )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    # W11: arq pool's enqueue_job must have been called with translate_job + job_id
    mock_arq.enqueue_job.assert_called_once_with("translate_job", job_id)


@pytest.mark.asyncio
async def test_upload_no_tracked_changes_flag(app_and_tmp):
    """has_tracked_changes=False for a plain DOCX with no tracked changes."""
    app, _ = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("clean.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 202
    assert response.json()["has_tracked_changes"] is False


@pytest.mark.asyncio
async def test_upload_detects_tracked_changes(app_and_tmp):
    """has_tracked_changes=True for a DOCX containing <w:ins> elements."""
    app, _ = app_and_tmp
    docx_bytes = _make_tracked_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("tracked.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "en"},
        )
    assert response.status_code == 202
    assert response.json()["has_tracked_changes"] is True


@pytest.mark.asyncio
async def test_upload_persists_file_to_disk(app_and_tmp, tmp_path):
    """Uploaded file is saved to {data_dir}/jobs/{job_id}/source.docx."""
    app, _ = app_and_tmp
    docx_bytes = _make_docx()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/upload",
            files={"file": ("hello.docx", docx_bytes, "application/octet-stream")},
            data={"source_lang": "auto", "target_lang": "vi"},
        )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    expected_path = tmp_path / "jobs" / job_id / "source.docx"
    assert expected_path.exists(), f"Source file not found at {expected_path}"
    assert expected_path.read_bytes() == docx_bytes
