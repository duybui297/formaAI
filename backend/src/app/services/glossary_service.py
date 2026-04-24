"""
Glossary service: CRUD + CSV/TBX import + terminology injection helpers.

D-02-01: glossaries + glossary_terms two-table schema.
D-02-02: one glossary per (source_lang, target_lang) pair.
D-02-03: (glossary_id, source_term) unique constraint; hard-delete only (no soft-delete).
D-02-04: CSV primary import path; TBX minimal via stdlib ElementTree.
D-02-06: LLM-swap hook — if qwen-mt-turbo is replaced with a model without native
         terminology support, only the translator.translate_batch call-site changes;
         this service module and DB schema stay portable.
"""
from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FlagSeverity,
    FlagType,
    Glossary,
    GlossaryTerm,
    Segment,
    SegmentFlag,
)

if TYPE_CHECKING:
    pass

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Header variants accepted by CSV parser (D-02-04)
# ---------------------------------------------------------------------------
_HEADER_VARIANTS: dict[str, set[str]] = {
    "source_term": {"source_term", "source", "src", "Source Term", "Source"},
    "target_term": {"target_term", "target", "tgt", "Target Term", "Target"},
    "notes": {"notes", "note", "comment", "Notes", "Comment"},
}

# Phase 1 CORE-05: placeholder token pattern ⟦T{n}⟧
_PLACEHOLDER_RE = re.compile(r"⟦T\d+⟧")


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def create_glossary(
    session: AsyncSession,
    name: str,
    source_lang: str,
    target_lang: str,
) -> Glossary:
    """GLOS-01: Create a new named glossary for a language pair."""
    g = Glossary(name=name, source_lang=source_lang, target_lang=target_lang)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    log.info("glossary_created", glossary_id=g.id, name=name, pair=f"{source_lang}->{target_lang}")
    return g


async def get_glossary(session: AsyncSession, glossary_id: str) -> Glossary | None:
    """GLOS-01: Fetch a glossary by ID. Returns None if not found."""
    result = await session.execute(select(Glossary).where(Glossary.id == glossary_id))
    return result.scalar_one_or_none()


