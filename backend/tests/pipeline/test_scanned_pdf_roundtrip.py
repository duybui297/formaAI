"""
Round-trip unit test: mocked PaddleOCR → segments → composed PDF → page count match.

Tests the full pipeline chain:
  extract_scanned_pdf_segments  →  compose_bilingual_pdf
                                →  compose_translated_only_pdf
                                →  segments_to_markdown + md_to_docx

PaddleOCR (PP-StructureV3) is mocked via conftest.py fixture;
no real model weights needed for this unit test.
"""
from __future__ import annotations

import os

import pymupdf
import pytest

from app.pipeline.scanned_pdf.extractor import extract_scanned_pdf_segments
from app.pipeline.scanned_pdf.composer import (
    compose_bilingual_pdf,
    compose_translated_only_pdf,
)
from app.pipeline.scanned_pdf.segment_to_md import segments_to_markdown, md_to_docx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_pdf(path: str, n_pages: int = 2) -> None:
    """Create a blank multi-page PDF (no extractable text — simulates scanned PDF)."""
    doc = pymupdf.open()
    for _ in range(n_pages):
        page = doc.new_page(width=595, height=842)  # A4 in points
        # Draw a rect so page is visually non-empty; no text layer
        page.draw_rect(
            pymupdf.Rect(50, 50, 100, 100),
            color=(0, 0, 0),
            fill=(0.9, 0.9, 0.9),
        )
    doc.save(path)
    doc.close()


