---
phase: 02-review-ux-glossary
plan: "03"
type: execute
wave: 1
depends_on: ["02-02"]
files_modified:
  - backend/src/app/services/glossary_service.py
  - backend/src/app/api/routes/glossaries.py
  - backend/src/app/api/routes/upload.py
  - backend/src/app/services/job_service.py
  - backend/src/app/api/__init__.py
autonomous: true
requirements:
  - GLOS-01
  - GLOS-02
  - GLOS-03
  - GLOS-04
  - GLOS-05

must_haves:
  truths:
    - "GET /glossaries returns glossary list, optionally filtered by source_lang + target_lang query params"
    - "POST /glossaries creates a new glossary row with name, source_lang, target_lang"
    - "GET /glossaries/{id}/terms returns all terms for the glossary"
    - "POST /glossaries/{id}/terms creates a new term (source_term, target_term, notes)"
    - "POST /glossaries/{id}/terms/import accepts CSV and TBX files and bulk-inserts terms"
    - "DELETE /glossaries/{id} removes glossary and cascades to terms"
    - "POST /upload accepts optional glossary_id Form field; 422 if pair mismatches"
    - "jobs.glossary_id persisted to DB when provided"
    - "CSV import respects header variants and utf-8-sig BOM stripping"
    - "TBX minimal parser extracts term pairs from TBX-Core and TBX-Basic files"
    - "run_post_check writes all 4 flag types: overflow, glossary_violation, placeholder_mismatch, llm_refusal"
  artifacts:
    - path: "backend/src/app/services/glossary_service.py"
      provides: "Glossary CRUD + CSV/TBX parsers + load_glossary_terms_for_job + run_post_check"
      exports: ["create_glossary", "get_glossary", "list_glossaries", "update_glossary_name", "delete_glossary", "create_term", "delete_term", "import_csv_terms", "parse_csv_glossary", "parse_tbx_minimal", "load_glossary_terms_for_job", "run_post_check"]
    - path: "backend/src/app/api/routes/glossaries.py"
      provides: "Full glossary REST surface (replaces Phase 1 stub)"
      exports: ["router"]
    - path: "backend/src/app/api/routes/upload.py"
      provides: "upload endpoint extended with glossary_id Form field"
  key_links:
    - from: "backend/src/app/api/routes/upload.py"
      to: "backend/src/app/services/glossary_service.py get_glossary"
      via: "glossary_id validation in upload handler"
      pattern: "await get_glossary"
    - from: "backend/src/app/services/glossary_service.py load_glossary_terms_for_job"
      to: "backend/src/app/workers/translate_worker.py"
      via: "called by worker in Plan 04"
      pattern: "load_glossary_terms_for_job"
    - from: "backend/src/app/services/glossary_service.py run_post_check"
      to: "backend/src/app/workers/translate_worker.py"
      via: "imported and called per batch in Plan 04"
      pattern: "run_post_check"
---

<objective>
Implement the full glossary backend: glossary_service.py (CRUD helpers + CSV/TBX parsers + glossary term loader + run_post_check with all 4 flag detectors), glossaries.py route (replaces Phase 1 stub), upload.py extension (glossary_id Form field + pair validation), job_service.py extension (persist glossary_id on job creation).

Purpose: This plan delivers GLOS-01, GLOS-02, GLOS-03 (prep — worker wired in Plan 04), GLOS-04 (run_post_check implementation), GLOS-05. All glossary CRUD endpoints are live after this plan. Plan 04 Task 3 imports run_post_check from this module — no file conflict.
Output: Full REST surface for glossary management plus post-check logic. Frontend glossary pages (Plan 05) and worker glossary injection (Plan 04) depend on these endpoints and service functions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-RESEARCH.md
@.planning/phases/02-review-ux-glossary/02-PATTERNS.md

