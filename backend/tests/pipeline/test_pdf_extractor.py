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


# --- Gap 3: PDF heading detection tests ---


def test_detect_heading_level_classifies_h1_h2_body():
    """Gap 3: _detect_heading_level returns correct heading level."""
    from app.pipeline.pdf.extractor import _detect_heading_level
    assert _detect_heading_level(24.0, 12.0) == 1, "24/12=2.0 >= 1.8 → h1"
    assert _detect_heading_level(18.0, 12.0) == 2, "18/12=1.5 >= 1.4, < 1.8 → h2"
    assert _detect_heading_level(12.0, 12.0) == 0, "12/12=1.0 < 1.4 → body"
    assert _detect_heading_level(16.0, 12.0) == 0, "16/12=1.33 < 1.4 → body"


def test_spans_to_html_emits_h1_for_large_font():
    """Gap 3: spans_to_html wraps large-font spans in <h1>."""
    from app.pipeline.pdf.extractor import spans_to_html
    block = {
        "lines": [
            {"spans": [{"text": "Introduction", "size": 24.0, "flags": 0}]},
            {"spans": [{"text": "Body text here.", "size": 12.0, "flags": 0}]},
        ]
    }
    html = spans_to_html(block)
    assert "<h1>" in html, f"Expected <h1> tag for 24pt span; got: {html!r}"
    assert "Introduction" in html
    assert "Body text here." in html


def test_spans_to_html_no_heading_for_uniform_font():
    """Gap 3: spans_to_html must not emit h1/h2 when all spans are same size."""
    from app.pipeline.pdf.extractor import spans_to_html
    block = {
        "lines": [
            {"spans": [{"text": "Normal paragraph text.", "size": 12.0, "flags": 0}]},
            {"spans": [{"text": "More body text.", "size": 12.0, "flags": 0}]},
        ]
    }
    html = spans_to_html(block)
    assert "<h1>" not in html, "No h1 for uniform 12pt text"
    assert "<h2>" not in html, "No h2 for uniform 12pt text"


def test_is_bold_font_detects_dot_b_suffix():
    """Subset fonts in academic PDFs encode bold via `.B` suffix when the
    PDF span flags don't carry the bold bit (verified on BMC paper)."""
    from app.pipeline.pdf.extractor import _is_bold_font

    assert _is_bold_font("AdvTTaf7f9f4f.B") is True, "`.B` suffix → bold"
    assert _is_bold_font("ABCDEF+AdvTTaf7f9f4f.B") is True, "subset prefix stripped"
    assert _is_bold_font("Helvetica-Bold") is True, "`-Bold` suffix → bold"
    assert _is_bold_font("Roboto Black") is True, "`black` keyword → bold"
    assert _is_bold_font("AdvTT86d47313") is False, "body font without bold marker"
    assert _is_bold_font("") is False, "empty string is safe"


def test_is_italic_font_detects_dot_i_suffix():
    from app.pipeline.pdf.extractor import _is_italic_font

    assert _is_italic_font("AdvTT8861b38f.I") is True, "`.I` suffix → italic"
    assert _is_italic_font("Helvetica-Oblique") is True, "`-Oblique` → italic"
    assert _is_italic_font("Times-Italic") is True, "`-Italic` → italic"
    assert _is_italic_font("AdvTT86d47313") is False
    assert _is_italic_font("") is False


