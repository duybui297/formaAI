"""Unit tests: D-04-17 text-density scanned PDF detection heuristic."""
from __future__ import annotations

import pytest
import pymupdf

from app.pipeline.scanned_pdf.detector import detect_scanned_pdf


def _make_pdf_with_text(text: str) -> pymupdf.Document:
    """Create an in-memory single-page PDF with the given text."""
    doc = pymupdf.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 100), text)
    return doc


def _make_empty_pdf() -> pymupdf.Document:
    """Create an in-memory single-page PDF with no text."""
    doc = pymupdf.open()
    doc.new_page()  # blank page, no text
    return doc


@pytest.mark.unit
def test_detect_native_pdf_returns_false(tmp_path):
    """PDF with plenty of text is classified as native (not scanned)."""
    # A paragraph of text — far above 50 chars/page threshold
    long_text = "This is a native PDF document with extractable text. " * 5
    doc = _make_pdf_with_text(long_text)
    result = detect_scanned_pdf(doc)
    assert result is False


@pytest.mark.unit
def test_detect_scanned_pdf_returns_true(tmp_path):
    """PDF with no extractable text is classified as scanned."""
    doc = _make_empty_pdf()
    result = detect_scanned_pdf(doc)
    assert result is True


@pytest.mark.unit
def test_detect_uses_configurable_threshold(tmp_path):
    """Text density threshold is configurable via threshold parameter."""
    # 30 chars of text on 1 page → chars_per_page = 30
    text = "A" * 30
    doc = _make_pdf_with_text(text)

    # With threshold=50 (default): 30 < 50 → scanned
    assert detect_scanned_pdf(doc, threshold=50.0) is True
    # With threshold=20: 30 >= 20 → native
    assert detect_scanned_pdf(doc, threshold=20.0) is False