<interfaces>
<!-- From backend/src/app/db/models.py (after Plan 02) -->
```python
class Glossary(Base):
    id: Mapped[str]            # String(36), uuid default
    name: Mapped[str]          # String(255)
    source_lang: Mapped[str]   # String(64)
    target_lang: Mapped[str]   # String(64)
    created_at / updated_at
    terms: Mapped[list[GlossaryTerm]]   # relationship selectin

class GlossaryTerm(Base):
    id: Mapped[str]            # String(36)
    glossary_id: Mapped[str]   # FK glossaries.id CASCADE
    source_term: Mapped[str]   # Text
    target_term: Mapped[str]   # Text
    notes: Mapped[str | None]  # Text nullable
    created_at
    UniqueConstraint(glossary_id, source_term)

class SegmentFlag(Base):
    id: Mapped[str]
    segment_id: Mapped[str]    # FK segments.id
    flag_type: Mapped[FlagType]     # overflow / glossary_violation / placeholder_mismatch / llm_refusal
    severity: Mapped[FlagSeverity]  # info / warn / block
    details: Mapped[dict | None]    # JSON

class Segment(Base):
    id: Mapped[str]
    source_text: Mapped[str]
    translated_text: Mapped[str | None]
    expansion_ratio: Mapped[float | None]   # NEW Phase 2
```

<!-- From backend/src/app/api/routes/upload.py (existing, extend) -->
```python
# Current signature (partial):
async def upload_document(
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    tracked_changes_action: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    ...
) -> dict:
    ...
    # job = await create_job(session, ...) without glossary_id
```

<!-- From backend/src/app/services/job_service.py -->
```python
async def create_job(
    session: AsyncSession,
    *,
    input_format: str,
    input_path: str,
    original_filename: str,
    source_lang: str,
    target_lang: str,
    has_tracked_changes: bool,
    tracked_changes_action: TrackedChangesAction | None,
    segments_total: int = 0,
) -> Job:
    ...
    # Phase 2: add glossary_id: str | None = None parameter
```

<!-- RESEARCH.md Section 4 — CSV/TBX parse functions -->
# parse_csv_glossary(file_content: bytes, encoding: str = "utf-8-sig") -> list[dict]
# parse_tbx_minimal(file_content: bytes, source_lang: str, target_lang: str) -> list[dict]
# Both return list of {"source_term": str, "target_term": str, "notes": str | None}

<!-- Phase 1 CORE-05: placeholder token format -->
# Placeholder tokens use pattern: ⟦T{n}⟧ (e.g., ⟦T1⟧, ⟦T2⟧)
# run_post_check must detect when source contains ⟦T{n}⟧ but translated_text does not
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement glossary_service.py — CRUD + CSV/TBX parsers + term loader + run_post_check</name>
  <files>
    backend/src/app/services/glossary_service.py
  </files>
  <read_first>
    - backend/src/app/services/job_service.py (full file — module header, CRUD function pattern, docstring style)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Section 4 (CSV parser with BOM, header variants), §Section 5 (load_glossary_terms_for_job, run_post_check pattern)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §glossary_service.py (CRUD pattern + deviation notes)
    - backend/src/app/db/models.py (Glossary, GlossaryTerm, SegmentFlag, Segment models and FlagType/FlagSeverity enums)
  </read_first>
  <behavior>
    - create_glossary(session, name, source_lang, target_lang) → Glossary
    - get_glossary(session, glossary_id) → Glossary | None
    - list_glossaries(session, source_lang=None, target_lang=None) → list[Glossary]
    - update_glossary_name(session, glossary_id, name) → Glossary | None
    - delete_glossary(session, glossary_id) → bool (True if deleted, False if not found)
    - create_term(session, glossary_id, source_term, target_term, notes) → GlossaryTerm; raises IntegrityError on duplicate source_term
    - delete_term(session, term_id) → bool
    - import_csv_terms(session, glossary, content, ext) → {"imported": N, "skipped_duplicates": M}
    - parse_csv_glossary(content: bytes, encoding="utf-8-sig") → list[dict]; raises ValueError on missing headers or short terms
    - parse_tbx_minimal(content: bytes, source_lang: str, target_lang: str) → list[dict]
    - load_glossary_terms_for_job(session, glossary_id: str | None) → dict[str, str] | None
    - run_post_check: overflow flag if expansion_ratio > threshold (lang-pair keyed)
    - run_post_check: glossary_violation flag if target term absent from translation (case-insensitive, min 2 chars per D-02-07)
    - run_post_check: placeholder_mismatch flag if ⟦T{n}⟧ token present in source but absent from translation (Phase 1 CORE-05)
    - run_post_check: llm_refusal flag if translated.strip() == source.strip() OR len(translated.strip()) < 3
  </behavior>
  <action>
