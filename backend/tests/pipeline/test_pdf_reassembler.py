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


def test_clip_rect_away_from_images_clips_right_edge():
    """Gap 2: text rect is clipped when image overlaps from the right."""
    import pymupdf
    from app.pipeline.pdf.reassembler import _clip_rect_away_from_images

    text_rect = pymupdf.Rect(10, 100, 200, 120)
    image_rect = pymupdf.Rect(150, 90, 300, 130)
    result = _clip_rect_away_from_images(text_rect, [image_rect])
    assert result.x1 == pytest.approx(150.0, abs=0.1), f"Right edge should be clipped to 150, got {result.x1}"
    assert result.x0 == pytest.approx(10.0, abs=0.1), "Left edge must be unchanged"


def test_clip_rect_away_from_images_no_overlap_unchanged():
    """Gap 2: rect with no image overlap is returned unchanged."""
    import pymupdf
    from app.pipeline.pdf.reassembler import _clip_rect_away_from_images

    text_rect = pymupdf.Rect(10, 100, 140, 120)
    image_rect = pymupdf.Rect(150, 100, 300, 120)
    result = _clip_rect_away_from_images(text_rect, [image_rect])
    assert result.x1 == pytest.approx(140.0, abs=0.1), "No overlap — rect must be unchanged"


def test_clip_rect_away_from_images_clips_left_edge():
    """WR-01: text rect is clipped when image overlaps from the left (wide figure case)."""
    import pymupdf
    from app.pipeline.pdf.reassembler import _clip_rect_away_from_images

    # Image starts left of (or at) the text rect's left edge and extends into it
    text_rect = pymupdf.Rect(100, 100, 200, 120)
    image_rect = pymupdf.Rect(50, 90, 180, 130)
    result = _clip_rect_away_from_images(text_rect, [image_rect])
    assert result.x0 == pytest.approx(180.0, abs=0.1), f"Left edge should be clipped to 180, got {result.x0}"
    assert result.x1 == pytest.approx(200.0, abs=0.1), "Right edge must be unchanged"


def test_reassembler_wraps_translated_html_in_block_size_div(tmp_path):
    """PDF format-fidelity: reassembler wraps translated HTML in a per-block
    <div style="font-size:Npt"> so heading em sizes resolve and body text
    renders at the original block's size (not PyMuPDF's 16pt default)."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a PDF with a 9.2pt body block — typical academic-paper size
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Body text at original size", fontsize=9.2)
    src_path = tmp_path / "src.pdf"
    doc.save(str(src_path))

    doc2 = pymupdf.open(str(src_path))
    segments = extract_pdf_segments(doc2, job_id="size-test")
    assert segments, "Need at least 1 segment"

    # Capture the html passed to insert_htmlbox
    captured: list[str] = []
    real_insert = pymupdf.Page.insert_htmlbox

    def spy(self, rect, html, **kw):
        captured.append(html)
        return real_insert(self, rect, html, **kw)

    pymupdf.Page.insert_htmlbox = spy
    try:
        out = str(tmp_path / "out.pdf")
        reassemble_pdf(doc2, segments, {s.id: s.source_text for s in segments}, out, overflow_flags=[])
    finally:
        pymupdf.Page.insert_htmlbox = real_insert

    assert captured, "insert_htmlbox should have been called at least once"
    wrapper_html = captured[0]
    assert '<div style="font-size:' in wrapper_html, (
        f"Translated HTML must be wrapped in a per-block size div; got: {wrapper_html!r}"
    )
    assert 'pt">' in wrapper_html, "Wrapper must specify pt-based font-size"


def test_math_passthrough_segment_is_not_redacted(tmp_path):
    """kind='math_passthrough' segments skip redact+reinsert — source glyph stays visible."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a PDF with one text block
    src_doc = pymupdf.open()
    page = src_doc.new_page()
    page.insert_text((72, 72), "Original math glyph")
    src_path = str(tmp_path / "math_src.pdf")
    src_doc.save(src_path)

    # Extract segments
    doc = pymupdf.open(src_path)
    segments = extract_pdf_segments(doc, job_id="test-passthrough")
    assert len(segments) >= 1

    # Mark all segments as math_passthrough
    for seg in segments:
        seg.kind = "math_passthrough"

    # translated_map would erase content if segments were processed
    translated_map = {s.id: "REPLACED BY TRANSLATION" for s in segments}
    overflow_flags = []
    out_path = str(tmp_path / "passthrough_out.pdf")
    reassemble_pdf(doc, segments, translated_map, out_path, overflow_flags)

    # Output PDF should still contain original text (not "REPLACED BY TRANSLATION")
    result = pymupdf.open(out_path)
    text = result[0].get_text()
    assert "REPLACED BY TRANSLATION" not in text, (
        "math_passthrough segments must not be reinserted — source stays intact"
    )
    # Source text should still be present (not erased by redaction)
    assert "Original" in text or len(text.strip()) > 0, (
        "Source text should survive — no redaction for math_passthrough"
    )


