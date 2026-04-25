"""
PPTX reassembler — write translated text back into a Presentation.

CRITICAL PITFALL: NEVER set paragraph.text = value — it calls paragraph.clear()
which destroys ALL <p:rPr> run formatting (bold, italic, font, color).
Same run-merge write-back as DOCX: runs[0].text = translated, runs[1:].text = "".

D-03-01: SmartArt segments (structural_position ends in '.smartart') are SKIPPED
         during write-back — translation was extracted but cannot be reinserted.
D-03-02: Auto-fit applied conservatively: only when shrink_factor >= 0.7.
         If shrink would go below 0.7, flag overflow instead.
LAYOUT-03: Auto-adjusted metadata returned in detect_pptx_overflow() result dict.
"""
from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING

from pptx.enum.text import MSO_AUTO_SIZE

from app.pipeline.segment import Segment

if TYPE_CHECKING:
    from pptx import Presentation


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at write-back time."""
    return unicodedata.normalize("NFC", s)


def _write_paragraph_runs(paragraph, translated_text: str) -> None:
    """
    PPTX run-merge write-back. Mirrors DOCX write_translated_paragraph exactly.

    python-pptx paragraph.runs returns list of Run objects with .text attribute.
    NEVER: paragraph.text = translated  (destroys all <p:rPr> run formatting)
    ALWAYS: runs[0].text = translated, runs[1:].text = "" (blank remaining runs)
    """
    runs = paragraph.runs
    if not runs:
        # Zero-run paragraph: add a run (preserves para-level formatting)
        paragraph.add_run().text = _nfc(translated_text)
        return
    runs[0].text = _nfc(translated_text)
    for run in runs[1:]:
        run.text = ""


def detect_pptx_overflow(shape, source_text: str, translated_text: str) -> dict:  # type: ignore[type-arg]
    """
    Measure whether translated text causes overflow in a shape's text frame.

    Uses character-count ratio as proxy for font-size shrink factor (D-03-02).
    Avoids requiring a rendering engine (text_frame.autofit_text() fails headless).

    Returns dict:
      overflow: bool      — True if shrink_factor < 0.7
      auto_adjusted: bool — True if auto-fit was applied (shrink_factor >= 0.7 but char_ratio > 1)
      char_ratio: float   — len(translated) / len(source)

    LAYOUT-03: auto_adjusted=True recorded in SegmentFlag.details by the worker.
    """
    char_ratio = len(translated_text) / max(len(source_text), 1)
    shrink_factor = 1.0 / char_ratio if char_ratio > 0 else 1.0

    if char_ratio <= 1.0:
        # Text got shorter or same length — no overflow concern
        return {"overflow": False, "auto_adjusted": False, "char_ratio": round(char_ratio, 3)}

    if shrink_factor >= 0.7:
        # Safe to auto-fit: font would shrink to >= 70% of original (D-03-02)
        try:
            shape.text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        except Exception:  # noqa: BLE001
            pass  # shape may not support auto_size (e.g. SmartArt — already skipped)
        return {"overflow": False, "auto_adjusted": True, "char_ratio": round(char_ratio, 3)}

    # shrink_factor < 0.7 — would make font too small; flag overflow, skip auto-fit
    return {"overflow": True, "auto_adjusted": False, "char_ratio": round(char_ratio, 3)}


def _write_back_text_frame(
    shape,
    text_frame,
    translated_map: dict[str, str],
    seg_by_pos: dict[str, Segment],
    shape_pos: str,
) -> list[dict]:  # type: ignore[type-arg]
    overflow_results: list[dict] = []  # type: ignore[type-arg]
    for para_idx, para in enumerate(text_frame.paragraphs):
        pos = f"{shape_pos}.tf.0.para.{para_idx}"
        seg = seg_by_pos.get(pos)
        if seg is None:
            continue
        translated = translated_map.get(seg.id, seg.source_text)
        _write_paragraph_runs(para, translated)
        # Overflow detection + auto-fit per D-03-02
        result = detect_pptx_overflow(shape, seg.source_text, translated)
        if result["overflow"] or result["auto_adjusted"]:
            overflow_results.append({"segment_id": seg.id, **result})
    return overflow_results


def _write_back_table(
    table,
    translated_map: dict[str, str],
    seg_by_pos: dict[str, Segment],
    shape_pos: str,
) -> list[dict]:  # type: ignore[type-arg]
    overflow_results: list[dict] = []  # type: ignore[type-arg]
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            for para_idx, para in enumerate(cell.text_frame.paragraphs):
                pos = f"{shape_pos}.table.row.{row_idx}.col.{col_idx}.para.{para_idx}"
                seg = seg_by_pos.get(pos)
                if seg is None:
                    continue
                translated = translated_map.get(seg.id, seg.source_text)
                _write_paragraph_runs(para, translated)
    return overflow_results


def _write_back_notes(
    notes_text_frame,
    translated_map: dict[str, str],
    seg_by_pos: dict[str, Segment],
    slide_idx: int,
) -> None:
    for para_idx, para in enumerate(notes_text_frame.paragraphs):
        pos = f"slide.{slide_idx}.notes.para.{para_idx}"
        seg = seg_by_pos.get(pos)
        if seg is None:
            continue
        translated = translated_map.get(seg.id, seg.source_text)
        _write_paragraph_runs(para, translated)


def _write_back_master(
    prs: "Presentation",
    translated_map: dict[str, str],
    seg_by_pos: dict[str, Segment],
) -> None:
    for master_idx, master in enumerate(prs.slide_masters):
        for shape_idx, shape in enumerate(master.shapes):
            if not shape.has_text_frame:
                continue
            for para_idx, para in enumerate(shape.text_frame.paragraphs):
                pos = f"master.{master_idx}.shape.{shape_idx}.para.{para_idx}"
                seg = seg_by_pos.get(pos)
                if seg is None:
                    continue
                translated = translated_map.get(seg.id, seg.source_text)
                _write_paragraph_runs(para, translated)


def _write_back_shapes(
    shapes,
    translated_map: dict[str, str],
    seg_by_pos: dict[str, Segment],
    pos_prefix: str,
) -> list[dict]:  # type: ignore[type-arg]
    """
    Recursively write translated text back into shapes.

    Returns list of overflow_result dicts for segments that need overflow/auto-adjusted flags.
    SmartArt positions (ending in '.smartart') are skipped silently (D-03-01).
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # noqa: PLC0415

    from app.pipeline.pptx.smartart import is_smartart  # noqa: PLC0415

    overflow_results: list[dict] = []  # type: ignore[type-arg]

    for shape_idx, shape in enumerate(shapes):
        shape_pos = f"{pos_prefix}.shape.{shape_idx}"

        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            overflow_results.extend(
                _write_back_shapes(
                    shape.shapes, translated_map, seg_by_pos, f"{shape_pos}.group"
                )
            )

        elif is_smartart(shape):
            # D-03-01: SmartArt write-back is SKIPPED
            # The segment exists in the review UI (translation shown) but XML is not modified
            continue

        elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            overflow_results.extend(
                _write_back_table(shape.table, translated_map, seg_by_pos, shape_pos)
            )

        elif shape.has_text_frame:
            overflow_results.extend(
                _write_back_text_frame(shape, shape.text_frame, translated_map, seg_by_pos, shape_pos)
            )

    return overflow_results