Create `backend/src/app/services/glossary_service.py`:

```python
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
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Glossary, GlossaryTerm, Segment, SegmentFlag, FlagType, FlagSeverity

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
    """
    if ext == ".tbx":
        rows = parse_tbx_minimal(
            file_content, glossary.source_lang, glossary.target_lang
        )
    else:
        rows = parse_csv_glossary(file_content)

    imported = 0
    skipped = 0
    for row in rows:
        t = GlossaryTerm(
            glossary_id=glossary.id,
            source_term=row["source_term"],
            target_term=row["target_term"],
            notes=row.get("notes"),
        )
        session.add(t)
        try:
            await session.flush()
            imported += 1
        except IntegrityError:
            await session.rollback()
            skipped += 1

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
        select(GlossaryTerm.source_term, GlossaryTerm.target_term)
        .where(GlossaryTerm.glossary_id == glossary_id)
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
    3. placeholder_mismatch: ⟦T{n}⟧ token in source absent from translation (Phase 1 CORE-05) → FlagType.placeholder_mismatch (block)
    4. llm_refusal: translated.strip() == source.strip() OR len(translated.strip()) < 3 → FlagType.llm_refusal (block)

    Writes expansion_ratio to segments table.
    Writes all flags in a single add_all + flush per batch.
    """
    lang_pair = f"{source_lang.lower()}->{target_lang.lower()}"
    expansion_threshold = expansion_thresholds.get(lang_pair, 1.5)  # default 1.5 per RESEARCH

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
                        severity=FlagSeverity.block,
                        details={"missing_tokens": sorted(missing_tokens)},
                    )
                )

        # --- 4. llm_refusal: output identical to input OR too short ---
        translated_stripped = translated.strip()
        source_stripped = source.strip()
        if translated_stripped == source_stripped or len(translated_stripped) < 3:
            flags_to_insert.append(
                SegmentFlag(
                    segment_id=seg.id,
                    flag_type=FlagType.llm_refusal,
                    severity=FlagSeverity.block,
                    details={"translated_len": len(translated_stripped), "source_len": len(source_stripped)},
                )
            )

    if flags_to_insert:
        session.add_all(flags_to_insert)
        await session.flush()
```

Note on import_csv_terms: The per-row rollback approach uses flush+rollback per row for SQLite test compat. For PostgreSQL production, consider replacing with:

