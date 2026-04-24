"""
Glossary service: CRUD functions for Glossary and GlossaryTerm rows,
plus post-translation check logic.

D-02-01: glossaries + glossary_terms two-table schema.
D-02-03: (glossary_id, source_term) unique constraint; hard-delete only.
D-02-04: CSV primary, TBX minimal via ElementTree.
D-02-07: Terms shorter than 2 chars are skipped in post-check.
GLOS-03: load_glossary_terms_for_job — called by worker before batch loop.
GLOS-04: run_post_check — called per batch after translation completes.
LAYOUT-01: overflow detection via expansion_ratio threshold.
"""
from __future__ import annotations

import csv
import io
import re

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    FlagSeverity,
    FlagType,
    Glossary,
    GlossaryTerm,
    Segment,
    SegmentFlag,
)

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


async def create_glossary(
    session: AsyncSession,
    name: str,
    source_lang: str,
    target_lang: str,
) -> Glossary:
    """GLOS-01: Create a new glossary row."""
    g = Glossary(name=name, source_lang=source_lang, target_lang=target_lang)
    session.add(g)
    await session.commit()
    await session.refresh(g)
    log.info("glossary_created", glossary_id=g.id, name=g.name)
    return g


async def get_glossary(session: AsyncSession, glossary_id: str) -> Glossary | None:
    """Return the glossary with the given ID, or None if not found."""
    result = await session.execute(
        select(Glossary).where(Glossary.id == glossary_id)
    )
    return result.scalar_one_or_none()


async def list_glossaries(
    session: AsyncSession,
    source_lang: str | None = None,
    target_lang: str | None = None,
) -> list[Glossary]:
    """GLOS-01/05: List all glossaries, optionally filtered by language pair."""
    stmt = select(Glossary)
    if source_lang is not None:
        stmt = stmt.where(Glossary.source_lang == source_lang)
    if target_lang is not None:
        stmt = stmt.where(Glossary.target_lang == target_lang)
    result = await session.execute(stmt.order_by(Glossary.created_at.desc()))
    return list(result.scalars().all())


async def update_glossary(
    session: AsyncSession,
    glossary_id: str,
    name: str,
) -> Glossary | None:
    """Update glossary name. Returns None if not found."""
    g = await get_glossary(session, glossary_id)
    if g is None:
        return None
    g.name = name
    await session.commit()
    return g


async def delete_glossary(session: AsyncSession, glossary_id: str) -> bool:
    """Hard-delete a glossary and its terms (CASCADE). Returns True if deleted."""
    result = await session.execute(
        delete(Glossary).where(Glossary.id == glossary_id)
    )
    await session.commit()
    return result.rowcount > 0


async def create_term(
    session: AsyncSession,
    glossary_id: str,
    source_term: str,
    target_term: str,
    notes: str | None = None,
) -> GlossaryTerm:
    """Add a single term to a glossary."""
    term = GlossaryTerm(
        glossary_id=glossary_id,
        source_term=source_term,
        target_term=target_term,
        notes=notes,
    )
    session.add(term)
    await session.commit()
    await session.refresh(term)
    return term


async def delete_term(session: AsyncSession, term_id: str) -> bool:
    """Hard-delete a single glossary term. Returns True if deleted."""
    result = await session.execute(
        delete(GlossaryTerm).where(GlossaryTerm.id == term_id)
    )
    await session.commit()
    return result.rowcount > 0


# ---------------------------------------------------------------------------
# CSV / TBX import
# ---------------------------------------------------------------------------


