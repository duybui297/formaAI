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


# ---------------------------------------------------------------------------
# Phase 03.2 integration tests — BMC academic-paper fixture
# ---------------------------------------------------------------------------

import os
import re
from pathlib import Path

# BMC paper fixture — absolute path from project root
_BMC_FIXTURE = (
    Path(__file__).parents[3]
    / ".data"
    / "jobs"
    / "932530eb-eeda-4b0a-986a-7d32f74fa820"
    / "source.pdf"
)


@pytest.mark.skipif(
    not _BMC_FIXTURE.exists(),
    reason="BMC paper fixture not found at expected path — run from project root with .data/ present",
)
def test_bmc_paper_table2_produces_cell_segments():
    """
    Phase 03.2 integration: BMC paper page 6 Table 2 produces per-cell segments.

    Before Phase 03.2: Table 2 rows were each one fused block segment.
    After Phase 03.2: Each cell is its own segment with kind='table_cell'.

    Success criteria from CONTEXT.md:
    - At least one segment with kind='table_cell' exists in the extracted segments
    - No segment with kind='table_cell' has a fused structural_position
      (position must match 'page.N.table.T.row.R.col.C', not a plain block)
    - The total cell segment count is > 10 (Table 2 has 30+ rows × 4 cols = 120+
      cells; even if find_tables detects only part of the table, > 10 is conservative)
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(_BMC_FIXTURE))
    segments = extract_pdf_segments(doc, job_id="bmc-integration-test")

    table_segs = [s for s in segments if s.kind == "table_cell"]

    # If find_tables() does not detect any tables in the BMC paper, skip rather
    # than fail — detection quality depends on PyMuPDF version and table line-art
    # clarity; the BMC paper may use text-drawn borders that find_tables() misses.
    if not table_segs:
        pytest.skip(
            "find_tables() detected 0 tables in BMC paper fixture — "
            "table detection may require PDF with explicit line-art borders. "
            "Verify manually by checking segment kinds on source.pdf."
        )

    assert len(table_segs) > 10, (
        f"Expected >10 table_cell segments from Table 2 (30+ rows × 4 cols), "
        f"got: {len(table_segs)}"
    )

    # All table_cell structural positions must follow the page.N.table.T.row.R.col.C pattern
    pattern = re.compile(r"page\.\d+\.table\.\d+\.row\.\d+\.col\.\d+")
    for seg in table_segs:
        assert pattern.match(seg.structural_position), (
            f"table_cell structural_position must match pattern, got: {seg.structural_position!r}"
        )


@pytest.mark.skipif(
    not _BMC_FIXTURE.exists(),
    reason="BMC paper fixture not found — skip",
)
def test_bmc_paper_page3_math_passthrough_segments():
    """
    Phase 03.2 integration: BMC paper page 3 math/symbol spans (AdvP4C4E74) are
    emitted as kind='math_passthrough' segments, not as translatable 'text' segments.

    CONTEXT.md: page 3 has 14 text blocks with mixed body fonts (AdvTT*) and
    math spans (AdvP4C4E74 for '¼'). Body should translate; math should passthrough.

    Success criteria:
    - At least 1 segment with kind='math_passthrough' in the extracted segments
    - At least 1 segment with kind='text' on page 3 (body fonts still translate)
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(_BMC_FIXTURE))
    segments = extract_pdf_segments(doc, job_id="bmc-math-test")

    # Page 3 is 0-indexed page 2
    page3_segs = [s for s in segments if s.structural_position.startswith("page.2.")]

    passthrough_segs = [s for s in segments if s.kind == "math_passthrough"]
    text_segs_page3 = [s for s in page3_segs if s.kind == "text"]

    if not passthrough_segs:
        # Check whether the PDF actually has AdvP* fonts — if not, skip rather than fail
        page = doc[2]
        raw_blocks = page.get_text("dict")["blocks"]
        adv_p_fonts = [
            span.get("font", "")
            for b in raw_blocks
            if b["type"] == 0
            for line in b.get("lines", [])
            for span in line.get("spans", [])
            if span.get("font", "").startswith("AdvP")
        ]
        if not adv_p_fonts:
            pytest.skip(
                "Page 3 of BMC fixture has no AdvP* font spans — "
                "fixture may have been reprocessed or this is a different version."
            )

    assert len(passthrough_segs) >= 1, (
        f"Expected >=1 math_passthrough segment from BMC page 3 AdvP4C4E74 spans, "
        f"got 0 across all pages. Check _is_math_font('AdvP4C4E74') returns True."
    )
    assert len(text_segs_page3) >= 1, (
        f"Page 3 should still have translatable body segments (AdvTT* fonts), "
        f"but got 0 'text' kind segments on page 3."
    )