```python
from sqlalchemy.dialects.postgresql import insert as pg_insert
stmt = pg_insert(GlossaryTerm).values(rows_dicts).on_conflict_do_nothing(
    index_elements=["glossary_id", "source_term"]
)
result = await session.execute(stmt)
imported = result.rowcount
skipped = len(rows) - imported
```
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/services/test_glossary_service.py backend/tests/services/test_csv_import.py backend/tests/services/test_tbx_import.py backend/tests/services/test_post_check.py -x -q 2>&1 | tail -15</automated>
  </verify>
  <done>
    - glossary_service.py exists and all functions import cleanly
    - All 12 functions exported including run_post_check
    - test_glossary_service.py, test_csv_import.py, test_tbx_import.py xfail tests pass
    - test_post_check.py: all 5 stubs pass (overflow, glossary_violation, placeholder_mismatch, llm_refusal, short term skip)
    - CSV: standard headers, BOM stripping, alias headers all parse correctly
    - TBX: TBX-Core format parses correctly; wrong-language pair returns []
    - load_glossary_terms_for_job returns None for None glossary_id
    - run_post_check writes glossary_violation only when source_term appears in source text
    - run_post_check placeholder_mismatch: ⟦T1⟧ in source but not translated → flag written
    - run_post_check llm_refusal: translated identical to source → flag written
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Replace glossaries.py stub with full CRUD route</name>
  <files>
    backend/src/app/api/routes/glossaries.py
  </files>
  <read_first>
    - backend/src/app/api/routes/glossaries.py (current stub — full replace)
    - backend/src/app/api/routes/jobs.py (full file — import pattern, serializer helper, Depends pattern)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §glossaries.py (endpoint patterns + serializer)
    - .planning/phases/02-review-ux-glossary/02-RESEARCH.md §Code Examples (list_glossaries endpoint)
    - .planning/phases/02-review-ux-glossary/02-UI-SPEC.md §Copywriting Contract (error messages)
  </read_first>
  <behavior>
    - GET /glossaries → {"glossaries": [...]} (optionally filtered by source_lang + target_lang)
    - POST /glossaries → create (201)
    - GET /glossaries/{id} → get or 404
    - PATCH /glossaries/{id} → rename only (name field)
    - DELETE /glossaries/{id} → delete or 404 (204)
    - GET /glossaries/{id}/terms → list terms for glossary
    - POST /glossaries/{id}/terms → add term (201); 409 on duplicate source_term
    - DELETE /glossaries/{id}/terms/{term_id} → delete term (204)
    - POST /glossaries/{id}/terms/import → CSV/TBX import (200 with {imported, skipped_duplicates})
    - List response shape: {"glossaries": [GlossaryDict, ...]} — wrapped, matching Phase 1 /jobs pattern
  </behavior>
  <action>
Replace the entire content of `backend/src/app/api/routes/glossaries.py`:

```python
"""
Glossary CRUD routes — GLOS-01, GLOS-02, GLOS-05.

GET    /glossaries                         — list all (filterable by lang pair)
POST   /glossaries                         — create glossary
GET    /glossaries/{id}                    — get glossary + term list
PATCH  /glossaries/{id}                    — rename glossary
DELETE /glossaries/{id}                    — delete glossary (cascades to terms)
GET    /glossaries/{id}/terms              — list terms
POST   /glossaries/{id}/terms              — add term
DELETE /glossaries/{id}/terms/{term_id}    — delete term
POST   /glossaries/{id}/terms/import       — bulk import CSV or TBX
"""
from __future__ import annotations

from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Glossary, GlossaryTerm
from app.db.session import get_session
from app.services.glossary_service import (
    create_glossary,
    create_term,
    delete_glossary,
    delete_term,
    get_glossary,
    import_csv_terms,
    list_glossaries,
    update_glossary_name,
)

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class CreateGlossaryRequest(BaseModel, frozen=True):
    name: str = Field(..., min_length=1, max_length=255)
    source_lang: str = Field(..., min_length=2, max_length=64)
    target_lang: str = Field(..., min_length=2, max_length=64)


class RenameGlossaryRequest(BaseModel, frozen=True):
    name: str = Field(..., min_length=1, max_length=255)


class CreateTermRequest(BaseModel, frozen=True):
    source_term: str = Field(..., min_length=2, max_length=500)
    target_term: str = Field(..., min_length=2, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


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
) -> dict:
    """GLOS-01/05: List glossaries. Optional source_lang + target_lang filter for UPLD-04 picker.

    Response: {"glossaries": [...]} — wrapped, matching Phase 1 /jobs pattern.
    """
    glossaries = await list_glossaries(session, source_lang=source_lang, target_lang=target_lang)
    return {"glossaries": [_glossary_to_dict(g) for g in glossaries]}


@router.post("/glossaries", status_code=201)
async def create_glossary_endpoint(
    body: CreateGlossaryRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-01: Create a new named glossary for a language pair."""
    g = await create_glossary(
        session,
        name=body.name,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
    )
    return _glossary_to_dict(g)


@router.get("/glossaries/{glossary_id}")
async def get_glossary_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-01/05: Get a glossary with its term list."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return _glossary_to_dict(g, include_terms=True)


@router.patch("/glossaries/{glossary_id}")
async def rename_glossary_endpoint(
    glossary_id: str,
    body: RenameGlossaryRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-05: Rename a glossary."""
    g = await update_glossary_name(session, glossary_id, body.name)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return _glossary_to_dict(g)


@router.delete("/glossaries/{glossary_id}", status_code=204)
async def delete_glossary_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """GLOS-05: Delete glossary and all its terms (CASCADE)."""
    deleted = await delete_glossary(session, glossary_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Glossary not found")


# ---------------------------------------------------------------------------
# Term endpoints
# ---------------------------------------------------------------------------

@router.get("/glossaries/{glossary_id}/terms")
async def list_terms_endpoint(
    glossary_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-01: List terms for a glossary."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")
    return {"terms": [_term_to_dict(t) for t in (g.terms or [])]}


@router.post("/glossaries/{glossary_id}/terms", status_code=201)
async def add_term_endpoint(
    glossary_id: str,
    body: CreateTermRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-01: Add a term pair to a glossary."""
    g = await get_glossary(session, glossary_id)
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


@router.delete("/glossaries/{glossary_id}/terms/{term_id}", status_code=204)
async def delete_term_endpoint(
    glossary_id: str,
    term_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    """GLOS-01/05: Delete a term. No confirmation dialog (terms are cheap to re-add)."""
    deleted = await delete_term(session, term_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Term not found")


@router.post("/glossaries/{glossary_id}/terms/import")
async def import_terms_endpoint(
    glossary_id: str,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """GLOS-02: Bulk import terms from CSV or TBX file.

    Returns {imported: N, skipped_duplicates: M}.
    Raises 422 on parse error (CSV malformed, TBX invalid XML).
    """
    g = await get_glossary(session, glossary_id)
    if g is None:
        raise HTTPException(status_code=404, detail="Glossary not found")

    content = await file.read()
    # Enforce upload size (same 25MB cap as main upload endpoint)
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
```

