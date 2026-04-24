"""Export service tests — REV-05, REV-06.

Stubs: will pass after Plan 04 implements export_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_prefers_edited_text(db_session, tmp_path):
    """export_job uses edited_text over translated_text when both present — D-02-20."""
    from app.services.export_service import export_job
    # Implementation to be verified once export_service is built


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_empty_string_edit_not_dropped(db_session, tmp_path):
    """export_job respects edited_text='' (explicit clear) — Pitfall 5: no `or` fallback."""
    from app.services.export_service import export_job
    # edited_text="" must produce "" in output, not fall back to translated_text


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 export_service implementation", strict=False)
async def test_export_idempotent(db_session, tmp_path):
    """Calling export_job twice produces identical output, segment rows unchanged — REV-06."""
    from app.services.export_service import export_job
    # Two exports should produce same file; segment.edited_text unchanged after export
