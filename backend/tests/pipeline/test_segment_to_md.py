"""Wave 0 RED tests: Segment tree → Markdown helper (D-04-33)."""
import pytest
from app.pipeline.scanned_pdf.segment_to_md import segments_to_markdown  # noqa: F401 — RED


@pytest.mark.unit
def test_doc_title_renders_as_h1():
    """region_label='doc_title' emits '# text' heading."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/segment_to_md.py")


@pytest.mark.unit
def test_paragraph_title_renders_as_h2():
    """region_label='paragraph_title' emits '## text' heading."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/segment_to_md.py")


@pytest.mark.unit
def test_text_label_renders_as_paragraph():
    """region_label='text' emits plain paragraph text."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/segment_to_md.py")


@pytest.mark.unit
def test_edited_text_wins_over_translated():
    """Segment.edited_text is used when not None (edited_text ?? translated_text ?? source)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/segment_to_md.py")
