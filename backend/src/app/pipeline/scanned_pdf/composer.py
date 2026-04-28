"""
Bilingual PDF composition using fpdf2 (OCR-03, D-04-07/08/09).

Produces three output artifacts from the same translated Segment state (D-04-22):
  1. output.pdf       — bilingual: left=original page image, right=translated text
  2. output-translated-only.pdf — translated text only (single-column)
  3. output.docx      — translated DOCX via segment_to_md + python-docx

Uses FPDF(unit="mm") with explicit NotoSans/NotoSansCJK font registration.
Falls back to Helvetica when Noto fonts are not present (development/CI environments).
PyMuPDF page dimensions (in PDF points) are converted to mm via _pt_to_mm().
"""
from __future__ import annotations

import math
import os

import pymupdf
import structlog

from app.pipeline.segment import Segment

log = structlog.get_logger()

_NOTO_SANS = "/backend/fonts/NotoSans-Regular.ttf"
# D-04-27: prefer Sans CJK when bundled; accept Serif CJK as alternate when
# Sans variant is unavailable (Google Fonts ships Serif CJK as a default download).
_NOTO_CJK_CANDIDATES = (
    "/backend/fonts/NotoSansCJK-Regular.ttc",
    "/backend/fonts/NotoSerifCJK-Regular.ttc",
)

# Font size range for fit-to-region (D-04-29)
_MIN_FONT_PT = 8.0
_MAX_FONT_PT = 24.0
_FONT_CANDIDATES = [24.0, 18.0, 14.0, 10.0, 8.0]

# D-04-24: region_label → initial font size hint
_LABEL_FONT_SIZE: dict[str, float] = {
    "doc_title": 18.0,
    "paragraph_title": 14.0,
    "footnote": 8.0,
    "page_number": 8.0,
}


def _pt_to_mm(pt: float) -> float:
    """Convert PDF points to millimetres (1pt = 25.4/72 mm)."""
    return pt * 25.4 / 72.0


def _estimate_fits(text: str, font_size_pt: float, w_mm: float, h_mm: float) -> bool:
    """
    Rough estimate: does `text` fit in w_mm × h_mm at font_size_pt?
    Uses avg char width ≈ 0.55× font_size (mm) for Latin text.
    This is an approximation; real rendering may differ slightly.
    """
    if not text or w_mm <= 0 or h_mm <= 0:
        return True
    # fpdf2 uses 1 font point = 1/72 inch = 0.3528 mm
    char_w_mm = font_size_pt * 0.3528 * 0.55
    if char_w_mm <= 0:
        return True
    chars_per_line = max(1, int(w_mm / char_w_mm))
    line_h_mm = font_size_pt * 0.3528 * 1.4  # 1.4 line-height
    num_lines = math.ceil(len(text) / chars_per_line)
    return (num_lines * line_h_mm) <= h_mm


def _init_pdf():
    """Create and initialize an fpdf2 FPDF instance with Noto fonts.

    Falls back to built-in Helvetica when Noto fonts are absent (CI / dev).
    Returns (pdf, primary_font_name).
    """
    from fpdf import FPDF  # noqa: PLC0415

    pdf = FPDF(unit="mm")

    # Register Noto fonts when available (D-04-27)
    noto_available = os.path.exists(_NOTO_SANS)
    noto_cjk_path = next(
        (p for p in _NOTO_CJK_CANDIDATES if os.path.exists(p)),
        None,
    )

    if noto_available:
        pdf.add_font("NotoSans", fname=_NOTO_SANS)
        primary_font = "NotoSans"
    else:
        log.debug("noto_sans_font_missing_using_fallback", path=_NOTO_SANS)
        primary_font = "Helvetica"  # built-in fpdf2 fallback

    if noto_cjk_path:
        pdf.add_font("NotoCJK", fname=noto_cjk_path)
        pdf.set_fallback_fonts(["NotoCJK"])
    else:
        log.debug("noto_cjk_font_missing", candidates=_NOTO_CJK_CANDIDATES)

    return pdf, primary_font


def _render_region(
    pdf,
    primary_font: str,
    translated_text: str,
    region_bbox: tuple[float, float, float, float],
    region_label: str,
    src_w_mm: float,
    src_h_mm: float,
    right_offset_mm: float,
) -> bool:
    """
    Render translated_text in the right half at the proportional position.
    Returns True if text overflows at minimum font size (D-04-29).

    D-04-08: right-side text at proportionally-mapped region position.
    """
    x0n, y0n, x1n, y1n = region_bbox
    x_mm = right_offset_mm + x0n * src_w_mm
    y_mm = y0n * src_h_mm
    w_mm = max(5.0, (x1n - x0n) * src_w_mm)
    h_mm = max(3.0, (y1n - y0n) * src_h_mm)

    # Initial font size from label hint (D-04-29)
    initial_size = _LABEL_FONT_SIZE.get(region_label, 11.0)
    initial_size = max(_MIN_FONT_PT, min(_MAX_FONT_PT, initial_size))

    # Find largest font size in [8, 24] that fits (D-04-29)
    chosen_size = _MIN_FONT_PT
    overflowed = True
    for size in _FONT_CANDIDATES:
        if size > initial_size:
            continue
        if _estimate_fits(translated_text, size, w_mm, h_mm):
            chosen_size = size
            overflowed = False
            break

    try:
        pdf.set_xy(x_mm, y_mm)
        pdf.set_font(primary_font, size=chosen_size)
        pdf.multi_cell(w=w_mm, text=translated_text, align="L")
    except Exception as exc:
        log.warning("compose_region_render_failed", error=str(exc))

    return overflowed