# ---------------------------------------------------------------------------
# Round-trip unit test (mocked PaddleOCR)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scanned_pdf_roundtrip_unit(mock_ppstructurev3, tmp_path):
    """
    Full round-trip: canned OCR output → segments → all 3 artifacts produced.

    Steps:
    1. Create a 2-page scanned PDF (no text layer).
    2. Extract segments via extract_scanned_pdf_segments with mock pipeline.
    3. Build a synthetic translated_map from segment IDs.
    4. Compose bilingual PDF → assert page count == 2.
    5. Compose translated-only PDF → assert file exists.
    6. Generate DOCX via segments_to_markdown + md_to_docx → assert file exists.
    7. Assert low_confidence_pages is empty (mock has high confidence).
    """
    # 1. Create synthetic scanned PDF
    input_pdf_path = str(tmp_path / "source.pdf")
    _make_minimal_pdf(input_pdf_path, n_pages=2)

    src_doc = pymupdf.open(input_pdf_path)
    pages_dir = str(tmp_path / "pages")
    os.makedirs(pages_dir, exist_ok=True)

    # 2. Extract segments with mocked PP-StructureV3
    segments, low_conf_pages = await extract_scanned_pdf_segments(
        doc=src_doc,
        job_id="roundtrip-test-job",
        pages_dir=pages_dir,
        pipeline=mock_ppstructurev3,
        dpi=72,  # low DPI speeds up test
    )

    # 3. Synthetic translated_map: identity translation for all OCR segments
    translated_map = {seg.id: f"[translated] {seg.source_text}" for seg in segments}

    # 4. Compose bilingual PDF
    bilingual_path = str(tmp_path / "output.pdf")
    overflow_flags: list[dict] = []
    compose_bilingual_pdf(
        segments=segments,
        translated_map=translated_map,
        pages_dir=pages_dir,
        output_path=bilingual_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    assert os.path.exists(bilingual_path), "output.pdf must be created"
    result_doc = pymupdf.open(bilingual_path)
    assert len(result_doc) == 2, (
        f"Bilingual PDF should have {len(src_doc)} pages (one per source page), "
        f"got {len(result_doc)}"
    )
    result_doc.close()

    # 5. Compose translated-only PDF
    translated_only_path = str(tmp_path / "output-translated-only.pdf")
    compose_translated_only_pdf(
        segments=segments,
        translated_map=translated_map,
        output_path=translated_only_path,
        src_doc=src_doc,
    )

    assert os.path.exists(translated_only_path), "output-translated-only.pdf must be created"
    translated_doc = pymupdf.open(translated_only_path)
    assert len(translated_doc) >= 1, "Translated-only PDF must have at least 1 page"
    translated_doc.close()

    # 6. DOCX via markdown
    md_text = segments_to_markdown(segments)
    docx_path = str(tmp_path / "output.docx")
    md_to_docx(md_text, docx_path)

    assert os.path.exists(docx_path), "output.docx must be created"
    assert os.path.getsize(docx_path) > 0, "output.docx must be non-empty"

    # 7. Low-confidence pages: mock returns rec_scores [0.92, 0.85, 0.91] → mean ≈ 0.893 > 0.7
    assert low_conf_pages == [], (
        f"Mock has high confidence; expected no low-conf pages, got {low_conf_pages}"
    )

    src_doc.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scanned_pdf_roundtrip_low_confidence(
    low_confidence_mock_ppstructurev3, tmp_path
):
    """
    Low-confidence mock produces low_confidence_pages entry.
    All 3 artifacts are still produced — low confidence does not abort compose.
    """
    input_pdf_path = str(tmp_path / "source.pdf")
    _make_minimal_pdf(input_pdf_path, n_pages=1)

    src_doc = pymupdf.open(input_pdf_path)
    pages_dir = str(tmp_path / "pages")
    os.makedirs(pages_dir, exist_ok=True)

    segments, low_conf_pages = await extract_scanned_pdf_segments(
        doc=src_doc,
        job_id="roundtrip-lowconf-test",
        pages_dir=pages_dir,
        pipeline=low_confidence_mock_ppstructurev3,
        dpi=72,
    )

    # Low-conf mock: page 0 should be flagged
    assert 0 in low_conf_pages, (
        f"Expected page 0 in low_conf_pages (rec_scores mean ≈ 0.45 < 0.7), "
        f"got {low_conf_pages}"
    )

    # Artifacts are still produced
    translated_map = {seg.id: seg.source_text for seg in segments}
    overflow_flags: list[dict] = []
    bilingual_path = str(tmp_path / "output.pdf")
    compose_bilingual_pdf(
        segments=segments,
        translated_map=translated_map,
        pages_dir=pages_dir,
        output_path=bilingual_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    assert os.path.exists(bilingual_path), "Bilingual PDF created even with low confidence"

    src_doc.close()


# ---------------------------------------------------------------------------
# Integration test (real PaddleOCR, skipped when fixture missing)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_scanned_pdf_roundtrip_integration(tmp_path):
    """
    Real PaddleOCR round-trip on a typed Vietnamese PDF fixture.

    Skipped when:
    - PaddleOCR is not installed (ImportError)
    - Fixture file backend/tests/fixtures/scanned/vn-typed.pdf is absent
    """
    fixture_path = os.path.join(
        os.path.dirname(__file__), "..", "fixtures", "scanned", "vn-typed.pdf"
    )
    if not os.path.exists(fixture_path):
        pytest.skip("vn-typed.pdf fixture not present — skipping integration test")

    try:
        from paddleocr import PPStructureV3  # type: ignore[import]
    except ImportError:
        pytest.skip("PaddleOCR not installed — skipping integration test")

    pipeline = PPStructureV3()
    src_doc = pymupdf.open(fixture_path)
    pages_dir = str(tmp_path / "pages")
    os.makedirs(pages_dir, exist_ok=True)

    segments, low_conf_pages = await extract_scanned_pdf_segments(
        doc=src_doc,
        job_id="integration-roundtrip",
        pages_dir=pages_dir,
        pipeline=pipeline,
        dpi=150,
    )

    assert len(segments) >= 1, "Real OCR should produce at least 1 segment"

    translated_map = {seg.id: seg.source_text for seg in segments}
    overflow_flags: list[dict] = []
    bilingual_path = str(tmp_path / "output.pdf")
    compose_bilingual_pdf(
        segments=segments,
        translated_map=translated_map,
        pages_dir=pages_dir,
        output_path=bilingual_path,
        overflow_flags=overflow_flags,
        src_doc=src_doc,
    )

    result_doc = pymupdf.open(bilingual_path)
    assert len(result_doc) == len(src_doc), (
        "Integration: bilingual PDF page count must match source"
    )
    result_doc.close()
    src_doc.close()
