"""
Glossary CRUD routes — GLOS-01, GLOS-02, GLOS-05.

All routes are prefixed with /api/v1/glossaries (applied at app level).

GET    /api/v1/glossaries                              — list all (filterable by lang pair)
POST   /api/v1/glossaries                              — create glossary
GET    /api/v1/glossaries/{id}                         — get glossary + term list
PATCH  /api/v1/glossaries/{id}                         — rename glossary
DELETE /api/v1/glossaries/{id}                         — delete glossary (cascades to terms)
GET    /api/v1/glossaries/{id}/terms                   — list terms
POST   /api/v1/glossaries/{id}/terms                   — add term
PATCH  /api/v1/glossaries/{id}/terms/{term_id}         — update term (source_term, target_term, notes)
DELETE /api/v1/glossaries/{id}/terms/{term_id}         — delete term
POST   /api/v1/glossaries/{id}/terms/import            — bulk import CSV or TBX
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.db.models import Glossary, GlossaryTerm, User
from app.db.session import get_session
from app.schemas.glossary import (
    CreateGlossaryRequest,
    CreateTermRequest,
    RenameGlossaryRequest,
    UpdateTermRequest,
)
from app.services.glossary_service import (
    create_glossary,
    create_term,
    delete_glossary,
    delete_term,
    get_glossary,
    get_glossary_for_user,
    import_csv_terms,
    list_glossaries,
    update_glossary_name,
    update_term,
)

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _glossary_to_dict(g: Glossary, include_terms: bool = False) -> dict:
    d: dict = {
        "id": g.id,
        "name": g.name,
        "source_lang": g.source_lang,
        "target_lang": g.target_lang,
        "term_count": len(g.terms) if g.terms is not None else 0,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }
    if include_terms:
        d["terms"] = [_term_to_dict(t) for t in (g.terms or [])]
    return d


def _term_to_dict(t: GlossaryTerm) -> dict:
    return {
        "id": t.id,
        "glossary_id": t.glossary_id,
        "source_term": t.source_term,
        "target_term": t.target_term,
        "notes": t.notes,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


# ---------------------------------------------------------------------------
# Glossary endpoints
# ---------------------------------------------------------------------------


@router.get("/glossaries")
async def list_glossaries_endpoint(
    source_lang: str | None = None,
    target_lang: str | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01/05: List glossaries for the current user. Optional source_lang + target_lang filter for UPLD-04 picker.

    Auth: requires valid JWT (get_current_active_user).
    """
    glossaries = await list_glossaries(session, source_lang=source_lang, target_lang=target_lang, user_id=current_user.id)
    return {"glossaries": [_glossary_to_dict(g) for g in glossaries]}


@router.post("/glossaries", status_code=201)
async def create_glossary_endpoint(
    body: CreateGlossaryRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01: Create a new named glossary for a language pair.

    Auth: requires valid JWT (get_current_active_user).
    """
    g = await create_glossary(
        session,
        name=body.name,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        user_id=current_user.id,
    )
    return _glossary_to_dict(g)


@router.get("/glossaries/{glossary_id}")
async def get_glossary_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01/05: Get a glossary with its term list.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return _glossary_to_dict(g, include_terms=True)


@router.patch("/glossaries/{glossary_id}")
async def rename_glossary_endpoint(
    glossary_id: str,
    body: RenameGlossaryRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-05: Rename a glossary.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    g.name = body.name
    await session.commit()
    await session.refresh(g)
    return _glossary_to_dict(g)


@router.delete("/glossaries/{glossary_id}", status_code=204)
async def delete_glossary_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """GLOS-05: Delete glossary and all its terms (CASCADE).

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    await session.delete(g)
    await session.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Term endpoints
# Note: import route declared BEFORE /{term_id} routes so FastAPI does not
# match the literal "import" as a term_id path parameter.
# ---------------------------------------------------------------------------


@router.get("/glossaries/{glossary_id}/terms")
async def list_terms_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01: List terms for a glossary.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return {"terms": [_term_to_dict(t) for t in (g.terms or [])]}


@router.post("/glossaries/{glossary_id}/terms", status_code=201)
async def add_term_endpoint(
    glossary_id: str,
    body: CreateTermRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01: Add a term pair to a glossary.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    try:
        t = await create_term(
            session,
            glossary_id=glossary_id,
            source_term=body.source_term,
            target_term=body.target_term,
            notes=body.notes,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail=f"Term '{body.source_term}' already exists in this glossary",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _term_to_dict(t)


@router.post("/glossaries/{glossary_id}/terms/import")
async def import_terms_endpoint(
    glossary_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-02: Bulk import terms from CSV or TBX file.

    Returns {imported: N, skipped_duplicates: M}.
    Raises 422 on parse error (CSV malformed, TBX invalid XML).
    Raises 413 if file exceeds 25 MB.

    IMPORTANT: Declared before /{term_id} routes so FastAPI does not match
    the literal "import" segment as a term_id path parameter.

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")

    content = await file.read()
    # Enforce upload size (same 25MB cap as main upload endpoint — T-02-03-01)
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 25 MB limit")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".csv", ".tbx"}:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{ext}'. Use .csv or .tbx",
        )

    try:
        result = await import_csv_terms(session, g, content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return result


@router.patch("/glossaries/{glossary_id}/terms/{term_id}", status_code=200)
async def update_term_endpoint(
    glossary_id: str,
    term_id: str,
    body: UpdateTermRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """GLOS-01: Update source_term, target_term, or notes on an existing term.

    glossary_id is validated (404 if glossary not found).
    Returns updated term dict.
    409 if updated source_term creates a duplicate (D-02-03).

    Auth: requires valid JWT (get_current_active_user).
    Ownership: glossary must belong to current_user.
    """
    g = await get_glossary_for_user(session, glossary_id, current_user.id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    try:
        t = await update_term(
            session,
            term_id,
            source_term=body.source_term,
            target_term=body.target_term,
            notes=body.notes,
        )
    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="A term with that source_term already exists in this glossary",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if t is None:
        raise HTTPException(status_code=404, detail="Term not found")
    return _term_to_dict(t)


@router.delete("/glossaries/{glossary_id}/terms/{term_id}", status_code=204)
async def delete_term_endpoint(
    glossary_id: str,
    term_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """GLOS-01/05: Delete a term. No confirmation dialog (terms are cheap to re-add)."""
    deleted = await delete_term(session, term_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Term not found")
    return Response(status_code=204)
