"""Glossary service CRUD tests — GLOS-01 service layer.

Stubs: will pass after Plan 03 implements glossary_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_create_and_get_glossary(db_session):
    """create_glossary + get_glossary round-trip."""
    from app.services.glossary_service import create_glossary, get_glossary
    g = await create_glossary(db_session, name="Test", source_lang="vi", target_lang="en")
    assert g.id is not None
    fetched = await get_glossary(db_session, g.id)
    assert fetched is not None
    assert fetched.name == "Test"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_delete_glossary(db_session, make_glossary):
    """delete_glossary removes the row."""
    from app.services.glossary_service import get_glossary, delete_glossary
    g = await make_glossary()
    await delete_glossary(db_session, g.id)
    assert await get_glossary(db_session, g.id) is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 glossary_service implementation", strict=False)
async def test_load_glossary_terms_for_job_none(db_session):
    """load_glossary_terms_for_job returns None when glossary_id is None."""
    from app.services.glossary_service import load_glossary_terms_for_job
    result = await load_glossary_terms_for_job(db_session, glossary_id=None)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 update_term implementation", strict=False)
async def test_update_term(db_session, make_glossary, make_glossary_term):
    """update_term patches target_term in place; returns updated GlossaryTerm."""
    from app.services.glossary_service import update_term
    g = await make_glossary()
    t = await make_glossary_term(g.id, source_term="AICore", target_term="AICore")
    updated = await update_term(db_session, t.id, target_term="AICore Inc.")
    assert updated is not None
    assert updated.target_term == "AICore Inc."


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Requires Plan 03 update_term implementation", strict=False)
async def test_update_term_not_found_returns_none(db_session):
    """update_term returns None for unknown term_id (not 404 at service layer)."""
    from app.services.glossary_service import update_term
    result = await update_term(db_session, "nonexistent-id", target_term="anything")
    assert result is None