def parse_csv_glossary(content: bytes) -> list[dict]:
    """
    Parse CSV glossary file. Expected columns: source_term, target_term[, notes].

    Returns list of {source_term, target_term, notes} dicts.
    Raises ValueError on malformed CSV.
    """
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file is empty or has no header row")

    # Normalize fieldnames to lowercase
    fieldnames_lower = [f.lower().strip() for f in reader.fieldnames]
    if "source_term" not in fieldnames_lower or "target_term" not in fieldnames_lower:
        raise ValueError(
            "CSV must have 'source_term' and 'target_term' columns "
            f"(got: {list(reader.fieldnames)})"
        )

    rows = []
    for i, row in enumerate(reader, start=2):
        # Normalize keys to lowercase
        row_lower = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        src = row_lower.get("source_term", "").strip()
        tgt = row_lower.get("target_term", "").strip()
        if not src or not tgt:
            log.warning("csv_import_skip_empty_row", row=i)
            continue
        rows.append({
            "source_term": src,
            "target_term": tgt,
            "notes": row_lower.get("notes") or None,
        })
    return rows


def parse_tbx_minimal(content: bytes) -> list[dict]:
    """
    Parse minimal TBX (TermBase eXchange) file.
    Extracts <termEntry> elements with source/target lang terms.

    Returns list of {source_term, target_term, notes} dicts.
    """
    import xml.etree.ElementTree as ET  # noqa: PLC0415

    try:
        root = ET.fromstring(content.decode("utf-8", errors="replace"))
    except ET.ParseError as exc:
        raise ValueError(f"Invalid TBX XML: {exc}") from exc

    rows = []
    # TBX namespace varies; strip namespace for robustness
    for entry in root.iter():
        if entry.tag.endswith("termEntry"):
            terms_by_lang: dict[str, str] = {}
            for lang_set in entry.iter():
                if lang_set.tag.endswith("langSet"):
                    lang = lang_set.get("{http://www.w3.org/XML/1998/namespace}lang") or lang_set.get("lang", "")
                    for term_el in lang_set.iter():
                        if term_el.tag.endswith("term") and term_el.text:
                            terms_by_lang[lang] = term_el.text.strip()
                            break
            langs = list(terms_by_lang.keys())
            if len(langs) >= 2:
                rows.append({
                    "source_term": terms_by_lang[langs[0]],
                    "target_term": terms_by_lang[langs[1]],
                    "notes": None,
                })
    return rows


async def import_csv_terms(
    session: AsyncSession,
    glossary: Glossary,
    content: bytes,
    ext: str,
) -> dict:
    """
    GLOS-02: Import terms from CSV or TBX file.

    Returns {imported: N, skipped_duplicates: M}.
    """
    if ext in (".tbx",):
        rows = parse_tbx_minimal(content)
    else:
        rows = parse_csv_glossary(content)

    # Load existing (source_term) set to detect duplicates
    existing_result = await session.execute(
        select(GlossaryTerm.source_term).where(GlossaryTerm.glossary_id == glossary.id)
    )
    existing_terms = {row[0] for row in existing_result.all()}

    imported = 0
    skipped = 0
    for row in rows:
        src = row["source_term"]
        if src in existing_terms:
            skipped += 1
            continue
        term = GlossaryTerm(
            glossary_id=glossary.id,
            source_term=src,
            target_term=row["target_term"],
            notes=row.get("notes"),
        )
        session.add(term)
        existing_terms.add(src)
        imported += 1

    await session.commit()
    log.info("terms_imported", glossary_id=glossary.id, imported=imported, skipped=skipped)
    return {"imported": imported, "skipped_duplicates": skipped}


# ---------------------------------------------------------------------------
# Worker helpers — called by translate_worker.py
# ---------------------------------------------------------------------------


