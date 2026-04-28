"""Wave 0 RED tests: OCR extractor wrapping PP-StructureV3 (OCR-01)."""
import pytest
from app.pipeline.scanned_pdf.extractor import extract_scanned_pdf_segments  # noqa: F401 — RED


@pytest.mark.unit
async def test_extract_segments_returns_ocr_text_kind(mock_ppstructurev3, tmp_path):
    """Each extracted block produces a Segment with kind='ocr_text'."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/extractor.py")


@pytest.mark.unit
async def test_extract_segments_normalizes_bbox_to_unit_range(mock_ppstructurev3, tmp_path):
    """region_bbox values are all in [0, 1]."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/extractor.py")


@pytest.mark.unit
async def test_low_confidence_page_detected(low_confidence_mock_ppstructurev3, tmp_path):
    """Pages with mean rec_scores < 0.7 are returned in low_confidence_pages list."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/extractor.py")


@pytest.mark.unit
async def test_figure_label_produces_passthrough_segment(tmp_path):
    """block_label='image' or 'chart' produces segment skipped by translator."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/extractor.py")


@pytest.mark.unit
async def test_per_page_ocr_error_is_isolated(tmp_path):
    """OCR failure on one page produces placeholder segment; other pages processed."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/extractor.py")