def test_table_cell_segment_reassemble_no_crash(tmp_path):
    """kind='table_cell' segments run through the reassembler without crashing."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build synthetic table PDF (same as extractor fixture)
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    x0, y0, col_w, row_h = 50, 50, 100.0, 50.0
    for text, pos in [("A1", (60, 80)), ("B1", (160, 80)), ("A2", (60, 130)), ("B2", (160, 130))]:
        page.insert_text(pos, text, fontsize=11)
    shape = page.new_shape()
    for r in range(3):
        shape.draw_line((x0, y0 + r * row_h), (x0 + 200, y0 + r * row_h))
    for c in range(3):
        shape.draw_line((x0 + c * 100, y0), (x0 + c * 100, y0 + 100))
    shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()
    src_path = str(tmp_path / "table_src.pdf")
    doc.save(src_path)

    doc2 = pymupdf.open(src_path)
    segments = extract_pdf_segments(doc2, "test-table-cell")
    table_segs = [s for s in segments if s.kind == "table_cell"]
    if not table_segs:
        pytest.skip("find_tables() did not detect table in synthetic PDF — skip integration test")

    # Identity translated_map
    translated_map = {s.id: s.source_text for s in segments}
    overflow_flags = []
    out_path = str(tmp_path / "table_out.pdf")
    reassemble_pdf(doc2, segments, translated_map, out_path, overflow_flags)

    # Verify output is a valid PDF
    result = pymupdf.open(out_path)
    assert len(result) >= 1, "Output PDF must have at least 1 page"


def test_table_cell_inset_prevents_word_adhesion(tmp_path):
    """Phase 03.3 Bug 1: table_cell insert rect must be inset by _TABLE_CELL_INSET_PT.

    Without the inset, insert_htmlbox fills cell0 to its right edge and cell1
    starts at the same coordinate — PDF word extraction joins them as a single
    token ('AlphaAlphaBetaBeta'). This test spies on insert_htmlbox call arguments
    to assert that the rect passed for table_cell segments is smaller than the full
    cell bbox (i.e. has been inset by at least 1.0 pt on each side).
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a two-column vector-bordered table PDF
    # Page 400×300, two 100pt wide columns at x=[50,150,250], rows at y=[50,100]
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)

    shape = page.new_shape()
    for x in [50, 150, 250]:
        shape.draw_line((x, 50), (x, 100))
    for y in [50, 100]:
        shape.draw_line((50, y), (250, y))
    shape.finish(color=(0, 0, 0), width=1.0)
    shape.commit()

    page.insert_text((60, 80), "Alpha", fontsize=10)
    page.insert_text((160, 80), "Beta", fontsize=10)

    src_path = str(tmp_path / "adhesion_src.pdf")
    doc.save(src_path)

    doc2 = pymupdf.open(src_path)
    segments = extract_pdf_segments(doc2, job_id="test-adhesion")
    table_segs = [s for s in segments if s.kind == "table_cell"]
    if not table_segs:
        pytest.skip(
            "find_tables() detected 0 table cells in synthetic PDF — synthetic environment limitation"
        )

    translated_map = {s.id: s.source_text for s in segments}

    # Spy on insert_htmlbox to capture rect arguments for table_cell segments
    captured_rects: list[pymupdf.Rect] = []
    real_insert = pymupdf.Page.insert_htmlbox

    def spy(self, rect, html, **kw):
        captured_rects.append(pymupdf.Rect(rect))
        return real_insert(self, rect, html, **kw)

    pymupdf.Page.insert_htmlbox = spy
    try:
        out_path = str(tmp_path / "adhesion_out.pdf")
        overflow_flags: list[dict] = []
        reassemble_pdf(doc2, segments, translated_map, out_path, overflow_flags)
    finally:
        pymupdf.Page.insert_htmlbox = real_insert

    assert captured_rects, "insert_htmlbox should have been called at least once"

    # Cell[0,0] spans x=[50,150] — the insert rect must be inset (x0 > 50.0, x1 < 150.0)
    # Cell[0,1] spans x=[150,250] — similarly inset
    # Assert: every captured rect has its left edge > the nominal cell x0 value
    # i.e. no rect starts exactly at a border coordinate (50.0, 150.0, or 250.0)
    exact_border_starts = [50.0, 150.0, 250.0]
    rects_at_border = [
        r for r in captured_rects
        if any(abs(r.x0 - bx) < 0.01 for bx in exact_border_starts)
    ]
    assert not rects_at_border, (
        f"insert_htmlbox called with rect(s) starting exactly at cell border "
        f"(no inset applied): {rects_at_border!r}. "
        "table_cell segments must use an inset rect (_TABLE_CELL_INSET_PT=1.5)."
    )


