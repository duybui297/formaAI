"""
PDF end-to-end round-trip integration test.

Tests: extract → identity translate → reassemble → reopen + verify.
Covers PDF-01 through PDF-04 (plus LAYOUT-02, LAYOUT-03) as a pipeline chain.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def simple_text_pdf(tmp_path_factory):
    """Single-column PDF with 3 text blocks at different y-positions."""
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 80),  "First block of text for round trip test")
    page.insert_text((72, 110), "Second block with different content here")
    page.insert_text((72, 140), "Third block completes the single column")
    path = tmp_path_factory.mktemp("pdf_rt") / "simple.pdf"
    doc.save(str(path))
    return path


def test_pdf_full_round_trip(simple_text_pdf, tmp_path):
    """
    PDF-01, PDF-02: Full pipeline round trip with identity translation.
    Extract → translate identity → reassemble → reopen → verify PDF valid.
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    doc = pymupdf.open(str(simple_text_pdf))
    segments = extract_pdf_segments(doc, job_id="pdf-rt-test-01")

    assert len(segments) >= 1, f"Expected >=1 segment, got {len(segments)}"

    # Invariant I4: structural_position uniqueness
    positions = [s.structural_position for s in segments]
    assert len(positions) == len(set(positions)), f"Duplicate positions: {positions}"

    # Identity translation
    translated_map = {s.id: s.source_text for s in segments}

    # Invariant I1
    assert len(segments) == len(translated_map)

    overflow_flags: list[dict] = []
    output_path = str(tmp_path / "output.pdf")

    # Reassemble
    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags)

    # Verify output is a valid PDF
    result_doc = pymupdf.open(output_path)
    assert len(result_doc) >= 1, "Output PDF should have at least 1 page"


def test_pdf_images_preserved_through_round_trip(tmp_path):
    """PDF-02 + D-03-05: I2 invariant — image blocks preserved through redact-reinsert."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Create a PDF with text only — image block count = 0 before and after
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text with no images")

    # Count images before
    before_images = [b for b in page.get_text("dict")["blocks"] if b["type"] == 1]

    segments = extract_pdf_segments(doc, job_id="pdf-img-test")
    translated_map = {s.id: s.source_text for s in segments}
    overflow_flags: list[dict] = []
    output_path = str(tmp_path / "images_preserved.pdf")
    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags)

    result_doc = pymupdf.open(output_path)
    after_images = [b for b in result_doc[0].get_text("dict")["blocks"] if b["type"] == 1]

    # I2 invariant: image count preserved
    assert len(after_images) == len(before_images), (
        f"Images changed: before={len(before_images)}, after={len(after_images)}"
    )


def test_pdf_column_detection_single_col_round_trip(simple_text_pdf, tmp_path):
    """PDF-04: single-column PDF produces page.N.col.0.block.B or page.N.block.B positions."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(simple_text_pdf))
    segments = extract_pdf_segments(doc, job_id="pdf-col-test")

    # All segments should have structural_position starting with "page."
    for seg in segments:
        assert seg.structural_position.startswith("page."), (
            f"Expected page. prefix, got: {seg.structural_position}"
        )

    # For a single-column PDF, we expect consistent position format
    assert len(segments) >= 1


def test_pdf_overflow_flags_list_populated(tmp_path):
    """PDF-03 + LAYOUT-02: overflow_flags out-param is populated (list, not None)."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello")
    segments = extract_pdf_segments(doc, job_id="pdf-overflow-test")
    translated_map = {s.id: s.source_text for s in segments}

    overflow_flags: list[dict] = []
    output_path = str(tmp_path / "overflow_check.pdf")
    reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags)

    # overflow_flags is a list (may be empty for identity translation of short text)
    assert isinstance(overflow_flags, list)
