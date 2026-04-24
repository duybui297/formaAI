"""
Tests for the full glossary REST surface — GET/POST/PATCH/DELETE glossary + terms.

TDD RED: written before full glossaries.py implementation.
Uses app_and_tmp fixture from tests/api/conftest.py.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_glossaries_empty(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/glossaries")
    assert resp.status_code == 200
    body = resp.json()
    assert "glossaries" in body
    assert isinstance(body["glossaries"], list)


@pytest.mark.asyncio
async def test_create_glossary_201(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/glossaries",
            json={"name": "My Glossary", "source_lang": "vi", "target_lang": "en"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] is not None
    assert body["name"] == "My Glossary"
    assert body["source_lang"] == "vi"
    assert body["target_lang"] == "en"


@pytest.mark.asyncio
async def test_get_glossary_returns_detail(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Detail", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.get(f"/glossaries/{glossary_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == glossary_id
    assert "terms" in body


@pytest.mark.asyncio
async def test_get_glossary_404(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/glossaries/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_glossary_rename(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Old Name", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/glossaries/{glossary_id}",
            json={"name": "New Name"},
        )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_glossary_204(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Delete Me", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.delete(f"/glossaries/{glossary_id}")
        assert resp.status_code == 204
        get_resp = await client.get(f"/glossaries/{glossary_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_glossary_404(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete("/glossaries/no-such-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_glossaries_filtered_by_lang(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/glossaries",
            json={"name": "VI->EN", "source_lang": "vi", "target_lang": "en"},
        )
        await client.post(
            "/glossaries",
            json={"name": "JA->EN", "source_lang": "ja", "target_lang": "en"},
        )
        resp = await client.get("/glossaries?source_lang=vi&target_lang=en")
    assert resp.status_code == 200
    glossaries = resp.json()["glossaries"]
    assert all(g["source_lang"] == "vi" for g in glossaries)


@pytest.mark.asyncio
async def test_add_term_201(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Terms", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "source", "notes": "note"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["source_term"] == "nguon"
    assert body["target_term"] == "source"
    assert body["notes"] == "note"


@pytest.mark.asyncio
async def test_add_term_409_on_duplicate(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Dup", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "source"},
        )
        resp = await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "other"},
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_terms_for_glossary(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "List", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "source"},
        )
        resp = await client.get(f"/glossaries/{glossary_id}/terms")
    assert resp.status_code == 200
    body = resp.json()
    assert "terms" in body
    assert len(body["terms"]) == 1


@pytest.mark.asyncio
async def test_patch_term_updates_fields(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Patch", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        term_resp = await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "source"},
        )
        term_id = term_resp.json()["id"]
        resp = await client.patch(
            f"/glossaries/{glossary_id}/terms/{term_id}",
            json={"target_term": "updated_source"},
        )
    assert resp.status_code == 200
    assert resp.json()["target_term"] == "updated_source"


@pytest.mark.asyncio
async def test_patch_term_404_unknown_term(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "P404", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.patch(
            f"/glossaries/{glossary_id}/terms/no-such-term",
            json={"target_term": "updated"},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_term_204(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "DelTerm", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        term_resp = await client.post(
            f"/glossaries/{glossary_id}/terms",
            json={"source_term": "nguon", "target_term": "source"},
        )
        term_id = term_resp.json()["id"]
        resp = await client.delete(f"/glossaries/{glossary_id}/terms/{term_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_import_terms_csv(app_and_tmp, tmp_path):
    app, _ = app_and_tmp
    csv_content = b"source_term,target_term\nnguon,source\ndich,target\n"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "Import", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.post(
            f"/glossaries/{glossary_id}/terms/import",
            files={"file": ("glossary.csv", csv_content, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported"] == 2
    assert body["skipped_duplicates"] == 0


@pytest.mark.asyncio
async def test_import_terms_unsupported_format(app_and_tmp):
    app, _ = app_and_tmp
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/glossaries",
            json={"name": "BadFmt", "source_lang": "vi", "target_lang": "en"},
        )
        glossary_id = create_resp.json()["id"]
        resp = await client.post(
            f"/glossaries/{glossary_id}/terms/import",
            files={"file": ("glossary.xlsx", b"garbage", "application/vnd.ms-excel")},
        )
    assert resp.status_code == 422