def _segs_by_page(segments: list[Segment]) -> dict[int, list[Segment]]:
    """Group segments by page number from structural_position 'page.N.region.M'."""
    result: dict[int, list[Segment]] = {}
    for seg in segments:
        pos = seg.structural_position or ""
        parts = pos.split(".")
        if len(parts) >= 2 and parts[0] == "page":
            try:
                page_num = int(parts[1])
                result.setdefault(page_num, []).append(seg)
            except ValueError:
                pass
    return result


def compose_bilingual_pdf(
    segments: list[Segment],
    translated_map: dict[str, str],
    pages_dir: str,
    output_path: str,
    overflow_flags: list[dict],
    src_doc: pymupdf.Document,
) -> None:
    """
    D-04-07: Double-wide pages (left=source image, right=translated text).
    D-04-08: Right-side text at proportionally-mapped region positions.
    D-04-22: Writes bilingual output.pdf only; caller produces the other two.
    overflow_flags out-parameter: populated with overflow events for caller to persist.
    """
    pdf, primary_font = _init_pdf()
    by_page = _segs_by_page(segments)

    for page_num, src_page in enumerate(src_doc):
        src_w_mm = _pt_to_mm(src_page.rect.width)
        src_h_mm = _pt_to_mm(src_page.rect.height)

        # D-04-07: double-wide page
        pdf.add_page(format=(2 * src_w_mm, src_h_mm))

        # Left half: original page image
        png_path = os.path.join(pages_dir, f"page-{page_num}.png")
        if os.path.exists(png_path):
            pdf.image(png_path, x=0, y=0, w=src_w_mm, h=src_h_mm, keep_aspect_ratio=True)

        # Right half: translated text per region, sorted top-to-bottom
        page_segs = sorted(
            by_page.get(page_num, []),
            key=lambda s: s.region_bbox[1] if s.region_bbox else 0.0,
        )

        for seg in page_segs:
            if seg.region_bbox is None:
                continue  # placeholder segments (figure_passthrough, OCR-error)
            if seg.kind == "figure_passthrough":
                translated = "[Figure on left]"
            else:
                translated = translated_map.get(seg.id, seg.source_text)

            try:
                overflowed = _render_region(
                    pdf,
                    primary_font,
                    translated,
                    seg.region_bbox,
                    seg.region_label or "text",
                    src_w_mm,
                    src_h_mm,
                    right_offset_mm=src_w_mm,  # right half starts at x=src_w_mm
                )
                if overflowed:
                    overflow_flags.append({
                        "segment_id": seg.id,
                        "overflow": True,
                        "auto_adjusted": False,
                        "reason": "min_font_overflow",
                    })
            except Exception as exc:
                log.warning("compose_segment_failed", segment_id=seg.id, error=str(exc))
                overflow_flags.append({
                    "segment_id": seg.id,
                    "overflow": True,
                    "auto_adjusted": False,
                    "error": str(exc),
                })

    pdf.output(output_path)
    log.info("bilingual_pdf_composed", path=output_path, pages=len(src_doc))


def compose_translated_only_pdf(
    segments: list[Segment],
    translated_map: dict[str, str],
    output_path: str,
    src_doc: pymupdf.Document,
) -> None:
    """
    D-04-22: Translated-only PDF (right side rendered as standalone single-column PDF).
    Same region positions as bilingual right-side, but left-side image is omitted.
    Page dimensions match source page (not double-wide).
    """
    pdf, primary_font = _init_pdf()
    by_page = _segs_by_page(segments)

    for page_num, src_page in enumerate(src_doc):
        src_w_mm = _pt_to_mm(src_page.rect.width)
        src_h_mm = _pt_to_mm(src_page.rect.height)
        pdf.add_page(format=(src_w_mm, src_h_mm))

        page_segs = sorted(
            by_page.get(page_num, []),
            key=lambda s: s.region_bbox[1] if s.region_bbox else 0.0,
        )

        for seg in page_segs:
            if seg.region_bbox is None or seg.kind == "figure_passthrough":
                continue
            translated = translated_map.get(seg.id, seg.source_text)
            try:
                _render_region(
                    pdf,
                    primary_font,
                    translated,
                    seg.region_bbox,
                    seg.region_label or "text",
                    src_w_mm,
                    src_h_mm,
                    right_offset_mm=0.0,  # no offset — single-column
                )
            except Exception as exc:
                log.warning(
                    "compose_translated_only_failed",
                    segment_id=seg.id,
                    error=str(exc),
                )

    pdf.output(output_path)
    log.info("translated_only_pdf_composed", path=output_path)
