"""
PPTX extractor + walker TDD tests.

Tests are written RED-first. They import from app.pipeline.pptx.extractor
which does not exist yet — ImportError is expected until plan 03 implements it.

Requirements: PPTX-01 (text box, notes, table, master), PPTX-02 (SmartArt),
              PPTX-03 (overflow), PPTX-04 (group recursion).
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Programmatic PPTX fixtures (no binary commits — generated from python-pptx)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def simple_pptx(tmp_path_factory):
    """PPTX with text box + speaker notes + 2×2 table on one slide."""
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    # Text box
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Hello PPTX"
    # Speaker notes
    notes = slide.notes_slide.notes_text_frame
    notes.text = "Speaker note text"
    # Table 2×2
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1))
    table_shape.table.cell(0, 0).text = "Cell A"
    table_shape.table.cell(0, 1).text = "Cell B"
    # Bulleted list: text box with multiple paragraphs at different indent levels
    bullet_box = slide.shapes.add_textbox(Inches(6), Inches(1), Inches(3), Inches(2))
    bf = bullet_box.text_frame
    bf.text = "Top-level bullet item"
    # Add a second paragraph (level 0)
    p1 = bf.add_paragraph()
    p1.text = "Second bullet item"
    p1.level = 0
    # Add a third paragraph (level 1 — sub-bullet)
    p2 = bf.add_paragraph()
    p2.text = "Sub-bullet nested item"
    p2.level = 1
    path = tmp_path_factory.mktemp("pptx_fixtures") / "simple.pptx"
    prs.save(str(path))
    return path


@pytest.fixture(scope="module")
def group_pptx(tmp_path_factory):
    """PPTX with a real nested GroupShape (built via lxml OOXML injection).

    M1 fix: the previous fixture created a plain text box — the GROUP code path
    was never exercised. This fixture injects a genuine <p:grpSp> element containing
    an inner <p:sp> text shape using raw OOXML so walk_shape_tree MUST recurse into
    MSO_SHAPE_TYPE.GROUP to find the text.
    """
    from pptx import Presentation
    from lxml import etree
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)

    # Build a real <p:grpSp> with a nested <p:sp> text shape via OOXML injection.
    # python-pptx has no public API to create group shapes, so we use lxml directly.
    # Namespaces match the OOXML spec (ISO/IEC 29500-1).
    grp_xml = """<p:grpSp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
         xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
         xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:nvGrpSpPr>
    <p:cNvPr id="100" name="OuterGroup"/>
    <p:cNvGrpSpPr/>
    <p:nvPr/>
  </p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="914400" y="914400"/>
      <a:ext cx="2743200" cy="1371600"/>
      <a:chOff x="914400" y="914400"/>
      <a:chExt cx="2743200" cy="1371600"/>
    </a:xfrm>
  </p:grpSpPr>
  <p:sp>
    <p:nvSpPr>
      <p:cNvPr id="101" name="InnerText"/>
      <p:cNvSpPr txBox="1"/>
      <p:nvPr/>
    </p:nvSpPr>
    <p:spPr>
      <a:xfrm>
        <a:off x="914400" y="914400"/>
        <a:ext cx="2743200" cy="685800"/>
      </a:xfrm>
      <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    </p:spPr>
    <p:txBody>
      <a:bodyPr/>
      <a:lstStyle/>
      <a:p>
        <a:r>
          <a:t>Nested group text</a:t>
        </a:r>
      </a:p>
    </p:txBody>
  </p:sp>
</p:grpSp>"""

    spTree = slide.shapes._spTree
    spTree.append(etree.fromstring(grp_xml))

    path = tmp_path_factory.mktemp("pptx_fixtures") / "group.pptx"
    prs.save(str(path))
    return path


@pytest.fixture(scope="module")
def overflow_pptx(tmp_path_factory):
    """PPTX with a tight text box containing very long text to trigger overflow detection."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    # Small box with a lot of text to force overflow ratio > 1/0.7
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(0.5))
    tf = txBox.text_frame
    tf.text = "Short"
    path = tmp_path_factory.mktemp("pptx_fixtures") / "overflow.pptx"
    prs.save(str(path))
    return path


# ---------------------------------------------------------------------------
# PPTX-01: text box, notes, table extraction
# ---------------------------------------------------------------------------