After creating the route, register it in `backend/src/app/api/__init__.py` (or `main.py` — check where jobs.py router is included). The router must be mounted alongside the jobs router. Check `backend/src/app/main.py` to verify inclusion pattern.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && uv run --directory backend pytest backend/tests/api/test_glossaries.py -x -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - test_glossaries.py xfail tests now pass (or become xpass)
    - GET /glossaries returns {"glossaries": []} on fresh DB (wrapped, not bare array)
    - POST /glossaries 201 with id, name, source_lang, target_lang
    - GET /glossaries/{id} 404 for unknown id
    - DELETE /glossaries/{id} 204 for known id; 404 for unknown
    - GET /glossaries?source_lang=vi&target_lang=en filters correctly
  </done>
</task>

<task type="auto">
  <name>Task 3: Extend upload.py + job_service.py with glossary_id</name>
  <files>
    backend/src/app/api/routes/upload.py
    backend/src/app/services/job_service.py
  </files>
  <read_first>
    - backend/src/app/api/routes/upload.py (full file — find Form field signature, glossary validation insertion point, create_job call)
    - backend/src/app/services/job_service.py (full file — create_job function signature to extend)
    - .planning/phases/02-review-ux-glossary/02-PATTERNS.md §upload.py (extension point at line 46, validation pattern)
    - .planning/phases/02-review-ux-glossary/02-CONTEXT.md D-02-24 (single-select glossary picker), D-02-25 (filters to matching pair), D-02-26 (locked at submit; pair mismatch → 422)
  </read_first>
  <action>
**upload.py changes** (surgical edits only):

1. Add import for glossary service:
   ```python
   from app.services.glossary_service import get_glossary
   ```

2. Add `glossary_id` Form field after `tracked_changes_action` in the endpoint function signature:
   ```python
   glossary_id: str | None = Form(None),
   ```

