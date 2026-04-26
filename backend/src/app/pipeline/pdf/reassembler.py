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
from app.pipeline.pdf.extractor import _body_font_size
from app.pipeline.pdf.fonts import build_noto_archive_and_css
from app.pipeline.segment import Segment

# Minimum rect dimensions (in PDF points) required to safely redact + reinsert.
# Below either threshold, insert_htmlbox cannot fit even one glyph at scale_low=0.7
# and the cell ends up blank. Empirical thresholds from PoC test PDFs.
#
# Height < 6pt: typical of dense table rows where the bbox hugs visible glyphs.
# Width  < 20pt: typical of rotated / vertically-stacked column strips in
#                academic-paper tables where each "block" is one narrow column.
_MIN_RECT_HEIGHT_PT = 6.0
_MIN_RECT_WIDTH_PT = 20.0


def _clip_rect_away_from_images(
    rect: pymupdf.Rect,
    image_rects: list[pymupdf.Rect],
) -> pymupdf.Rect:
    """
    Shrink rect to avoid overlapping adjacent image blocks.

    Strategy:
    - For each image rect that intersects the text rect:
        - Image to the right: clip text rect's right edge to image's left edge
        - Image below: clip text rect's bottom edge to image's top edge
    - Returns the (possibly clipped) rect. If no overlap, returns the original rect unchanged.

    Does NOT clip left or top edges — captions typically extend right or down
    when translated text expands, not left or up.

    PPTX-analog: mirrors the auto-fit shape-height guard; same conservative principle.

    Gap 2 fix (PDF-02/PDF-03): caption text no longer overflows into adjacent image area.
    """
    clipped = pymupdf.Rect(rect)  # copy
    for img in image_rects:
        if not clipped.intersects(img):
            continue
        # Image overlaps from the right: clip right edge to image's left edge
        if img.x0 > clipped.x0:
            clipped = pymupdf.Rect(clipped.x0, clipped.y0, min(clipped.x1, img.x0), clipped.y1)
        # Image overlaps from the left: clip left edge to image's right edge
        elif img.x1 < clipped.x1:
            clipped = pymupdf.Rect(max(clipped.x0, img.x1), clipped.y0, clipped.x1, clipped.y1)
        # Image is below rect: clip bottom edge
        if img.y0 > clipped.y0 and img.y0 < clipped.y1:
            clipped = pymupdf.Rect(clipped.x0, clipped.y0, clipped.x1, img.y0)
    return clipped


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

        # Collect image block rects for collision detection (Gap 2 fix — PDF-02/PDF-03)
        image_rects = [
            pymupdf.Rect(b["bbox"])
            for b in raw_blocks
            if b["type"] == 1
        ]

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

        # Recover cell bboxes for table_cell segments by re-running find_tables()
        # (same source doc, same page — table structure is stable between extract and reassemble)
        table_cell_bboxes: dict[str, pymupdf.Rect] = {}
        try:
            finder = page.find_tables()
            for t_idx, tbl in enumerate(finder.tables):
                for r in range(tbl.row_count):
                    for c in range(tbl.col_count):
                        cell_idx = r * tbl.col_count + c
                        if cell_idx >= len(tbl.cells):
                            continue
                        cell = tbl.cells[cell_idx]
                        if cell is None:
                            continue
                        pos_key = f"page.{page_num}.table.{t_idx}.row.{r}.col.{c}"
                        table_cell_bboxes[pos_key] = pymupdf.Rect(cell)
        except Exception as exc:  # noqa: BLE001
            import structlog as _sl  # noqa: PLC0415
            _sl.get_logger().warning("reassembler_find_tables_failed", page=page_num, error=str(exc))

        # Match segments to blocks. Partition into "active" (safe to redact +
        # reinsert) and "skipped" (rect too small — leave source untranslated).
        # kind-aware dispatch:
        #   math_passthrough → skip entirely (source glyphs stay intact)
        #   table_cell       → cell bbox from find_tables(); synthetic block dict
        #   text (default)   → existing pos_to_block lookup (unchanged)
        active_pairs: list[tuple[Segment, dict]] = []
        for seg in page_segs:
            # math_passthrough: skip both redact and reinsert — source page region stays intact
            if seg.kind == "math_passthrough":
                continue

            if seg.kind == "table_cell":
                cell_rect = table_cell_bboxes.get(seg.structural_position)
                if cell_rect is None:
                    # find_tables() missed this cell — skip silently
                    continue
                rect_w = cell_rect.width
                rect_h = cell_rect.height
                if rect_h < _MIN_RECT_HEIGHT_PT or rect_w < _MIN_RECT_WIDTH_PT:
                    overflow_flags.append({
                        "segment_id": seg.id,
                        "overflow": True,
                        "auto_adjusted": False,
                        "scale_applied": 0.0,
                        "reason": "table_cell_rect_too_small",
                        "rect_width": round(rect_w, 2),
                        "rect_height": round(rect_h, 2),
                    })
                    continue
                # Create a minimal synthetic "block" dict compatible with Pass 1/3.
                # bbox tuple (x0, y0, x1, y1) works with pymupdf.Rect(block["bbox"]).
                # _body_font_size() returns 12.0 fallback for empty "lines" list —
                # acceptable for table cells per CONTEXT.md deferred items.
                synthetic_block = {
                    "bbox": (cell_rect.x0, cell_rect.y0, cell_rect.x1, cell_rect.y1),
                    "lines": [],
                }
                active_pairs.append((seg, synthetic_block))
                continue

            # Default: kind == "text" — existing pos_to_block lookup (unchanged)
            block = pos_to_block.get(seg.structural_position)
            if block is None:
                continue
            bbox = block["bbox"]
            rect_w = bbox[2] - bbox[0]
            rect_h = bbox[3] - bbox[1]
            if rect_h < _MIN_RECT_HEIGHT_PT or rect_w < _MIN_RECT_WIDTH_PT:
                # Too short or too narrow to safely fit text — flag and skip
                # both redact and reinsert (preserves source visibly).
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "auto_adjusted": False,
                    "scale_applied": 0.0,
                    "reason": "rect_too_small",
                    "rect_width": round(rect_w, 2),
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
            # fill=None → transparent redaction (preserves background color/graphics)
            page.add_redact_annot(rect, fill=None)

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
        # Gap 2 fix: clip rect away from adjacent images before inserting
        # NOTE: Pass 1 redaction still uses the ORIGINAL rect to fully erase source text.
        # ----------------------------------------------------------------
        for seg, block in active_pairs:
            translated_html = translated_map.get(seg.id, seg.source_text)
            rect = pymupdf.Rect(block["bbox"])

            # Wrap translated HTML in a per-block size container so headings (em)
            # and body text render at the original block's body font size instead
            # of PyMuPDF's browser-default 16pt or a hard-coded global override.
            body_pt = _body_font_size(block)
            sized_html = f'<div style="font-size:{body_pt:.1f}pt">{translated_html}</div>'

            # Gap 2 fix: clip rect to avoid overlapping adjacent images
            safe_rect = _clip_rect_away_from_images(rect, image_rects)
            rect_w = safe_rect.width
            rect_h = safe_rect.height
            if rect_h < _MIN_RECT_HEIGHT_PT or rect_w < _MIN_RECT_WIDTH_PT:
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "auto_adjusted": False,
                    "scale_applied": 0.0,
                    "reason": "image_collision",
                    "rect_width": round(rect_w, 2),
                    "rect_height": round(rect_h, 2),
                })
                continue

            try:
                spare_height, scale = page.insert_htmlbox(
                    safe_rect,  # use clipped rect, not original rect
                    sized_html,
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
                    "auto_adjusted": False,
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
                    "auto_adjusted": False,
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
