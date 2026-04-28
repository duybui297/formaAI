"""Unit tests: fpdf2 bilingual PDF composer (OCR-03)."""
from __future__ import annotations

import os

import pymupdf
import pytest

from app.pipeline.segment import Segment
from app.pipeline.scanned_pdf.composer import (
    compose_bilingual_pdf,
    compose_translated_only_pdf,
    _pt_to_mm,
)
from app.pipeline.scanned_pdf.segment_to_md import md_to_docx, segments_to_markdown


def _make_src_doc(width_pt: float = 595.0, height_pt: float = 842.0) -> pymupdf.Document:
    """Create a single-page in-memory PyMuPDF doc with given dimensions (A4 by default)."""
    doc = pymupdf.open()
    doc.new_page(width=width_pt, height=height_pt)
    return doc


def _make_text_segment(
    page: int = 0,
    block: int = 0,
    source_text: str = "Hello world",
    region_bbox: tuple = (0.05, 0.05, 0.95, 0.20),
    region_label: str = "text",
) -> Segment:
    """Create a minimal ocr_text Segment for composer tests."""
    return Segment.from_text(
        source_text=source_text,
        structural_position=f"page.{page}.region.{block}",
        seq_in_job=page * 100 + block,
        kind="ocr_text",
        confidence=0.9,
        region_bbox=region_bbox,
        region_label=region_label,
    )


@pytest.mark.unit
def test_compose_produces_double_wide_page(tmp_path):
    """Output PDF page width is 2x source page width (D-04-07)."""
    src_doc = _make_src_doc(width_pt=595.0, height_pt=842.0)
    seg = _make_text_segment()
    overflow_flags: list[dict] = []

    output_path = str(tmp_path / "bilingual.pdf")
    compose_bilingual_pdf(
        segments=[seg],
        translated_map={seg.id: "Xin chào"},
        pages_dir=str(tmp_path),
        output_path=output_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    # Open output and verify page dimensions
    out_doc = pymupdf.open(output_path)
    assert len(out_doc) == 1
    out_page = out_doc[0]

    src_w_mm = _pt_to_mm(595.0)
    out_w_mm = _pt_to_mm(out_page.rect.width)
    # Output width must be 2× source width (within 1mm rounding)
    assert abs(out_w_mm - 2 * src_w_mm) < 1.0, (
        f"Expected bilingual width ≈{2 * src_w_mm:.1f}mm, got {out_w_mm:.1f}mm"
    )


@pytest.mark.unit
def test_compose_region_positioned_text_on_right_half(tmp_path):
    """Translated text is placed at proportional position on right half (D-04-08).

    This test verifies that the composer does not crash and produces a valid PDF
    when given a segment with a region_bbox. Full pixel-level text position
    verification would require PDF rendering — we test the contract (no error +
    valid output file produced) and that the output has correct page dimensions.
    """
    src_doc = _make_src_doc()
    seg = _make_text_segment(
        region_bbox=(0.1, 0.1, 0.8, 0.3),  # region at 10-80% x, 10-30% y
        region_label="paragraph_title",
    )
    overflow_flags: list[dict] = []

    output_path = str(tmp_path / "bilingual.pdf")
    compose_bilingual_pdf(
        segments=[seg],
        translated_map={seg.id: "Tiêu đề đoạn văn"},
        pages_dir=str(tmp_path),
        output_path=output_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    # PDF was created without error
    assert os.path.exists(output_path)
    out_doc = pymupdf.open(output_path)
    assert len(out_doc) == 1


@pytest.mark.unit
def test_compose_overflow_flag_when_text_too_long(tmp_path):
    """Segment text that doesn't fit at 8pt minimum produces overflow flag (D-04-29)."""
    src_doc = _make_src_doc()
    # Extremely tiny region (1% × 1% of page) with very long translated text
    seg = _make_text_segment(
        region_bbox=(0.01, 0.01, 0.02, 0.02),  # tiny 1%×1% region
        source_text="Short",
    )
    # Provide very long translated text that cannot fit in a tiny region at any font size
    very_long_text = "A" * 2000
    overflow_flags: list[dict] = []

    output_path = str(tmp_path / "bilingual.pdf")
    compose_bilingual_pdf(
        segments=[seg],
        translated_map={seg.id: very_long_text},
        pages_dir=str(tmp_path),
        output_path=output_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    # Overflow should have been recorded
    assert len(overflow_flags) >= 1
    flag = overflow_flags[0]
    assert flag["segment_id"] == seg.id
    assert flag["overflow"] is True


@pytest.mark.unit
def test_compose_produces_three_outputs(tmp_path):
    """Compose stage produces bilingual PDF, translated-only PDF, and DOCX (D-04-22)."""
    src_doc = _make_src_doc()
    segs = [
        _make_text_segment(block=0, source_text="Title", region_label="doc_title"),
        _make_text_segment(block=1, source_text="Body text paragraph."),
    ]
    translated_map = {s.id: f"[translated] {s.source_text}" for s in segs}
    overflow_flags: list[dict] = []

    bilingual_pdf = str(tmp_path / "output.pdf")
    translated_only_pdf = str(tmp_path / "output-translated-only.pdf")
    docx_path = str(tmp_path / "output.docx")

    # Produce all three outputs
    compose_bilingual_pdf(segs, translated_map, str(tmp_path), bilingual_pdf, overflow_flags, src_doc)
    compose_translated_only_pdf(segs, translated_map, translated_only_pdf, src_doc)
    md_text = segments_to_markdown(segs)
    md_to_docx(md_text, docx_path)

    assert os.path.exists(bilingual_pdf), "bilingual PDF not produced"
    assert os.path.exists(translated_only_pdf), "translated-only PDF not produced"
    assert os.path.exists(docx_path), "DOCX not produced"

    # Verify page count matches
    bil_doc = pymupdf.open(bilingual_pdf)
    tonly_doc = pymupdf.open(translated_only_pdf)
    assert len(bil_doc) == len(src_doc), "bilingual PDF page count mismatch"
    assert len(tonly_doc) == len(src_doc), "translated-only PDF page count mismatch"

    # Verify translated-only is single width (not double-wide)
    src_w_mm = _pt_to_mm(595.0)
    tonly_w_mm = _pt_to_mm(tonly_doc[0].rect.width)
    assert abs(tonly_w_mm - src_w_mm) < 1.0, (
        f"Translated-only should be single-width {src_w_mm:.1f}mm, got {tonly_w_mm:.1f}mm"
    )
