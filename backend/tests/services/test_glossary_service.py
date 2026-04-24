"""
Tests for glossary_service.py — CRUD functions.

TDD RED: these tests are written before glossary_service.py is implemented.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models import Glossary, GlossaryTerm
from app.services.glossary_service import (
    create_glossary,
    create_term,
    delete_glossary,
    delete_term,
    get_glossary,
    list_glossaries,
    update_glossary_name,
    update_term,
)


@pytest.mark.asyncio
async def test_create_glossary_returns_glossary(db_session):
    g = await create_glossary(db_session, name="My Glossary", source_lang="vi", target_lang="en")
    assert g.id is not None
    assert g.name == "My Glossary"
    assert g.source_lang == "vi"
    assert g.target_lang == "en"


@pytest.mark.asyncio
async def test_get_glossary_existing(db_session):
    g = await create_glossary(db_session, name="Test", source_lang="vi", target_lang="en")
    fetched = await get_glossary(db_session, g.id)
    assert fetched is not None
    assert fetched.id == g.id


@pytest.mark.asyncio
async def test_get_glossary_not_found_returns_none(db_session):
    result = await get_glossary(db_session, "nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_glossaries_returns_all(db_session):
    await create_glossary(db_session, name="G1", source_lang="vi", target_lang="en")
    await create_glossary(db_session, name="G2", source_lang="en", target_lang="vi")
    results = await list_glossaries(db_session)
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_list_glossaries_filtered_by_source_lang(db_session):
    await create_glossary(db_session, name="VI->EN", source_lang="vi", target_lang="en")
    await create_glossary(db_session, name="JA->EN", source_lang="ja", target_lang="en")
    results = await list_glossaries(db_session, source_lang="vi")
    assert all(g.source_lang == "vi" for g in results)
    assert any(g.name == "VI->EN" for g in results)


@pytest.mark.asyncio
async def test_list_glossaries_filtered_by_both_langs(db_session):
    await create_glossary(db_session, name="Filter", source_lang="vi", target_lang="en")
    await create_glossary(db_session, name="Other", source_lang="vi", target_lang="ja")
    results = await list_glossaries(db_session, source_lang="vi", target_lang="en")
    assert all(g.target_lang == "en" for g in results)


@pytest.mark.asyncio
async def test_update_glossary_name_success(db_session):
    g = await create_glossary(db_session, name="Old", source_lang="vi", target_lang="en")
    updated = await update_glossary_name(db_session, g.id, "New")
    assert updated is not None
    assert updated.name == "New"


@pytest.mark.asyncio
async def test_update_glossary_name_not_found_returns_none(db_session):
    result = await update_glossary_name(db_session, "no-such-id", "Name")
    assert result is None


@pytest.mark.asyncio
async def test_delete_glossary_success(db_session):
    g = await create_glossary(db_session, name="To Delete", source_lang="vi", target_lang="en")
    deleted = await delete_glossary(db_session, g.id)
    assert deleted is True
    assert await get_glossary(db_session, g.id) is None


@pytest.mark.asyncio
async def test_delete_glossary_not_found_returns_false(db_session):
    result = await delete_glossary(db_session, "no-such-id")
    assert result is False


@pytest.mark.asyncio
async def test_create_term_success(db_session):
    g = await create_glossary(db_session, name="T", source_lang="vi", target_lang="en")
    t = await create_term(db_session, g.id, "nguồn", "source", notes="translation")
    assert t.id is not None
    assert t.source_term == "nguồn"
    assert t.target_term == "source"
    assert t.notes == "translation"


@pytest.mark.asyncio
async def test_create_term_duplicate_raises_integrity_error(db_session):
    g = await create_glossary(db_session, name="Dup", source_lang="vi", target_lang="en")
    await create_term(db_session, g.id, "từ", "word")
    with pytest.raises(IntegrityError):
        await create_term(db_session, g.id, "từ", "different")


@pytest.mark.asyncio
async def test_create_term_short_term_raises_value_error(db_session):
    g = await create_glossary(db_session, name="V", source_lang="vi", target_lang="en")
    with pytest.raises(ValueError, match="2 characters"):
        await create_term(db_session, g.id, "a", "word")


@pytest.mark.asyncio
async def test_update_term_success(db_session):
    g = await create_glossary(db_session, name="U", source_lang="vi", target_lang="en")
    t = await create_term(db_session, g.id, "original", "translation")
    updated = await update_term(db_session, t.id, target_term="new_translation")
    assert updated is not None
    assert updated.target_term == "new_translation"
    assert updated.source_term == "original"


@pytest.mark.asyncio
async def test_update_term_not_found_returns_none(db_session):
    result = await update_term(db_session, "no-such-term", target_term="x" * 10)
    assert result is None


@pytest.mark.asyncio
async def test_delete_term_success(db_session):
    g = await create_glossary(db_session, name="D", source_lang="vi", target_lang="en")
    t = await create_term(db_session, g.id, "delete_me", "removed")
    result = await delete_term(db_session, t.id)
    assert result is True


@pytest.mark.asyncio
async def test_delete_term_not_found_returns_false(db_session):
    result = await delete_term(db_session, "no-such-term")
    assert result is False


@pytest.mark.asyncio
async def test_load_glossary_terms_for_job_none_id_returns_none(db_session):
    from app.services.glossary_service import load_glossary_terms_for_job
    result = await load_glossary_terms_for_job(db_session, None)
    assert result is None


@pytest.mark.asyncio
async def test_load_glossary_terms_for_job_returns_dict(db_session):
    from app.services.glossary_service import load_glossary_terms_for_job
    g = await create_glossary(db_session, name="L", source_lang="vi", target_lang="en")
    await create_term(db_session, g.id, "nguồn", "source")
    await create_term(db_session, g.id, "đích", "target")
    terms = await load_glossary_terms_for_job(db_session, g.id)
    assert terms is not None
    assert terms["nguồn"] == "source"
    assert terms["đích"] == "target"


@pytest.mark.asyncio
async def test_load_glossary_terms_for_job_empty_glossary_returns_none(db_session):
    from app.services.glossary_service import load_glossary_terms_for_job
    g = await create_glossary(db_session, name="Empty", source_lang="vi", target_lang="en")
    result = await load_glossary_terms_for_job(db_session, g.id)
    assert result is None
