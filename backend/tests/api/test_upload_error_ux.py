"""
Error detail payload shape tests for POST /upload.

test_upload.py covers status codes (415, 422). This file covers the DETAIL field
content that UploadForm.tsx surfaces to the user. Both layers must pass for the
frontend error UX to work end-to-end.

Existing status-code coverage in test_upload.py:
  - test_upload_rejects_unsupported_extension -> 415 for .txt
  - test_upload_rejects_pdf_phase1 -> 422 for .pdf (Phase 1 gate)
  - test_upload_rejects_pptx_phase1 -> 422 for .pptx (Phase 1 gate)
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_upload_txt_detail_mentions_docx(app_and_tmp):
    """415 unsupported: detail field non-empty and mentions the expected format."""
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("note.txt", b"hello", "text/plain")},
            data={"source_lang": "en", "target_lang": "vi"},
        )
    assert r.status_code == 415
    body = r.json()
    assert "detail" in body and body["detail"]
    assert any(kw in body["detail"].lower() for kw in ("docx", "supported", "phase 1"))


@pytest.mark.asyncio
async def test_upload_pdf_phase1_gate_detail(app_and_tmp):
    """Phase 1 gate: .pdf returns 422 with actionable detail (not 415).

    .pdf is in ALLOWED_EXTENSIONS so extension check passes; Phase 1 gate rejects it.
    """
    app, _ = app_and_tmp
    pdf_magic = b"%PDF-1.4\n%stub"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/upload",
            files={"file": ("doc.pdf", pdf_magic, "application/pdf")},
            data={"source_lang": "en", "target_lang": "vi"},
        )
    assert r.status_code == 422
    body = r.json()
    assert "detail" in body and body["detail"]
    assert any(kw in body["detail"].lower() for kw in ("pdf", "phase", "docx", "supported"))
