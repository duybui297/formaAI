"""Segment PATCH + regenerate API tests — REV-02, REV-04.

Stubs: will pass after Plan 04 implements segments.py route.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_patch_segment_edited_text(client):
    """PATCH /segments/{id} persists edited_text."""
    resp = await client.patch("/segments/test-seg-id", json={"edited_text": "Edited text"})
    assert resp.status_code == 200
    assert resp.json()["edited_text"] == "Edited text"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_patch_segment_clear_edit(client):
    """PATCH /segments/{id} with edited_text=null clears the edit."""
    resp = await client.patch("/segments/test-seg-id", json={"edited_text": None})
    assert resp.status_code == 200
    assert resp.json()["edited_text"] is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 04 segments route implementation", strict=False)
async def test_regenerate(client):
    """POST /segments/{id}/regenerate overwrites translated_text, preserves edited_text — D-02-20."""
    # REV-04: regenerate must not touch edited_text
    resp = await client.post("/segments/test-seg-id/regenerate")
    assert resp.status_code == 200
    data = resp.json()
    assert "translated_text" in data