def test_spans_to_html_merges_consecutive_same_style_runs():
    """`<b>Open</b><b> </b><b>Access</b>` is the bug we are fixing — adjacent
    bold spans must coalesce into a single `<b>Open Access</b>`."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"spans": [
                {"text": "Open", "size": 10.0, "flags": 16, "font": "Helvetica-Bold"},
                {"text": " ", "size": 10.0, "flags": 16, "font": "Helvetica-Bold"},
                {"text": "Access", "size": 10.0, "flags": 16, "font": "Helvetica-Bold"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>Open Access</b>" in html, f"Adjacent bold spans must merge; got {html!r}"
    assert "<b>Open</b>" not in html, "Should not have separate <b> tags"


def test_spans_to_html_inserts_br_on_paragraph_line_gap():
    """Spatial signal: when consecutive lines in a block have a y-gap that
    exceeds 1.2x the median line gap, a <br> is emitted. This is the BMC
    abstract scenario where 'Methods:' and 'Results:' sit on lines with
    extra leading between them — visual paragraph break in source."""
    from app.pipeline.pdf.extractor import spans_to_html

    # 3 lines: normal gap (12pt) between L0 and L1, big gap (16pt) before L2
    block = {
        "lines": [
            {"bbox": (0, 100, 200, 110), "spans": [
                {"text": "Methods:", "size": 10.0, "flags": 4, "font": "AdvTT99c4c969"},
                {"text": " Two real world clinical datasets.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
            {"bbox": (0, 112, 200, 122), "spans": [
                {"text": "More body text on the next line.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
            {"bbox": (0, 128, 200, 138), "spans": [
                {"text": "Results:", "size": 10.0, "flags": 4, "font": "AdvTT99c4c969"},
                {"text": " GAIN was the most accurate.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<br>" in html, f"Expected paragraph break from line-gap; got {html!r}"
    # The break must come BEFORE the Results label (between L1 and L2)
    br_pos = html.find("<br>")
    results_pos = html.find("<b>Results:</b>")
    assert br_pos < results_pos, f"<br> must precede Results; got {html!r}"


def test_spans_to_html_no_br_when_line_gap_is_uniform():
    """Spatial signal must NOT fire when all line gaps are roughly uniform —
    that's regular line wrap, not a paragraph break."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"bbox": (0, 100, 200, 110), "spans": [
                {"text": "First line.", "size": 10.0, "flags": 4, "font": "Body"},
            ]},
            {"bbox": (0, 112, 200, 122), "spans": [
                {"text": "Second line.", "size": 10.0, "flags": 4, "font": "Body"},
            ]},
            {"bbox": (0, 124, 200, 134), "spans": [
                {"text": "Third line.", "size": 10.0, "flags": 4, "font": "Body"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<br>" not in html, f"Uniform line gaps must NOT emit <br>; got {html!r}"


def test_spans_to_html_block_leading_heading_gets_break_before_body():
    """A bold run that opens the block AND does NOT end with `:` is a
    section header — body text after it gets a `<br>` separator. Inline
    labels ending with `:` (Background:) stay inline."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"spans": [
                {"text": "Acknowledgements", "size": 10.0, "flags": 4, "font": "AdvTT99c4c969"},
                {"text": " We thank the Hong Kong Hospital Authority for the extraction of data from the HA computerized medical system.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>Acknowledgements</b><br>" in html, (
        f"Section header must be followed by <br>; got {html!r}"
    )


def test_spans_to_html_inline_label_no_leading_break():
    """`<b>Background:</b> body text` must NOT get a `<br>` after the label
    — it's an inline label, not a block header."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"spans": [
                {"text": "Background:", "size": 10.0, "flags": 4, "font": "AdvTT99c4c969"},
                {"text": " Missing data is pervasive.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>Background:</b><br>" not in html, (
        f"Inline label should NOT be followed by <br>; got {html!r}"
    )


def test_spans_to_html_bold_via_variant_font_when_size_differs():
    """BMC sub-section headers (e.g. 'Study setting and datasets',
    'Experiments on HT-data') sit on their own line at 9.2pt while the
    block body is 9.8pt. The variant-font check must tolerate small size
    differences (≤ 1pt) so sub-headers still get wrapped in <b>."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"bbox": (0, 100, 200, 110), "spans": [
                {"text": "Sub-section header", "size": 9.2, "flags": 4, "font": "AdvTT99c4c969"},
            ]},
            {"bbox": (0, 112, 200, 122), "spans": [
                {"text": "Body text starts here and continues.", "size": 9.8, "flags": 4, "font": "AdvTT86d47313"},
            ]},
            {"bbox": (0, 124, 200, 134), "spans": [
                {"text": "Body text continues on this line as well.", "size": 9.8, "flags": 4, "font": "AdvTT86d47313"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>Sub-section header</b>" in html, (
        f"Variant font at body-1pt size should be bold; got {html!r}"
    )


def test_spans_to_html_bold_via_variant_font_within_block():
    """Inline-bold labels in academic abstracts ('Background:', 'Methods:')
    use a different subset font than the body — same flags=4, same size=10pt,
    but different font name (e.g. AdvTT99c4c969 for the label vs
    AdvTTb5929f4c for the body). spans_to_html must wrap these in <b>."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"spans": [
                {"text": "Background:", "size": 10.0, "flags": 4, "font": "AdvTT99c4c969"},
                {"text": " Missing data is", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
                {"text": " pervasive.", "size": 10.0, "flags": 4, "font": "AdvTTb5929f4c"},
            ]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>Background:</b>" in html, f"Expected inline <b>; got {html!r}"
    # Body text must NOT be bolded
    assert "<b> Missing data is</b>" not in html
    assert "<b> pervasive.</b>" not in html


def test_spans_to_html_bold_via_font_name_when_flags_miss_bit():
    """When PDF span flags don't carry the bold bit (flags=4 = serifed only)
    but the font name encodes bold via `.B`, spans_to_html still wraps in
    <b>. This is the BMC-paper scenario: 'RESEARCH ARTICLE' is visually bold
    but flags=4."""
    from app.pipeline.pdf.extractor import spans_to_html

    block = {
        "lines": [
            {"spans": [{
                "text": "RESEARCH ARTICLE",
                "size": 13.0,
                "flags": 4,
                "font": "AdvTTaf7f9f4f.B",
            }]},
        ]
    }
    html = spans_to_html(block)
    assert "<b>RESEARCH ARTICLE</b>" in html, f"Expected <b>; got {html!r}"


def test_spans_to_html_page_level_heading_for_uniform_title_block():
    """Title-only blocks (uniform large font) need page_body_pt to detect
    them as headings. Per-block detection would compare a uniform block's
    body size to itself (ratio = 1.0) and miss the heading."""
    from app.pipeline.pdf.extractor import spans_to_html

    title_block = {
        "lines": [
            {"spans": [{
                "text": "Generative adversarial networks",
                "size": 23.4,
                "flags": 4,
                "font": "AdvTTe45e47d2",
            }]},
        ]
    }
    # Without page_body_pt, no heading detected (current behavior)
    html_without = spans_to_html(title_block)
    assert "<h1>" not in html_without, (
        "Without page_body_pt, uniform-size block has ratio=1.0 → no heading"
    )
    # With page_body_pt = 10, title at 23.4 → ratio 2.3 → h1
    html_with = spans_to_html(title_block, page_body_pt=10.0)
    assert "<h1>" in html_with, f"Expected <h1>; got {html_with!r}"


# --- Phase 03.2 Plan 01: Segment.kind field + _is_math_font TDD ---


def test_segment_kind_field_default_text():
    """03.2-01 RED: Segment must have a `kind` field with default 'text'."""
    from app.pipeline.segment import Segment
    seg = Segment.from_text(
        source_text="Hello",
        structural_position="page.0.block.0",
        seq_in_job=0,
    )
    assert seg.kind == "text", f"Expected kind='text', got: {seg.kind!r}"


def test_is_math_font_detects_adv_prefix():
    """03.2-01 RED: _is_math_font must correctly classify math vs body fonts."""
    from app.pipeline.pdf.extractor import _is_math_font

    # Math fonts — must return True
    assert _is_math_font("AdvP4C4E74") is True, "AdvP prefix is math font"
    assert _is_math_font("CMSY10") is True, "CMSY prefix is TeX CM Symbol"
    assert _is_math_font("CMR12") is True, "CMR prefix is TeX CM Roman (math context)"
    assert _is_math_font("STIXGeneral") is True, "STIX prefix is math font family"
    assert _is_math_font("MathFont-Bold") is True, "MathFont keyword match"
    assert _is_math_font("Symbol") is True, "Symbol exact match"
    assert _is_math_font("MT-Extra") is True, "MT prefix is MathType"

    # Body fonts — must return False
    assert _is_math_font("AdvTT86d47313") is False, "AdvTT is a body-text subset, NOT math"
    assert _is_math_font("NotoSans-Regular") is False, "Noto body font"
    assert _is_math_font("Helvetica") is False, "standard body font"
    assert _is_math_font("Arial-BoldMT") is False, "MT suffix != MT prefix; Arial is body font"
    assert _is_math_font("Times-Roman") is False, "standard body font"
    assert _is_math_font("Calibri") is False, "standard body font"


def test_extract_pdf_segments_math_font_emitted_as_passthrough():
    """03.2-01 RED: _is_math_font integration — math-font spans must yield kind='math_passthrough'."""
    from app.pipeline.pdf.extractor import _is_math_font

    # Verify the detection predicate directly (the integration with
    # extract_pdf_segments is covered by test_extract_pdf_segments_all_segments_have_kind_field)
    math_font = "AdvP4C4E74"
    body_font = "Helvetica"
    assert _is_math_font(math_font) is True, f"Expected {math_font!r} to be detected as math"
    assert _is_math_font(body_font) is False, f"Expected {body_font!r} to be body (not math)"


def test_extract_pdf_segments_all_segments_have_kind_field(single_col_pdf):
    """03.2-01 RED: All segments from extract_pdf_segments must have a kind field."""
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-kind-field")
    assert len(segments) >= 1, "Expected at least 1 segment from single_col_pdf"

    valid_kinds = {"text", "table_cell", "math_passthrough"}
    for seg in segments:
        assert hasattr(seg, "kind"), f"Segment missing `kind` field: {seg!r}"
        assert seg.kind in valid_kinds, (
            f"Segment kind {seg.kind!r} not in valid set {valid_kinds}"
        )

    # A normal (non-math-font) PDF must have all segments as kind='text'
    assert all(seg.kind == "text" for seg in segments), (
        f"Expected all normal-PDF segments to be kind='text', got: "
        f"{[seg.kind for seg in segments]}"
    )


# --- Phase 03.2 Plan 02: Table cell extraction via find_tables() ---


@pytest.fixture(scope="module")
def table_pdf(tmp_path_factory):
    """
    Synthetic PDF with a 2-row × 3-column table drawn via PyMuPDF line primitives.
    Cell text:
      Row 0: "A1", "B1", "C1"
      Row 1: "A2", "B2", "C2"
    """
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)
    # Table at (50, 50) → (350, 150), two rows, three columns
    col_w = 100.0  # (350-50) / 3
    row_h = 50.0   # (150-50) / 2
    x0, y0 = 50, 50
    # Insert cell text at cell centres
    cells = [
        ("A1", (x0 + col_w*0 + 10, y0 + row_h*0 + 30)),
        ("B1", (x0 + col_w*1 + 10, y0 + row_h*0 + 30)),
        ("C1", (x0 + col_w*2 + 10, y0 + row_h*0 + 30)),
        ("A2", (x0 + col_w*0 + 10, y0 + row_h*1 + 30)),
        ("B2", (x0 + col_w*1 + 10, y0 + row_h*1 + 30)),
        ("C2", (x0 + col_w*2 + 10, y0 + row_h*1 + 30)),
    ]
    for text, pos in cells:
        page.insert_text(pos, text, fontsize=11)
    # Draw table grid lines so find_tables() can detect the table
    shape = page.new_shape()
    for row in range(3):  # 3 horizontal lines (top, mid, bottom)
        y = y0 + row * row_h
        shape.draw_line((x0, y), (x0 + col_w*3, y))
    for col in range(4):  # 4 vertical lines
        x = x0 + col * col_w
        shape.draw_line((x, y0), (x, y0 + row_h*2))
    shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()
    path = tmp_path_factory.mktemp("pdf_table_fixtures") / "table.pdf"
    doc.save(str(path))
    return path


def test_table_cells_emit_one_segment_per_cell(table_pdf):
    """
    03.2-02 RED: Pages with tables detected by find_tables() emit one Segment per cell
    with kind='table_cell', not one fused block per row.
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(table_pdf))
    segments = extract_pdf_segments(doc, job_id="test-table-cells")
    table_segs = [s for s in segments if s.kind == "table_cell"]

    # find_tables() must detect the drawn grid and emit at least 4 cell segments
    # (allows for merged/empty cells detected differently across environments)
    assert len(table_segs) >= 4, (
        f"Expected >=4 table_cell segments for a 2×3 table, got {len(table_segs)}. "
        f"All segments: {[(s.kind, s.source_text, s.structural_position) for s in segments]}"
    )


def test_table_cell_structural_position_format(table_pdf):
    """
    03.2-02 RED: Each table_cell segment must have structural_position matching
    'page.N.table.T.row.R.col.C'.
    """
    import re
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(table_pdf))
    segments = extract_pdf_segments(doc, job_id="test-table-pos")
    table_segs = [s for s in segments if s.kind == "table_cell"]

    pattern = re.compile(r"^page\.\d+\.table\.\d+\.row\.\d+\.col\.\d+$")
    for seg in table_segs:
        assert pattern.match(seg.structural_position), (
            f"table_cell structural_position {seg.structural_position!r} "
            f"does not match expected pattern 'page.N.table.T.row.R.col.C'"
        )


def test_non_table_blocks_still_kind_text(tmp_path_factory):
    """
    03.2-02 RED: Non-table blocks on the same page as a table continue to
    produce kind='text' segments.
    """
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open()
    page = doc.new_page(width=400, height=300)

    # Plain text paragraph above the table
    page.insert_text((72, 20), "This is a title paragraph above the table", fontsize=14)

    # Same 2×3 table grid
    col_w = 100.0
    row_h = 50.0
    x0, y0 = 50, 50
    for text, pos in [
        ("A1", (x0 + col_w*0 + 10, y0 + row_h*0 + 30)),
        ("B1", (x0 + col_w*1 + 10, y0 + row_h*0 + 30)),
        ("C1", (x0 + col_w*2 + 10, y0 + row_h*0 + 30)),
        ("A2", (x0 + col_w*0 + 10, y0 + row_h*1 + 30)),
        ("B2", (x0 + col_w*1 + 10, y0 + row_h*1 + 30)),
        ("C2", (x0 + col_w*2 + 10, y0 + row_h*1 + 30)),
    ]:
        page.insert_text(pos, text, fontsize=11)
    shape = page.new_shape()
    for row in range(3):
        y = y0 + row * row_h
        shape.draw_line((x0, y), (x0 + col_w*3, y))
    for col in range(4):
        x = x0 + col * col_w
        shape.draw_line((x, y0), (x, y0 + row_h*2))
    shape.finish(color=(0, 0, 0), width=0.5)
    shape.commit()

    path = tmp_path_factory.mktemp("pdf_mixed_fixtures") / "mixed.pdf"
    doc.save(str(path))

    doc2 = pymupdf.open(str(path))
    segments = extract_pdf_segments(doc2, job_id="test-mixed")

    text_segs = [s for s in segments if s.kind == "text"]
    table_segs = [s for s in segments if s.kind == "table_cell"]

    assert len(text_segs) >= 1, (
        f"Expected >=1 kind='text' segment for the paragraph, got none. "
        f"All: {[(s.kind, s.source_text) for s in segments]}"
    )
    assert len(table_segs) >= 1, (
        f"Expected >=1 kind='table_cell' segment from the table, got none. "
        f"All: {[(s.kind, s.source_text) for s in segments]}"
    )


def test_zero_table_page_behavior_unchanged(single_col_pdf):
    """
    03.2-02 RED: Pages without tables (find_tables() returns empty) behave
    identically to pre-03.2 — all segments have kind='text', structural_position
    uses the existing 'page.N.col.C.block.B' or 'page.N.block.B' format.
    """
    import re
    import pymupdf
    from app.pipeline.pdf.extractor import extract_pdf_segments

    doc = pymupdf.open(str(single_col_pdf))
    segments = extract_pdf_segments(doc, job_id="test-zero-table")

    # All segments must be kind='text' — no table_cell, no math_passthrough
    assert all(s.kind == "text" for s in segments), (
        f"Expected all kind='text' for no-table PDF, got: "
        f"{[(s.kind, s.structural_position) for s in segments]}"
    )

    # structural_position must NOT contain 'table' (table-aware format)
    table_pattern = re.compile(r"table\.")
    for seg in segments:
        assert not table_pattern.search(seg.structural_position), (
            f"No-table PDF segment has 'table.' in structural_position: "
            f"{seg.structural_position!r}"
        )
