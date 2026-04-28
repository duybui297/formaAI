"""Unit tests: Segment tree → Markdown helper (D-04-33)."""
from __future__ import annotations

import pytest

from app.pipeline.segment import Segment
from app.pipeline.scanned_pdf.segment_to_md import segments_to_markdown


def _seg(
    text: str,
    label: str = "text",
    seq: int = 0,
    kind: str = "ocr_text",
    translated: str | None = None,
    edited: str | None = None,
) -> Segment:
    """Build a minimal Segment for segment_to_md tests."""
    return Segment.from_text(
        source_text=text,
        structural_position=f"page.0.region.{seq}",
        seq_in_job=seq,
        kind=kind,
        region_label=label,
        translated_text=translated,
        edited_source_text=edited,
    )


@pytest.mark.unit
def test_doc_title_renders_as_h1():
    """region_label='doc_title' emits '# text' heading."""
    seg = _seg("My Document Title", label="doc_title", seq=0)
    md = segments_to_markdown([seg])
    assert md.startswith("# My Document Title"), f"Expected H1, got: {md!r}"


@pytest.mark.unit
def test_paragraph_title_renders_as_h2():
    """region_label='paragraph_title' emits '## text' heading."""
    seg = _seg("Section Header", label="paragraph_title", seq=0)
    md = segments_to_markdown([seg])
    assert md.startswith("## Section Header"), f"Expected H2, got: {md!r}"


@pytest.mark.unit
def test_text_label_renders_as_paragraph():
    """region_label='text' emits plain paragraph text (no # prefix)."""
    seg = _seg("This is a plain paragraph.", label="text", seq=0)
    md = segments_to_markdown([seg])
    assert "This is a plain paragraph." in md
    assert not md.strip().startswith("#"), f"Should not have heading marker, got: {md!r}"


@pytest.mark.unit
def test_edited_text_wins_over_translated():
    """Segment.edited_source_text is used when not None (edited ?? translated ?? source)."""
    seg = _seg(
        "original source",
        label="text",
        seq=0,
        translated="translated version",
        edited="edited wins",
    )
    md = segments_to_markdown([seg])
    assert "edited wins" in md, f"edited_source_text should win, got: {md!r}"
    assert "original source" not in md, "source should not appear when edited_source_text set"
    assert "translated version" not in md, "translated should not appear when edited_source_text set"