def reassemble_pptx(
    prs: "Presentation",
    segments: list[Segment],
    translated_map: dict[str, str],
) -> "tuple[Presentation, list[dict]]":
    """
    Write translations back into prs in-place.
    Returns (prs, overflow_results) — matches PDF reassembler's out-param pattern.

    SmartArt segments (structural_position ending in '.smartart') are SKIPPED (D-03-01).
    Overflow detection runs per shape after write-back (D-03-02, LAYOUT-03).
    Master text written back before slide loop.

    Returns:
        prs: mutated Presentation (same object as input)
        overflow_results: list of dicts with keys {segment_id, overflow, auto_adjusted, char_ratio}

    Caller unpacks: prs_out, pptx_overflow = reassemble_pptx(prs, segments, translated_map)
    """
    seg_by_pos = {s.structural_position: s for s in segments}

    # Master slides
    _write_back_master(prs, translated_map, seg_by_pos)

    all_overflow_results: list[dict] = []  # type: ignore[type-arg]
    for slide_idx, slide in enumerate(prs.slides):
        results = _write_back_shapes(slide.shapes, translated_map, seg_by_pos, f"slide.{slide_idx}")
        all_overflow_results.extend(results)
        # Notes
        if slide.has_notes_slide:
            _write_back_notes(
                slide.notes_slide.notes_text_frame, translated_map, seg_by_pos, slide_idx
            )

    return prs, all_overflow_results