3. Add glossary pair validation after the existing language validation block:
   ```python
   # D-02-26: validate glossary pair matches job pair; 422 on mismatch (D-02-25)
   if glossary_id is not None:
       g = await get_glossary(session, glossary_id)
       if g is None:
           raise HTTPException(status_code=422, detail="Glossary not found.")
       if g.source_lang != source_lang or g.target_lang != target_lang:
           raise HTTPException(
               status_code=422,
               detail="The selected glossary does not match the language pair.",
           )
   ```

4. Pass `glossary_id` to `create_job` call:
   ```python
   job = await create_job(
       ...,
       glossary_id=glossary_id,
   )
   ```

**job_service.py changes** (surgical edits only):

1. Add `glossary_id: str | None = None` parameter to `create_job` function signature.
2. Pass `glossary_id=glossary_id` when constructing the `Job` object.

Find the exact `Job(...)` constructor call in `create_job` and add `glossary_id=glossary_id`.

Do NOT change any other behavior of upload.py or job_service.py. Do not touch error handling, retry logic, or file saving.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation && grep -n "glossary_id" backend/src/app/api/routes/upload.py backend/src/app/services/job_service.py</automated>
  </verify>
  <done>
    - `glossary_id: str | None = Form(None)` present in upload.py endpoint signature
    - Glossary pair validation block present in upload.py (after language validation)
    - `create_job` in job_service.py accepts and persists `glossary_id`
    - Existing upload tests still pass: `uv run pytest backend/tests/api/test_upload.py -x -q`
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → POST /glossaries | Name field is user-supplied string |
| client → POST /glossaries/{id}/terms/import | File content is user-supplied; may be malformed CSV/TBX |
| client → POST /upload with glossary_id | FK value is user-supplied; must validate pair match |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-03-01 | DoS | POST /glossaries/{id}/terms/import | mitigate | File size enforced (25MB cap same as upload endpoint). `xml.etree.ElementTree` does not expand external entities — safe for untrusted TBX. |
| T-02-03-02 | Tampering | CSV formula injection | accept | Term data stored as TEXT; rendered in React JSX (auto-escapes HTML); never executed as code or formula. |
| T-02-03-03 | Integrity | glossary_id FK pair mismatch on upload | mitigate | Backend validates `glossary.source_lang == job.source_lang && glossary.target_lang == job.target_lang` before creating job; returns 422 per UI-SPEC copy. |
| T-02-03-04 | Information Disclosure | 404 vs 403 on glossary not found | accept | PoC has no multi-tenant ownership; returning 404 for unknown IDs is both correct and prevents enumeration in a future multi-user context. |
</threat_model>

<verification>
After all tasks in this plan:

1. `uv run pytest backend/tests/services/test_glossary_service.py backend/tests/services/test_csv_import.py backend/tests/services/test_tbx_import.py -x -q` — xfail tests pass
2. `uv run pytest backend/tests/services/test_post_check.py -x -q` — all 5 stubs pass (overflow, glossary_violation, placeholder_mismatch, llm_refusal, short-term skip)
3. `uv run pytest backend/tests/api/test_glossaries.py -x -q` — tests pass
4. `uv run pytest backend/tests/api/test_upload.py -x -q` — existing upload tests still pass
5. `grep -q "glossary_id" backend/src/app/services/job_service.py` — exits 0
6. `uv run pytest backend/tests/ -m "not integration" -x -q` — all tests green
</verification>

<success_criteria>
- glossary_service.py implements all CRUD + CSV/TBX parsers + load_glossary_terms_for_job + run_post_check (all 4 flag types)
- glossaries.py route has all 9 endpoints; GET /glossaries returns {"glossaries": [...]} (wrapped)
- upload.py accepts glossary_id Form field; validates pair match (422 on mismatch)
- job_service.py persists glossary_id on job creation
- run_post_check writes overflow, glossary_violation, placeholder_mismatch, llm_refusal flags
- All 131+ existing unit tests still pass
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-03-SUMMARY.md`
</output>
