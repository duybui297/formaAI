"""
Native PDF reassembler — redact-reinsert per text block with Noto font embedding.

PDF-02: Redact-annot workflow with Noto CJK fonts.
PDF-03: Overflow detection when insert_htmlbox returns spare_height < 0 (scale_low=0.7).
D-03-05: Images/vector graphics preserved via PDF_REDACT_IMAGE_NONE flag.
LAYOUT-02: Overflow SegmentFlags persisted by worker from overflow_flags out-param.
LAYOUT-03: Auto-adjusted metadata in overflow_flags entries.

CRITICAL ORDERING (Pitfall #3 from RESEARCH.md):
  For each page:
    Pass 1: ALL add_redact_annot calls
    Pass 2: SINGLE apply_redactions call
    Pass 3: ALL insert_htmlbox calls
  NEVER interleave passes 2 and 3 — insert_htmlbox text placed before apply_redactions
  will be erased by the redaction pass.

PITFALL: scale_low default is 0 — insert_htmlbox ALWAYS succeeds, never reports overflow.
  ALWAYS pass scale_low=0.7 to get spare_height < 0 signal when text still overflows at 70%.

PITFALL: PyMuPDF's text-block bboxes hug visible glyphs and can be much shorter
  than the typeset line height (especially for CJK rows in tables — observed 3.9pt
  bboxes for 8-9pt fonts). Redact-then-reinsert into such a rect produces a blank
  cell because insert_htmlbox cannot fit any line. We skip both the redact AND
  the reinsert for these undersized rects, leaving the source text visible
  (untranslated) and emit an overflow flag so the user knows.
"""
from __future__ import annotations

import pymupdf

from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.pdf.fonts import build_noto_archive_and_css
from app.pipeline.segment import Segment

# Minimum rect height (in PDF points) required to safely redact + reinsert.
# Below this, insert_htmlbox cannot fit a line even at scale_low=0.7 and we
# end up with a blank cell. Empirical threshold from PoC test PDFs.
_MIN_RECT_HEIGHT_PT = 6.0


def reassemble_pdf(
    doc: pymupdf.Document,
    segments: list[Segment],
    translated_map: dict[str, str],
    output_path: str,
    overflow_flags: list[dict],  # out-parameter: worker reads this to persist SegmentFlags
) -> None:
    """
    Redact and reinsert translated text into the PDF document.

    Parameters
    ----------
    doc           : pymupdf.Document — opened from job.input_path
    segments      : list[Segment] — from extract_pdf_segments()
    translated_map: {segment_id: translated_text}
    output_path   : path to write the output PDF
    overflow_flags: list to append overflow/auto-adjusted flag dicts into
                    (out-parameter — worker persists SegmentFlags from this)

    Note: doc is modified in-place. Caller should not reuse doc after this call.
    """
    arch, css = build_noto_archive_and_css()

    # Group segments by page
    segs_by_page: dict[int, list[Segment]] = {}
    for seg in segments:
        if not seg.structural_position.startswith("page."):
            continue
        page_num = int(seg.structural_position.split(".")[1])
        segs_by_page.setdefault(page_num, []).append(seg)

    for page_num, page in enumerate(doc):
        page_segs = segs_by_page.get(page_num, [])
        if not page_segs:
            continue

        # Re-extract block layout to get bboxes (same algorithm as extractor)
        raw_blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in raw_blocks if b["type"] == 0]
        if not text_blocks:
            continue

        column_groups, is_degraded = cluster_columns(text_blocks, page.rect.width)

        # Build a map from structural_position to block dict by reconstructing
        # the same walk order as extract_pdf_segments()
        pos_to_block: dict[str, dict] = {}
        for col_idx, col_blocks in enumerate(column_groups):
            for block_idx, block in enumerate(col_blocks):
                if is_degraded:
                    pos = f"page.{page_num}.block.{block_idx}"
                else:
                    pos = f"page.{page_num}.col.{col_idx}.block.{block_idx}"
                pos_to_block[pos] = block

        # Match segments to blocks. Partition into "active" (safe to redact +
        # reinsert) and "skipped" (rect too small — leave source untranslated).
        active_pairs: list[tuple[Segment, dict]] = []
        for seg in page_segs:
            block = pos_to_block.get(seg.structural_position)
            if block is None:
                continue
            bbox = block["bbox"]
            rect_h = bbox[3] - bbox[1]
            if rect_h < _MIN_RECT_HEIGHT_PT:
                # Too short to safely fit any line — flag and skip both
                # redact and reinsert (preserves source text visibly).
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "scale_applied": 0.0,
                    "reason": "rect_too_small",
                    "rect_height": round(rect_h, 2),
                })
                continue
            active_pairs.append((seg, block))

        if not active_pairs:
            continue

        # ----------------------------------------------------------------
        # Pass 1: Mark ALL text blocks for redaction
        # Must precede apply_redactions — see RESEARCH.md Pitfall #3
        # ----------------------------------------------------------------
        for _seg, block in active_pairs:
            rect = pymupdf.Rect(block["bbox"])
            # fill=False → transparent redaction (preserves background color/graphics)
            page.add_redact_annot(rect, fill=False)

        # ----------------------------------------------------------------
        # Pass 2: Apply redactions (images + vector graphics preserved)
        # PDF_REDACT_IMAGE_NONE = 0: preserve images (do NOT remove) (D-03-05)
        # PDF_REDACT_LINE_ART_NONE = 0: preserve vector graphics (do NOT remove)
        # ----------------------------------------------------------------
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        )

        # ----------------------------------------------------------------
        # Pass 3: Insert translated HTML into each block's rect
        # scale_low=0.7: MUST be set — default 0 never reports overflow (Pitfall #2)
        # ----------------------------------------------------------------
        for seg, block in active_pairs:
            translated_html = translated_map.get(seg.id, seg.source_text)
            rect = pymupdf.Rect(block["bbox"])

            try:
                spare_height, scale = page.insert_htmlbox(
                    rect,
                    translated_html,
                    css=css,
                    archive=arch,
                    scale_low=0.7,  # D-03-02: stop scaling at 70%; spare_height<0 if overflows
                    overlay=True,
                )
            except Exception as exc:
                # Per-block isolation: log error and continue (T-03-03 mitigation)
                import structlog  # noqa: PLC0415
                structlog.get_logger().warning(
                    "pdf_insert_htmlbox_failed",
                    segment_id=seg.id,
                    position=seg.structural_position,
                    error=str(exc),
                )
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "scale_applied": 0.0,
                    "error": str(exc),
                })
                continue

            if spare_height < 0:
                # PDF-03: text did not fit at scale_low=0.7 → overflow flag
                # LAYOUT-02: worker will persist SegmentFlag(overflow)
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "scale_applied": round(scale, 3),
                })
            elif scale < 1.0:
                # LAYOUT-03: text fit but was scaled — record as auto-adjusted
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": False,
                    "auto_adjusted": True,
                    "scale_applied": round(scale, 3),
                })

    # Finalize
    doc.subset_fonts()  # reduce output file size
    doc.save(output_path, garbage=3, deflate=True)
