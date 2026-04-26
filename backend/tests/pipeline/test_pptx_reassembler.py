"""
PPTX reassembler TDD tests.

Tests PPTX-03 (overflow detection + auto-fit) and LAYOUT-03 (auto-adjusted metadata).
RED until plan 03 implements pipeline/pptx/reassembler.py.
"""
from __future__ import annotations

import pytest


@pytest.fixture(scope="module")
def simple_pptx(tmp_path_factory):
    """PPTX with one slide containing a text box with short source text."""
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    tf = txBox.text_frame
    tf.text = "Short text"
    # Add bulleted paragraphs to exercise run-merge write-back on bullet paragraphs
    p1 = tf.add_paragraph()
    p1.text = "Bullet item one"
    p1.level = 0
    p2 = tf.add_paragraph()
    p2.text = "Sub-bullet item"
    p2.level = 1
    path = tmp_path_factory.mktemp("pptx_reassembler_fixtures") / "simple.pptx"
    prs.save(str(path))
    return path


def test_reassemble_pptx_identity_round_trip(simple_pptx):
    """PPTX-01 round-trip: identity translation preserves all text."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    from app.pipeline.pptx.reassembler import reassemble_pptx
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-roundtrip")
    translated_map = {s.id: s.source_text for s in segments}  # identity
    # reassemble_pptx returns tuple (Presentation, list[dict])
    result, overflow_results = reassemble_pptx(prs, segments, translated_map)
    assert isinstance(overflow_results, list), "overflow_results must be a list"
    # Verify text still present
    texts_after = [
        para.text
        for slide in result.slides
        for shape in slide.shapes
        if shape.has_text_frame
        for para in shape.text_frame.paragraphs
    ]
    assert any(t.strip() for t in texts_after), "Round-trip should preserve text"


def test_overflow_detection_flags_segment(tmp_path):
    """PPTX-03: when translated text expands by >43% (shrink < 0.7), overflow is detected."""
    from pptx import Presentation
    from pptx.util import Inches
    from app.pipeline.pptx.reassembler import detect_pptx_overflow

    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(0.5))
    txBox.text_frame.text = "Hi"

    # Simulate: source "Hi" (2 chars), translated "Very very very long translation" (31 chars)
    source_text = "Hi"
    translated_text = "Very very very long translation text that overflows the box"
    result = detect_pptx_overflow(txBox, source_text, translated_text)
    assert result["overflow"] is True, f"Expected overflow=True, got: {result}"
    assert result["char_ratio"] > 1.0 / 0.7


def test_autofit_applied_when_shrink_gte_0_7(tmp_path):
    """PPTX-03 + LAYOUT-03: when shrink >= 0.7, auto-fit is applied and auto_adjusted=True."""
    from pptx import Presentation
    from pptx.util import Inches
    from app.pipeline.pptx.reassembler import detect_pptx_overflow

    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Hello world this is normal text"

    # 20% expansion: shrink = 1/1.2 = 0.83 >= 0.7 → auto-fit should apply
    source_text = "Hello world this is normal text"  # 30 chars
    translated_text = "Hola mundo esto es texto normal aqui"  # 36 chars (20% expansion)
    result = detect_pptx_overflow(txBox, source_text, translated_text)
    assert result["overflow"] is False, f"Expected no overflow, got: {result}"
    assert result["auto_adjusted"] is True, f"Expected auto_adjusted=True, got: {result}"


def test_smartart_write_back_skipped(simple_pptx):
    """PPTX-02: SmartArt segments are not written back during reassembly."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    from app.pipeline.pptx.reassembler import reassemble_pptx
    from app.pipeline.segment import Segment

    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-smartart-wb")
    # Inject a fake smartart segment — should not cause write-back crash
    fake_smartart_seg = Segment.from_text(
        source_text="SmartArt text",
        structural_position="slide.0.shape.99.smartart",
        seq_in_job=999,
    )
    all_segs = segments + [fake_smartart_seg]
    translated_map = {s.id: s.source_text for s in all_segs}
    # Should not raise — smartart write-back is skipped silently
    result, overflow_results = reassemble_pptx(prs, all_segs, translated_map)
    assert result is not None
    assert isinstance(overflow_results, list), "overflow_results must be a list"


def test_autofit_skipped_for_auto_height_shape(tmp_path):
    """Gap 1: shapes with height=0 (auto-height) must not apply TEXT_TO_FIT_SHAPE."""
    from pptx import Presentation
    from pptx.util import Inches
    from app.pipeline.pptx.reassembler import detect_pptx_overflow
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(0))
    # Simulate auto-height: height set to 0
    txBox._element.spPr.xfrm.ext.cy = 0
    source = "Hello world"
    translated = "Xin chào thế giới hôm nay"  # ~20% longer, shrink=0.83 >= 0.7
    result = detect_pptx_overflow(txBox, source, translated)
    assert result["overflow"] is False
    assert result["auto_adjusted"] is False, "Auto-height shapes must not apply auto-fit"


def test_paragraph_dominant_font_pt_returns_max_run_size():
    """_paragraph_dominant_font_pt returns max run font size in pts, defaults 18pt."""
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from app.pipeline.pptx.reassembler import _paragraph_dominant_font_pt
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    para = txBox.text_frame.paragraphs[0]
    run = para.add_run()
    run.text = "Heading text"
    run.font.size = Pt(24)
    result = _paragraph_dominant_font_pt(para)
    assert abs(result - 24.0) < 0.1, f"Expected 24pt, got {result}"


def test_reassemble_pptx_bullet_paragraph_preserves_bullet_format(simple_pptx, tmp_path):
    """PPTX-01: bullet paragraph level is preserved through run-merge write-back."""
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    from app.pipeline.pptx.reassembler import reassemble_pptx

    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-bullet-roundtrip")

    # Identity translation
    translated_map = {s.id: s.source_text for s in segments}
    # reassemble_pptx returns tuple (Presentation, list[dict])
    result_prs, overflow_results = reassemble_pptx(prs, segments, translated_map)
    assert isinstance(overflow_results, list), "overflow_results must be a list"

    # Verify bullet paragraph levels are preserved in output
    output_path = str(tmp_path / "bullet_rt.pptx")
    result_prs.save(output_path)
    reopened = Presentation(output_path)

    levels_found = []
    for slide in reopened.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        levels_found.append(para.level)

    # simple_pptx has paragraphs at level 0 and level 1
    assert 0 in levels_found, f"Expected level 0 paragraph, found levels: {levels_found}"
    assert 1 in levels_found, f"Expected level 1 (sub-bullet) paragraph, found levels: {levels_found}"
