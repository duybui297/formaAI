"""
PDF extractor TDD tests.

Tests PDF-01: block extraction + structural_position generation.
RED until plan 04 implements pipeline/pdf/extractor.py.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def single_col_pdf(tmp_path_factory):
    """Single-column PDF with 3 text blocks."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF world")
    page.insert_text((72, 100), "Second line of text")
    page.insert_text((72, 128), "Third block content")
    path = tmp_path_factory.mktemp("pdf_fixtures") / "single.pdf"
    doc.save(str(path))
    return path


@pytest.fixture(scope="module")
def image_only_pdf(tmp_path_factory):
    """Adversarial: PDF with no text layer (all images) — should return empty segments."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    # No text insertion — image-only page
    path = tmp_path_factory.mktemp("pdf_fixtures") / "image_only.pdf"
    doc.save(str(path))
    return path


def test_extract_pdf_segments_single_col(single_col_pdf):
    """PDF-01: single-column PDF produces at least 1 segment with source_text."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-pdf-01")
    assert len(segments) >= 1, f"Expected >=1 segment, got: {len(segments)}"
    texts = [s.source_text for s in segments]
    assert any("Hello" in t for t in texts), f"Expected 'Hello' in texts, got: {texts}"


def test_extract_pdf_segments_structural_position_has_page(single_col_pdf):
    """PDF-01: structural_position includes page number."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-pdf-01b")
    assert all(
        s.structural_position.startswith("page.") for s in segments
    ), f"structural_position should start with 'page.', got: {[s.structural_position for s in segments]}"


def test_extract_pdf_segments_uniqueness(single_col_pdf):
    """I4 invariant: structural_position values are unique."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-pdf-unique")
    positions = [s.structural_position for s in segments]
    assert len(positions) == len(set(positions)), f"Duplicate positions: {positions}"


def test_extract_pdf_segments_image_only_returns_empty(image_only_pdf):
    """Adversarial: image-only PDF returns empty segment list without crashing."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    doc = pymupdf.open(str(image_only_pdf))
    segments = extract_pdf_segments(doc, job_id="test-pdf-imageonly")
    assert segments == []