async def list_glossaries(
    session: AsyncSession,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> list[Glossary]:
    """GLOS-05: List all glossaries, optionally filtered by language pair (UPLD-04 picker)."""
    q = select(Glossary).order_by(Glossary.created_at.desc())
    if source_lang is not None:
        q = q.where(Glossary.source_lang == source_lang)
    if target_lang is not None:
        q = q.where(Glossary.target_lang == target_lang)
    result = await session.execute(q)
    return list(result.scalars().all())


async def update_glossary_name(
    session: AsyncSession,
    glossary_id: str,
    name: str,
) -> Glossary | None:
    """GLOS-05: Update the name of a glossary. Returns None if not found."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        return None
    g.name = name
    await session.commit()
    await session.refresh(g)
    return g


async def delete_glossary(session: AsyncSession, glossary_id: str) -> bool:
    """GLOS-05: Delete a glossary and all its terms (CASCADE). Returns False if not found."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        return False
    await session.delete(g)
    await session.commit()
    log.info("glossary_deleted", glossary_id=glossary_id)
    return True


async def create_term(
    session: AsyncSession,
    glossary_id: str,
    source_term: str,
    target_term: str,
    notes: str | None = None,
) -> GlossaryTerm:
    """GLOS-01: Add a term pair to a glossary.

    Raises IntegrityError if (glossary_id, source_term) already exists (D-02-03).
    Raises ValueError if either term is shorter than 2 chars (D-02-07).
    """
    if len(source_term.strip()) < 2 or len(target_term.strip()) < 2:
        raise ValueError("Terms must be at least 2 characters (D-02-07)")
    t = GlossaryTerm(
        glossary_id=glossary_id,
        source_term=source_term.strip(),
        target_term=target_term.strip(),
        notes=notes,
    )
    session.add(t)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(t)
    return t


async def update_term(
    session: AsyncSession,
    term_id: str,
    *,
    source_term: str | None = None,
    target_term: str | None = None,
    notes: str | None = None,
) -> GlossaryTerm | None:
    """GLOS-01: Update source_term, target_term, and/or notes on a glossary term.

    Returns None if term not found.
    Raises ValueError if updated term would be shorter than 2 chars (D-02-07).
    Raises IntegrityError if updated source_term creates a duplicate (D-02-03).
    """
    result = await session.execute(
        select(GlossaryTerm).where(GlossaryTerm.id == term_id)
    )
    t = result.scalar_one_or_none()
    if t is None:
        return None

    if source_term is not None:
        if len(source_term.strip()) < 2:
            raise ValueError("source_term must be at least 2 characters (D-02-07)")
        t.source_term = source_term.strip()
    if target_term is not None:
        if len(target_term.strip()) < 2:
            raise ValueError("target_term must be at least 2 characters (D-02-07)")
        t.target_term = target_term.strip()
    if notes is not None:
        t.notes = notes

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    await session.refresh(t)
    return t


async def delete_term(session: AsyncSession, term_id: str) -> bool:
    """GLOS-01: Delete a term by ID. Returns False if not found."""
    result = await session.execute(
        select(GlossaryTerm).where(GlossaryTerm.id == term_id)
    )
    t = result.scalar_one_or_none()
    if t is None:
        return False
    await session.delete(t)
    await session.commit()
    return True


# ---------------------------------------------------------------------------
# CSV / TBX import
# ---------------------------------------------------------------------------


def parse_csv_glossary(
    file_content: bytes, encoding: str = "utf-8-sig"
) -> list[dict]:
    """GLOS-02: Parse CSV glossary file. Accepts header variants.

    utf-8-sig strips BOM from Excel-exported CSV (Pitfall 6).
    Returns list of {"source_term": str, "target_term": str, "notes": str | None}
    Raises ValueError with row number on parse or validation error.
    """
    text = file_content.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")

    # Build canonical field map from header variants
    field_map: dict[str, str] = {}
    for field in reader.fieldnames:
        if field is None:
            continue
        for canonical, variants in _HEADER_VARIANTS.items():
            if field.strip() in variants:
                field_map[field] = canonical
                break

    has_source = "source_term" in field_map.values()
    has_target = "target_term" in field_map.values()
    if not has_source or not has_target:
        raise ValueError(
            "CSV must have 'source_term' (or 'source') and 'target_term' (or 'target') columns"
        )

    # Reverse map: canonical → original field name
    canonical_to_field = {v: k for k, v in field_map.items()}

    terms: list[dict] = []
    for row_num, row in enumerate(reader, start=2):  # row 1 = header
        src = (row.get(canonical_to_field.get("source_term", ""), "") or "").strip()
        tgt = (row.get(canonical_to_field.get("target_term", ""), "") or "").strip()
        notes_key = canonical_to_field.get("notes", "")
        notes_raw = (row.get(notes_key, "") or "").strip() if notes_key else ""
        notes = notes_raw or None

        if not src or not tgt:
            raise ValueError(f"Row {row_num}: source_term and target_term are required")
        if len(src) < 2 or len(tgt) < 2:
            raise ValueError(
                f"Row {row_num}: terms must be at least 2 characters (D-02-07)"
            )
        terms.append({"source_term": src, "target_term": tgt, "notes": notes})

    return terms


def parse_tbx_minimal(
    file_content: bytes,
    source_lang: str,
    target_lang: str,
) -> list[dict]:
    """GLOS-02: Minimal TBX-Core / TBX-Basic extraction.

    Extracts (source_lang term, target_lang term) pairs from termEntry elements.
    Supports TBX-Core (tig/term) and TBX-Basic (ntig/termGrp/term) formats.
    Returns same shape as parse_csv_glossary for uniform downstream handling.

    ElementTree does not expand external entities by default — safe for untrusted XML.
    """
    try:
        root = ET.fromstring(file_content)
    except ET.ParseError as e:
        raise ValueError(f"Malformed TBX XML: {e}") from e

    terms: list[dict] = []
    src_lang_lc = source_lang.lower()
    tgt_lang_lc = target_lang.lower()

    for entry in root.iter("termEntry"):
        lang_terms: dict[str, str] = {}
        for lang_set in entry.iter("langSet"):
            lang = lang_set.get("{http://www.w3.org/XML/1998/namespace}lang", "").lower()
            # TBX-Core: tig/term
            for tig in lang_set.iter("tig"):
                term_el = tig.find("term")
                if term_el is not None and term_el.text:
                    lang_terms[lang] = term_el.text.strip()
            # TBX-Basic: ntig/termGrp/term
            for ntig in lang_set.iter("ntig"):
                term_grp = ntig.find("termGrp")
                if term_grp is not None:
                    term_el = term_grp.find("term")
                    if term_el is not None and term_el.text:
                        lang_terms[lang] = term_el.text.strip()

        src = lang_terms.get(src_lang_lc)
        tgt = lang_terms.get(tgt_lang_lc)
        if src and tgt and len(src) >= 2 and len(tgt) >= 2:
            terms.append({"source_term": src, "target_term": tgt, "notes": None})

    return terms


async def import_csv_terms(
    session: AsyncSession,
    glossary: Glossary,
    file_content: bytes,
    ext: str,
) -> dict:
    """GLOS-02: Bulk import terms from CSV or TBX file.

    Returns {"imported": N, "skipped_duplicates": M}.
    ext should be ".csv" or ".tbx".

    Duplicate detection: pre-fetches existing source_terms for this glossary,
    then skips any row whose source_term already exists. This avoids per-row
    rollback which corrupts the session state on SQLite (aiosqlite) and is
    also more efficient than per-row flush+rollback on PostgreSQL.
    """
    if ext == ".tbx":
        rows = parse_tbx_minimal(
            file_content, glossary.source_lang, glossary.target_lang
        )
    else:
        rows = parse_csv_glossary(file_content)

    # Pre-fetch existing source_terms for this glossary to detect duplicates
    result = await session.execute(
        select(GlossaryTerm.source_term).where(
            GlossaryTerm.glossary_id == glossary.id
        )
    )
    existing: set[str] = {row[0] for row in result.all()}

    imported = 0
    skipped = 0
    for row in rows:
        src = row["source_term"]
        if src in existing:
            skipped += 1
            continue
        t = GlossaryTerm(
            glossary_id=glossary.id,
            source_term=src,
            target_term=row["target_term"],
            notes=row.get("notes"),
        )
        session.add(t)
        existing.add(src)  # track in-batch duplicates
        imported += 1

    await session.commit()
    log.info(
        "glossary_import_complete",
        glossary_id=glossary.id,
        imported=imported,
        skipped_duplicates=skipped,
    )
    return {"imported": imported, "skipped_duplicates": skipped}


# ---------------------------------------------------------------------------
# Worker helpers
# ---------------------------------------------------------------------------


async def load_glossary_terms_for_job(
    session: AsyncSession, glossary_id: str | None
) -> dict[str, str] | None:
    """GLOS-03: Load {source_term: target_term} dict for the job's glossary.

    Called by the worker before the translate loop.
    Returns None if no glossary is attached to the job.
    Returns None (not empty dict) if glossary has zero terms — caller treats None as "no glossary".
    """
    if glossary_id is None:
        return None
    result = await session.execute(
        select(GlossaryTerm.source_term, GlossaryTerm.target_term).where(
            GlossaryTerm.glossary_id == glossary_id
        )
    )
    rows = result.all()
    if not rows:
        return None
    return {row.source_term: row.target_term for row in rows}


async def run_post_check(
    session: AsyncSession,
    batch_segs: list,
    translated_map: dict[str, str],
    glossary: dict[str, str] | None,
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> None:
    """GLOS-04 + LAYOUT-01: Post-translation checks per batch.

    For each translated segment, runs 4 detectors in order:
    1. overflow: expansion_ratio > lang-pair threshold → FlagType.overflow (warn)
    2. glossary_violation: target term absent from translation (case-insensitive, min 2 chars per D-02-07) → FlagType.glossary_violation (warn)
    3. placeholder_mismatch: ⟦T{n}⟧ token in source absent from translation (Phase 1 CORE-05) → FlagType.placeholder_mismatch (warn)
    4. llm_refusal: ONLY when len(source_stripped) > 8 AND translated_stripped == source_stripped → FlagType.llm_refusal (warn)
       Short tokens like "AI", "OK", "v2" are excluded to avoid false positives on acronyms/proper nouns.

    All flags use FlagSeverity.warn per D-02-09.
    Writes expansion_ratio to segments table.
    Writes all flags in a single add_all + flush per batch.
    """
    lang_pair = f"{source_lang.lower()}->{target_lang.lower()}"
    expansion_threshold = expansion_thresholds.get(lang_pair, 1.5)  # default 1.5

    flags_to_insert: list[SegmentFlag] = []

    for seg in batch_segs:
        translated = translated_map.get(seg.id)
        if translated is None:
            continue

        source = seg.source_text

        # --- 1. overflow: expansion ratio ---
        if len(source) > 0:
            ratio = len(translated) / len(source)
            await session.execute(
                update(Segment).where(Segment.id == seg.id).values(expansion_ratio=ratio)
            )
            if ratio > expansion_threshold:
                flags_to_insert.append(
                    SegmentFlag(
                        segment_id=seg.id,
                        flag_type=FlagType.overflow,
                        severity=FlagSeverity.warn,
                        details={"ratio": round(ratio, 3), "threshold": expansion_threshold},
                    )
                )

        # --- 2. glossary_violation: case-insensitive target term check ---
        if glossary:
            translated_lower = translated.lower()
            for src_term, tgt_term in glossary.items():
                # D-02-07: skip sub-2-char terms to avoid spurious substring matches
                if len(tgt_term) < 2:
                    continue
                # Only check violation if source term appears in source text
                if src_term.lower() not in source.lower():
                    continue
                if tgt_term.lower() not in translated_lower:
                    flags_to_insert.append(
                        SegmentFlag(
                            segment_id=seg.id,
                            flag_type=FlagType.glossary_violation,
                            severity=FlagSeverity.warn,
                            details={"term": src_term, "expected": tgt_term},
                        )
                    )

        # --- 3. placeholder_mismatch: ⟦T{n}⟧ tokens from Phase 1 CORE-05 ---
        source_tokens = set(_PLACEHOLDER_RE.findall(source))
        if source_tokens:
            translated_tokens = set(_PLACEHOLDER_RE.findall(translated))
            missing_tokens = source_tokens - translated_tokens
            if missing_tokens:
                flags_to_insert.append(
                    SegmentFlag(
                        segment_id=seg.id,
                        flag_type=FlagType.placeholder_mismatch,
                        severity=FlagSeverity.warn,
                        details={"missing_tokens": sorted(missing_tokens)},
                    )
                )

        # --- 4. llm_refusal: output identical to input (only for non-trivial sources) ---
        # Only flag when source is substantive (>8 chars) to avoid false positives on
        # short acronyms ("AI", "OK"), version strings ("v2"), proper nouns that are
        # intentionally unchanged.
        translated_stripped = translated.strip()
        source_stripped = source.strip()
        if len(source_stripped) > 8 and translated_stripped == source_stripped:
            flags_to_insert.append(
                SegmentFlag(
                    segment_id=seg.id,
                    flag_type=FlagType.llm_refusal,
                    severity=FlagSeverity.warn,
                    details={
                        "translated_len": len(translated_stripped),
                        "source_len": len(source_stripped),
                    },
                )
            )

    if flags_to_insert:
        session.add_all(flags_to_insert)
        await session.flush()