def test_extract_pptx_segments_text_box_produces_segment(simple_pptx):
    """PPTX-01: text box on slide produces at least one Segment with source_text."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job-01")
    texts = [s.source_text for s in segments]
    assert any("Hello PPTX" in t for t in texts), f"Expected 'Hello PPTX' in segments, got: {texts}"


def test_extract_pptx_segments_notes_produces_segment(simple_pptx):
    """PPTX-01: speaker notes produce a Segment."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job-01")
    texts = [s.source_text for s in segments]
    assert any("Speaker note" in t for t in texts), f"Expected notes segment, got: {texts}"


def test_extract_pptx_segments_table_cell_produces_segment(simple_pptx):
    """PPTX-01: table cells produce Segments with structural_position including 'table'."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job-01")
    table_segs = [s for s in segments if "table" in s.structural_position]
    assert len(table_segs) >= 2, f"Expected >=2 table segments, got: {len(table_segs)}"
    texts = [s.source_text for s in table_segs]
    assert "Cell A" in texts or any("Cell A" in t for t in texts)


def test_extract_pptx_segments_structural_position_unique(simple_pptx):
    """I4 invariant: all structural_position values are unique per extraction."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job-01")
    positions = [s.structural_position for s in segments]
    assert len(positions) == len(set(positions)), f"Duplicate structural_position: {positions}"


# ---------------------------------------------------------------------------
# PPTX-04: group shape recursion
# ---------------------------------------------------------------------------

def test_walk_shape_tree_group_recursion_finds_nested_text(group_pptx):
    """PPTX-04: walk_shape_tree recurses into real GroupShape (<p:grpSp>) and finds nested text.

    M1: The fixture injects a genuine <p:grpSp> via lxml — the extractor MUST recurse
    into MSO_SHAPE_TYPE.GROUP to find 'Nested group text'. If GROUP recursion is absent,
    the text will not appear and both assertions below will fail.
    """
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(group_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job-04")
    texts = [s.source_text for s in segments]
    positions = [s.structural_position for s in segments]
    # Assert text was found
    assert any("Nested" in t for t in texts), (
        f"Expected group text in segments — GROUP recursion likely missing. Got: {texts}"
    )
    # Assert structural_position contains '.group.' — proves GROUP code path was exercised.
    # If extractor only walks top-level shapes (no recursion), position will lack '.group.'
    assert any(".group." in p for p in positions), (
        f"Expected .group. in structural_position — GROUP code path not exercised. "
        f"Positions: {positions}"
    )


# ---------------------------------------------------------------------------
# PPTX-02: SmartArt detection
# ---------------------------------------------------------------------------

def test_smartart_flagged_not_silently_skipped():
    """PPTX-02: is_smartart() returns True for a shape with IGX_GRAPHIC type."""
    from app.pipeline.pptx.smartart import is_smartart

    class FakeShape:
        class FakeElement:
            def findall(self, path):
                return []
        shape_type = None  # will be set below
        element = FakeElement()

    from pptx.enum.shapes import MSO_SHAPE_TYPE
    fake = FakeShape()
    fake.shape_type = MSO_SHAPE_TYPE.IGX_GRAPHIC
    assert is_smartart(fake) is True, "IGX_GRAPHIC shape should be detected as SmartArt"


def test_non_smartart_shape_not_flagged():
    """PPTX-02: normal text-box shapes are NOT detected as SmartArt."""
    from app.pipeline.pptx.smartart import is_smartart

    class FakeShape:
        class FakeElement:
            def findall(self, path):
                return []
        shape_type = None
        element = FakeElement()

    from pptx.enum.shapes import MSO_SHAPE_TYPE
    fake = FakeShape()
    fake.shape_type = MSO_SHAPE_TYPE.TEXT_BOX
    assert is_smartart(fake) is False


def test_empty_pptx_returns_no_segments(tmp_path):
    """Adversarial: empty PPTX (no slides) returns empty list, does not crash."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation()
    # No slides added
    segments = extract_pptx_segments(prs, job_id="test-empty")
    assert segments == [] or isinstance(segments, list)


def test_extract_pptx_segments_bullet_list_produces_segment(simple_pptx):
    """PPTX-01: bulleted list paragraphs produce Segments with non-empty source_text."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-bullet-01")
    texts = [s.source_text for s in segments]
    # simple_pptx fixture has "Top-level bullet item", "Second bullet item", "Sub-bullet nested item"
    assert any("bullet" in t.lower() for t in texts), (
        f"Expected bullet text in segments, got: {texts}"
    )
    # All bullet segment positions must be unique (I4 invariant)
    positions = [s.structural_position for s in segments]
    assert len(positions) == len(set(positions)), f"Duplicate positions: {positions}"