async def load_glossary_terms_for_job(
    session: AsyncSession,
    glossary_id: str | None,
) -> dict[str, str] | None:
    """
    GLOS-03: Load glossary terms as {source_term: target_term} dict.

    Called by worker ONCE before the batch translate loop.
    Returns None if no glossary is attached to the job.
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


# ---------------------------------------------------------------------------
# Post-translation check (GLOS-04, LAYOUT-01)
# ---------------------------------------------------------------------------

# D-02-07: skip terms shorter than 2 chars in glossary violation check
_MIN_TERM_LEN = 2

# Default expansion ratio thresholds by language pair
_DEFAULT_THRESHOLDS: dict[str, float] = {
    "en->vi": 1.3,
    "vi->en": 0.9,
    "ja->vi": 1.5,
    "vi->ja": 0.9,
    "vi->zh": 0.85,
    "en->ja": 1.6,
}
_DEFAULT_THRESHOLD_FALLBACK = 1.5


def _get_threshold(
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> float:
    """Return the expansion ratio threshold for the given language pair."""
    key = f"{source_lang}->{target_lang}"
    return expansion_thresholds.get(key, _DEFAULT_THRESHOLD_FALLBACK)


def _check_glossary_violation(
    source_text: str,
    translated_text: str,
    glossary: dict[str, str],
) -> list[str]:
    """
    Return list of source terms that appear in source_text but whose target
    term is NOT present in translated_text.

    D-02-07: skips terms shorter than _MIN_TERM_LEN chars.
    """
    violations = []
    for src_term, tgt_term in glossary.items():
        if len(src_term) < _MIN_TERM_LEN:
            continue
        # Case-insensitive substring check for source term in source text
        if re.search(re.escape(src_term), source_text, re.IGNORECASE):
            # Check if target term appears in translated text (case-insensitive)
            if not re.search(re.escape(tgt_term), translated_text, re.IGNORECASE):
                violations.append(src_term)
    return violations


async def run_post_check(
    session: AsyncSession,
    batch_segs: list,
    translated_map: dict[str, str],
    glossary: dict[str, str] | None,
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> None:
    """
    GLOS-04 + LAYOUT-01: Post-translation check per batch.

    For each segment:
    - Compute expansion_ratio = len(translated) / len(source) (char-level)
    - Store expansion_ratio on Segment row
    - If expansion_ratio > threshold: write overflow SegmentFlag (warn)
    - If glossary term violated (D-02-07 applies): write glossary_violation flag (warn)
    - Detect LLM refusal markers: write llm_refusal flag (block)

    Does NOT mutate translated_text — only writes flags and expansion_ratio.
    """
    threshold = _get_threshold(source_lang, target_lang, expansion_thresholds)

    # LLM refusal patterns (heuristic)
    _refusal_patterns = [
        r"I (cannot|can't|am unable to) (translate|process)",
        r"(translation|content) (not|cannot be) (provided|generated)",
        r"as an AI",
    ]
    refusal_re = re.compile("|".join(_refusal_patterns), re.IGNORECASE)

    for seg in batch_segs:
        translated = translated_map.get(seg.id)
        if translated is None:
            continue

        src_len = len(seg.source_text)
        tgt_len = len(translated)

        # Compute and store expansion_ratio
        ratio: float | None = None
        if src_len > 0:
            ratio = tgt_len / src_len

        await session.execute(
            __import__("sqlalchemy", fromlist=["update"]).update(Segment)
            .where(Segment.id == seg.id)
            .values(expansion_ratio=ratio)
        )

        # LAYOUT-01: overflow flag
        if ratio is not None and ratio > threshold:
            flag = SegmentFlag(
                segment_id=seg.id,
                flag_type=FlagType.overflow,
                severity=FlagSeverity.warn,
                details={
                    "expansion_ratio": ratio,
                    "threshold": threshold,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                },
            )
            session.add(flag)

        # GLOS-04: glossary violation check
        if glossary:
            violations = _check_glossary_violation(
                seg.source_text, translated, glossary
            )
            if violations:
                flag = SegmentFlag(
                    segment_id=seg.id,
                    flag_type=FlagType.glossary_violation,
                    severity=FlagSeverity.warn,
                    details={"violated_terms": violations},
                )
                session.add(flag)

        # LLM refusal detection
        if refusal_re.search(translated):
            flag = SegmentFlag(
                segment_id=seg.id,
                flag_type=FlagType.llm_refusal,
                severity=FlagSeverity.block,
                details={"translated_text_excerpt": translated[:200]},
            )
            session.add(flag)

    await session.commit()
