"""Glossary CRUD API tests — GLOS-01, GLOS-05.

Stubs: will pass after Plan 03 implements glossaries.py route.
Response shape: {"glossaries": [...]} — wrapped, mirrors Phase 1 /jobs response.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_list_glossaries_empty(client):
    """GET /glossaries returns {"glossaries": []} when no glossaries exist."""
    resp = await client.get("/glossaries")
    assert resp.status_code == 200
    assert resp.json()["glossaries"] == []


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_create_glossary(client):
    """POST /glossaries creates a glossary row."""
    resp = await client.post(
        "/glossaries",
        json={"name": "AICore VN→EN", "source_lang": "vi", "target_lang": "en"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "AICore VN→EN"
    assert data["source_lang"] == "vi"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_get_glossary_not_found(client):
    """GET /glossaries/{id} returns 404 for unknown id."""
    resp = await client.get("/glossaries/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_delete_glossary(client, make_glossary):
    """DELETE /glossaries/{id} removes glossary and all terms."""
    g = await make_glossary()
    resp = await client.delete(f"/glossaries/{g.id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossaries route implementation", strict=False)
async def test_list_glossaries_filtered_by_pair(client, make_glossary):
    """GET /glossaries?source_lang=vi&target_lang=en returns only matching-pair glossaries."""
    await make_glossary(source_lang="vi", target_lang="en")
    await make_glossary(source_lang="vi", target_lang="ja")
    resp = await client.get("/glossaries?source_lang=vi&target_lang=en")
    assert resp.status_code == 200
    glossaries = resp.json()["glossaries"]
    assert len(glossaries) == 1
    assert glossaries[0]["target_lang"] == "en"
