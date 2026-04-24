"""
DOCX reassembler — write translated text back into a Document.

DOCX-02: run-merge write-back invariant.
  NEVER call paragraph.text = value — it calls paragraph.clear() which
  destroys ALL <w:rPr> formatting (bold, italic, underline, font, color).
  Instead: writes into runs[0].text only, blanks runs[1:] without removing
  the <w:r> elements (preserving all formatting attributes).

CORE-04: NFC-normalize before write-back (both extraction and reassembly sides).
"""
from __future__ import annotations

import unicodedata

from docx import Document
from docx.text.paragraph import Paragraph

from app.pipeline.docx.extractor import walk_document
from app.pipeline.segment import Segment


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize before write-back."""
    return unicodedata.normalize("NFC", s)


def write_translated_paragraph(paragraph: Paragraph, translated_text: str) -> None:
    """
    DOCX-02 run-merge write-back.

    Writes translated_text into the paragraph without destroying run formatting.

    Strategy:
      - If paragraph has runs: write into runs[0].text, blank runs[1:].
        The <w:r> elements and their <w:rPr> children are NOT removed.
        Only the <w:t> content is changed.
      - If paragraph has no runs: add_run(translated_text) as a new run.

    FORBIDDEN anti-pattern: paragraph.text = value
      This calls paragraph.clear() then paragraph.add_run(text), which removes
      ALL <w:r> elements and therefore all bold/italic/underline/font/color.
      Never use it in any docx-writing code (CLAUDE.md anti-pattern table).
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(_nfc(translated_text))
        return

    # Write translated text into first run only
    runs[0].text = _nfc(translated_text)  # touches <w:t>; <w:rPr> preserved intact

    # Blank remaining runs — keep <w:r> elements (with their <w:rPr>) in place
    for run in runs[1:]:
        run.text = ""  # blank <w:t>, do NOT remove <w:r>


def write_translated_run(
    paragraph: Paragraph,
    seg: Segment,
    translated_text: str,
) -> None:
    """
    Write translated_text into the specific run slot identified by seg.run_index.

    If run_index is None: falls back to write_translated_paragraph() (no-runs para).

    T-13-01: validates run_index < len(paragraph.runs) before writing.
    If out-of-bounds, logs a warning and skips — never raises. A malformed DOCX
    that shifts run counts between extraction and reassembly produces a degraded
    (partially-translated) document, not a crash.

    Blanks runs[run_index+1 : run_index+run_group_size] to clear the merged group
    while preserving their <w:r>/<w:rPr> elements.
    """
    import logging  # noqa: PLC0415

    if seg.run_index is None:
        write_translated_paragraph(paragraph, translated_text)
        return

    runs = paragraph.runs

    # T-13-01: bounds validation
    if seg.run_index >= len(runs):
        logging.getLogger(__name__).warning(
            "write_translated_run: run_index %d out of bounds (para has %d runs) — skipping",
            seg.run_index,
            len(runs),
        )
        return

    runs[seg.run_index].text = _nfc(translated_text)

    # Blank the remaining runs of the merged group (keep <w:r>/<w:rPr> intact)
    end = min(seg.run_index + seg.run_group_size, len(runs))
    for r in runs[seg.run_index + 1 : end]:
        r.text = ""


def reassemble_docx_runs(
    doc: Document,
    segments: list[Segment],
    translated_texts: dict[str, str],
) -> Document:
    """
    Variant of reassemble_docx() that uses write_translated_run() to preserve
    per-run formatting. segments must have come from extract_run_segments().

    Uses the same sequential walk-order counter-matching pattern as reassemble_docx().
    Does NOT parse structural_position strings — walk-order position is authoritative.

    Returns the modified document (same object, mutated in-place).
    """
    # Build a mapping from para_seq → list of Segments for that paragraph.
    # Segments from extract_run_segments() embed para_seq in structural_position as
    # "{loc_tag}.{para_seq}.run{run_idx}" (or "{loc_tag}.{para_seq}" for no-run paras).
    # We reconstruct the grouping by walking segments in order and correlating with
    # the same walk_document() counter used during extraction.
    #
    # Algorithm: maintain para_seq counter; for each paragraph visited, pop all
    # segments at the front of the queue that belong to para_seq.

    seg_queue = list(segments)  # ordered by extraction walk

    # Pre-group segments by their structural para_seq prefix so we can pop them
    # in bulk when we reach the matching paragraph in the walk.
    # structural_position format: "{loc_tag}.{para_seq}" or "{loc_tag}.{para_seq}.run{n}"
    def _para_seq_from_pos(pos: str) -> int | None:
        parts = pos.split(".")
        # parts[0] = loc_tag (e.g. "para", "cell_para", "header")
        # parts[1] = para_seq (integer)
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                return None
        return None

    # Build a {para_seq: [Segment, ...]} dict from the segments list
    from collections import defaultdict  # noqa: PLC0415

    para_seg_map: dict[int, list[Segment]] = defaultdict(list)
    for seg in segments:
        ps = _para_seq_from_pos(seg.structural_position)
        if ps is not None:
            para_seg_map[ps].append(seg)

    para_seq = 0
    for _, paragraph in walk_document(doc):
        text = paragraph.text
        if not text.strip():
            # Skip empty paragraphs — but still increment counter only if the
            # extraction skipped them too. extract_run_segments always increments
            # para_seq for every visited paragraph (empty or not).
            para_seq += 1
            continue

        # Write back all segments that belong to this paragraph
        for seg in para_seg_map.get(para_seq, []):
            translated = translated_texts.get(seg.id)
            if translated is not None:
                write_translated_run(paragraph, seg, translated)

        para_seq += 1

    return doc


def reassemble_docx(
    doc: Document,
    segments: list[Segment],
    translated_texts: dict[str, str],
) -> Document:
    """
    Write translated text back into the document using run-merge strategy.

    translated_texts is keyed by segment.id (D-06 sha256 ID).
    Only segments present in translated_texts are written; others are left as-is.

    The traversal order must exactly match extract_segments() to ensure
    segments align with the correct paragraphs.

    Returns the modified document (same object, mutated in-place).
    """
    seq = 0
    for _, paragraph in walk_document(doc):
        text = paragraph.text
        if not text.strip():
            continue

        if seq < len(segments):
            seg = segments[seq]
            translated = translated_texts.get(seg.id)
            if translated is not None:
                write_translated_paragraph(paragraph, translated)
        seq += 1

    return doc
