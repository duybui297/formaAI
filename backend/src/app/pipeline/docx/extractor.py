"""
DOCX document traversal and segment extraction.

CORE-01: Full document traversal order — body paragraphs + table cells (row-major)
         + headers + footers. Never uses doc.paragraphs (Pitfall #2 in RESEARCH.md).
DOCX-01: Uses doc.iter_inner_content() and cell.iter_inner_content() recursively
         to visit nested tables.
CORE-04: NFC-normalizes source_text at extraction time (Pitfall #7).
D-06:    Segment ID is sha256(source_text + structural_position)[:16].
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from typing import TYPE_CHECKING

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.pipeline.segment import Segment, make_segment_id

if TYPE_CHECKING:
    pass


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time (Pitfall #7 in RESEARCH.md)."""
    return unicodedata.normalize("NFC", s)


def walk_document(doc: Document) -> Iterator[tuple[str, Paragraph]]:
    """
    Yield all (location_tag, paragraph) pairs in document order.

    Visit order:
      1. Body paragraphs + table cells (row-major via iter_inner_content)
      2. Per-section: header, footer, even/first-page variants

    CRITICAL: Uses doc.iter_inner_content(), NOT doc.paragraphs.
    doc.paragraphs only returns body-level paragraphs; it silently misses
    table cells, headers, footers, and text boxes (DOCX-01 Pitfall #2).
    """
    yield from _walk_body(doc)
    for section in doc.sections:
        for hf in [
            section.header,
            section.footer,
            section.even_page_header,
            section.even_page_footer,
            section.first_page_header,
            section.first_page_footer,
        ]:
            if hf is not None and not hf.is_linked_to_previous:
                yield from _walk_element_paragraphs(hf._element, "header")


def _walk_body(doc: Document) -> Iterator[tuple[str, Paragraph]]:
    """Walk top-level body content: paragraphs and tables."""
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            yield ("para", block)
        elif isinstance(block, Table):
            yield from _walk_table(block)


def _walk_table(table: Table) -> Iterator[tuple[str, Paragraph]]:
    """
    Walk table cells in row-major order (top-to-bottom, left-to-right within row).
    Recurses into nested tables via cell.iter_inner_content() — NOT cell.paragraphs,
    which would miss nested tables (DOCX-01 Pitfall #2).
    """
    for row in table.rows:
        for cell in row.cells:
            for block in cell.iter_inner_content():
                if isinstance(block, Paragraph):
                    yield ("cell_para", block)
                elif isinstance(block, Table):
                    yield from _walk_table(block)


def _walk_element_paragraphs(
    element: object,
    location_tag: str,
) -> Iterator[tuple[str, Paragraph]]:
    """
    Walk a raw lxml element yielding Paragraph objects found at any depth.
    Used for headers/footers which are accessed via their _element directly.
    """
    for p_elem in element.iter(qn("w:p")):  # type: ignore[union-attr]
        yield (location_tag, Paragraph(p_elem, None))  # type: ignore[arg-type]


def _run_format_key(run) -> tuple:  # type: ignore[type-arg]
    """
    Return a tuple that identifies run formatting for merge-group detection.

    T-13-02: color access wrapped in try/except — a malformed <w:rPr> that raises
    on .rgb access must not crash the extraction pipeline.
    """
    color = None
    try:
        if run.font.color and run.font.color.type is not None:
            color = str(run.font.color.rgb)
    except Exception:  # noqa: BLE001
        pass
    return (run.bold, run.italic, run.underline, color, run.font.name, run.font.size)


def extract_run_segments(doc: Document, job_id: str) -> list[Segment]:
    """
    Like extract_segments() but splits at run-format boundaries within each paragraph.

    Consecutive runs with identical formatting are merged into one Segment (cost
    optimisation — reduces DashScope call volume for richly formatted docs).
    Each Segment carries run_index (first run in the group) and run_group_size.

    Falls back to paragraph-level extraction for paragraphs with no runs (run_index=None).

    CORE-01/DOCX-01: uses the same walk_document() traversal as extract_segments().
    CORE-04: NFC-normalises source_text at extraction time.
    D-06: Segment ID is sha256(source_text + structural_position)[:16].

    The job_id parameter is accepted for caller convenience but does not affect
    segment IDs — they are job-independent by design (D-06).
    """
    segments: list[Segment] = []
    seq = 0
    para_seq = 0  # counts non-empty paragraphs visited (walk-order counter for reassembly)

    for loc_tag, paragraph in walk_document(doc):
        runs = paragraph.runs

        if not runs:
            # No runs — fall back to paragraph-level extraction
            raw_text = paragraph.text
            text = _nfc(raw_text)
            if not text.strip():
                para_seq += 1
                continue
            structural_position = f"{loc_tag}.{para_seq}"
            segment = Segment.from_text(
                source_text=text,
                structural_position=structural_position,
                seq_in_job=seq,
                run_index=None,
                run_group_size=1,
            )
            segments.append(segment)
            seq += 1
            para_seq += 1
            continue

        # Group consecutive runs by format key
        groups: list[tuple[int, list]] = []  # (first_run_idx, [run, ...])
        for run_idx, run in enumerate(runs):
            if groups and _run_format_key(run) == _run_format_key(groups[-1][1][0]):
                groups[-1][1].append(run)
            else:
                groups.append((run_idx, [run]))

        # Emit one Segment per non-empty group
        para_had_content = False
        for first_run_idx, group_runs in groups:
            group_text = _nfc("".join(r.text for r in group_runs))
            if not group_text.strip():
                continue
            structural_position = f"{loc_tag}.{para_seq}.run{first_run_idx}"
            segment = Segment.from_text(
                source_text=group_text,
                structural_position=structural_position,
                seq_in_job=seq,
                run_index=first_run_idx,
                run_group_size=len(group_runs),
            )
            segments.append(segment)
            seq += 1
            para_had_content = True

        # Always advance the paragraph counter so it matches the walk order
        # consumed by reassembler.reassemble_docx_runs (CORE-03 pairing).
        para_seq += 1

    return segments


def extract_segments(doc: Document, job_id: str) -> list[Segment]:
    """
    Walk the document and build an ordered Segment list.

    - Skips empty paragraphs (no text or whitespace-only).
    - NFC-normalizes source_text at extraction (CORE-04, Pitfall #7).
    - Segment.id is sha256(source_text + structural_position)[:16] (D-06).
    - seq_in_job is assigned in walk order (0-indexed).

    The job_id parameter is accepted for caller convenience (may be used in
    future logging/tracing) but does not affect segment IDs — they are
    job-independent by design (D-06).
    """
    segments: list[Segment] = []
    seq = 0

    for loc_tag, paragraph in walk_document(doc):
        raw_text = paragraph.text
        text = _nfc(raw_text)
        if not text.strip():
            continue

        # Structural position encodes location and sequence for deterministic IDs
        structural_position = f"{loc_tag}.{seq}"
        segment = Segment.from_text(
            source_text=text,
            structural_position=structural_position,
            seq_in_job=seq,
        )
        segments.append(segment)
        seq += 1

    return segments
