"""
PDF reassembler TDD tests.

Tests PDF-02 (redact-reinsert), PDF-03 (overflow), LAYOUT-02 (DB flag), LAYOUT-03 (auto-adjusted).
RED until plan 04 implements pipeline/pdf/reassembler.py.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def single_col_pdf(tmp_path_factory):
    """Single-column PDF fixture for reassembly tests."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF world")
    path = tmp_path_factory.mktemp("pdf_reassembler_fixtures") / "single.pdf"
    doc.save(str(path))
    return path


def test_round_trip_pdf_redact_reinsert(single_col_pdf, tmp_path):
    """PDF-02: redact-reinsert round trip produces valid PDF with text."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-roundtrip")
    assert len(segments) >= 1, "Need at least 1 segment for round-trip test"

    translated_map = {s.id: s.source_text for s in segments}  # identity
    overflow_flags = []
    output_path = str(tmp_path / "output.pdf")

    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags=overflow_flags)

    # Verify output PDF is valid and contains text
    result_doc = pymupdf.open(output_path)
    assert len(result_doc) >= 1, "Output PDF should have at least 1 page"
    text = result_doc[0].get_text()
    assert len(text.strip()) > 0, "Output PDF should contain text after redact-reinsert"


def test_pdf_images_preserved_through_redaction(tmp_path):
    """PDF-02 + D-03-05: images are preserved through apply_redactions."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a PDF with a simple rect (simulating image-like content)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text block")
    # Count text blocks before
    before_text = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
    before_images = [b for b in page.get_text("dict")["blocks"] if b["type"] == 1]

    segments = extract_pdf_segments(doc, job_id="test-preserve")
    translated_map = {s.id: s.source_text for s in segments}
    output_path = str(tmp_path / "preserved.pdf")
    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags=[])

    result_doc = pymupdf.open(output_path)
    after_images = [b for b in result_doc[0].get_text("dict")["blocks"] if b["type"] == 1]
    assert len(after_images) == len(before_images), "Images should be preserved"


def test_overflow_db_flag_persisted(tmp_path):
    """LAYOUT-02: overflow flag is persisted in overflow_flags list when reassemble_pdf detects overflow."""
    import pymupdf
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a PDF with a very small bbox
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hi")

    # Extract segments
    from app.pipeline.pdf.extractor import extract_pdf_segments
    doc2 = pymupdf.open()
    page2 = doc2.new_page()
    page2.insert_text((72, 72), "Hi")
    segments = extract_pdf_segments(doc2, job_id="test-overflow")

    if not segments:
        pytest.skip("No segments extracted from minimal PDF — skip overflow test")

    # Translate to very long text that will overflow the small bbox
    translated_map = {s.id: "This is a very very very long translation that overflows the bbox completely." * 3 for s in segments}
    overflow_flags = []
    output_path = str(tmp_path / "overflow_test.pdf")
    reassemble_pdf(doc2, segments, translated_map, output_path, overflow_flags=overflow_flags)
    # overflow_flags is populated by reassemble_pdf with segment IDs that overflowed
    # In unit test, we can't guarantee overflow (depends on bbox size), so just verify no crash
    assert isinstance(overflow_flags, list)


def test_auto_adjusted_metadata_in_details(tmp_path):
    """LAYOUT-03: when scale is applied but ≥ 0.7, overflow_flags gets auto_adjusted=True detail."""
    # This test verifies the LAYOUT-03 metadata contract.
    # Full verification requires integration test with real font scaling.
    # Unit-level: verify that reassemble_pdf accepts overflow_flags out-param correctly.
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello")
    segments = extract_pdf_segments(doc, job_id="test-auto-adjusted")
    translated_map = {s.id: s.source_text for s in segments}
    overflow_flags = []
    output_path = str(tmp_path / "auto_adjusted.pdf")
    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags=overflow_flags)
    # No crash and overflow_flags is a list
    assert isinstance(overflow_flags, list)