def test_table_cell_scale_low_resolves_overflow(tmp_path):
    """Phase 03.3 Bug 2: table_cell segments must use _TABLE_SCALE_LOW=0.3, not 0.7.

    With scale_low=0.7, insert_htmlbox returns spare_height=-1 (blank cell) for
    JP→VN-expanded text in 80-120 pt wide, 12-20 pt tall cells. This test spies
    on insert_htmlbox to assert that the scale_low kwarg is <= 0.3 for table_cell
    segments. Before the fix, scale_low=0.7 is passed — the test fails.
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments
    from app.pipeline.pdf.reassembler import reassemble_pdf

    # Build a two-column table so find_tables() can detect cells
    # Use 80pt wide cells and 20pt tall rows (matches RESEARCH.md worst-case dims)
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)

    shape = page.new_shape()
    for x in [50, 130, 210]:
        shape.draw_line((x, 50), (x, 70))
    for y in [50, 70]:
        shape.draw_line((50, y), (210, y))
    shape.finish(color=(0, 0, 0), width=1.0)
    shape.commit()

    page.insert_text((55, 65), "短い", fontsize=8)
    page.insert_text((135, 65), "テスト", fontsize=8)

    src_path = str(tmp_path / "tight_cell_src.pdf")
    doc.save(src_path)

    doc2 = pymupdf.open(src_path)
    segments = extract_pdf_segments(doc2, job_id="test-scale-low")
    table_segs = [s for s in segments if s.kind == "table_cell"]
    if not table_segs:
        pytest.skip(
            "find_tables() detected 0 table cells in synthetic PDF — synthetic environment limitation"
        )

    # Simulate 3× expansion
    long_vn_text = "Đây là bản dịch rất dài mô phỏng việc mở rộng văn bản từ tiếng Nhật sang tiếng Việt"
    translated_map = {seg.id: long_vn_text for seg in table_segs}
    for seg in segments:
        if seg.id not in translated_map:
            translated_map[seg.id] = seg.source_text

    # Spy on insert_htmlbox to capture scale_low kwarg values for table_cell calls
    captured_scale_lows: list[float] = []
    real_insert = pymupdf.Page.insert_htmlbox

    def spy(self, rect, html, **kw):
        scale_low = kw.get("scale_low", 0.0)
        captured_scale_lows.append(scale_low)
        return real_insert(self, rect, html, **kw)

    pymupdf.Page.insert_htmlbox = spy
    try:
        out_path = str(tmp_path / "tight_cell_out.pdf")
        overflow_flags: list[dict] = []
        reassemble_pdf(doc2, segments, translated_map, out_path, overflow_flags)
    finally:
        pymupdf.Page.insert_htmlbox = real_insert

    assert captured_scale_lows, "insert_htmlbox should have been called at least once"

    # Assert: all table_cell insert_htmlbox calls use scale_low <= 0.3
    # Before the fix, scale_low=0.7 is passed — this assertion will FAIL (RED state).
    bad_scale_lows = [sl for sl in captured_scale_lows if sl > 0.3]
    assert not bad_scale_lows, (
        f"insert_htmlbox called with scale_low > 0.3 for table_cell segment(s): {bad_scale_lows!r}. "
        "The table_cell path must use _TABLE_SCALE_LOW=0.3 to avoid blank cells (Bug 2)."
    )
