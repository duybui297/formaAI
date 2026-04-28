"""Unit tests: OCR extractor wrapping PP-StructureV3 (OCR-01)."""
from __future__ import annotations

import numpy as np
import pytest
import pymupdf

from app.pipeline.scanned_pdf.extractor import extract_scanned_pdf_segments


def _make_blank_pdf_doc() -> pymupdf.Document:
    """Create an in-memory single-page PDF with NO extractable text (scanned page)."""
    doc = pymupdf.open()
    doc.new_page()
    return doc


def _make_erroring_pipeline() -> object:
    """Pipeline whose predict() raises an exception (simulates OCR crash)."""
    from unittest.mock import MagicMock
    pipeline = MagicMock()
    pipeline.predict.side_effect = RuntimeError("simulated OCR crash")
    return pipeline


def _make_figure_pipeline(label: str = "image") -> object:
    """Pipeline that returns a single figure/chart block."""
    from unittest.mock import MagicMock

    mock_res = MagicMock()
    mock_res.json = {
        "layout_parsing_result": {
            "parsing_res_list": [
                {
                    "block_bbox": np.array(
                        [[10, 10], [200, 10], [200, 150], [10, 150]], dtype=np.int16
                    ),
                    "block_label": label,
                    "block_content": "",
                    "block_id": 0,
                    "block_order": 0,
                },
            ]
        },
        "overall_ocr_res": {"rec_scores": [0.95]},
    }
    pipeline = MagicMock()
    pipeline.predict.return_value = [mock_res]
    return pipeline


@pytest.mark.unit
async def test_extract_segments_returns_ocr_text_kind(mock_ppstructurev3, tmp_path):
    """Each extracted text block produces a Segment with kind='ocr_text'."""
    doc = _make_blank_pdf_doc()
    pages_dir = str(tmp_path / "pages")

    segments, low_conf = await extract_scanned_pdf_segments(
        doc, job_id="test-job-01", pages_dir=pages_dir, pipeline=mock_ppstructurev3
    )

    # mock_ppstructurev3 returns 2 text blocks (paragraph_title + text)
    ocr_segs = [s for s in segments if s.kind == "ocr_text"]
    assert len(ocr_segs) == 2
    assert all(s.kind == "ocr_text" for s in ocr_segs)
    # Confidence should be set from page mean rec_scores (≈0.893)
    assert all(s.confidence is not None for s in ocr_segs)
    assert all(s.confidence > 0.7 for s in ocr_segs)


@pytest.mark.unit
async def test_extract_segments_normalizes_bbox_to_unit_range(mock_ppstructurev3, tmp_path):
    """region_bbox values are all in [0, 1]."""
    doc = _make_blank_pdf_doc()
    pages_dir = str(tmp_path / "pages")

    segments, _ = await extract_scanned_pdf_segments(
        doc, job_id="test-job-02", pages_dir=pages_dir, pipeline=mock_ppstructurev3
    )

    ocr_segs = [s for s in segments if s.kind == "ocr_text" and s.region_bbox is not None]
    assert len(ocr_segs) >= 1

    for seg in ocr_segs:
        x0, y0, x1, y1 = seg.region_bbox
        assert 0.0 <= x0 <= 1.0, f"x0={x0} out of [0,1]"
        assert 0.0 <= y0 <= 1.0, f"y0={y0} out of [0,1]"
        assert 0.0 <= x1 <= 1.0, f"x1={x1} out of [0,1]"
        assert 0.0 <= y1 <= 1.0, f"y1={y1} out of [0,1]"
        assert x0 < x1, "x0 should be less than x1"
        assert y0 < y1, "y0 should be less than y1"


@pytest.mark.unit
async def test_low_confidence_page_detected(low_confidence_mock_ppstructurev3, tmp_path):
    """Pages with mean rec_scores < 0.7 are returned in low_confidence_pages list."""
    doc = _make_blank_pdf_doc()
    pages_dir = str(tmp_path / "pages")

    segments, low_conf = await extract_scanned_pdf_segments(
        doc,
        job_id="test-job-03",
        pages_dir=pages_dir,
        pipeline=low_confidence_mock_ppstructurev3,
    )

    # Page 0 has mean conf ≈ 0.45 < 0.7
    assert 0 in low_conf
    # Segments are still produced (job continues despite low confidence)
    assert len(segments) >= 1


@pytest.mark.unit
async def test_figure_label_produces_passthrough_segment(tmp_path):
    """block_label='image' or 'chart' produces kind='figure_passthrough' segment."""
    doc = _make_blank_pdf_doc()
    pages_dir = str(tmp_path / "pages")
    pipeline = _make_figure_pipeline(label="image")

    segments, _ = await extract_scanned_pdf_segments(
        doc, job_id="test-job-04", pages_dir=pages_dir, pipeline=pipeline
    )

    passthrough_segs = [s for s in segments if s.kind == "figure_passthrough"]
    assert len(passthrough_segs) == 1
    assert passthrough_segs[0].source_text == "[Figure on left]"
    assert passthrough_segs[0].region_label == "image"


@pytest.mark.unit
async def test_per_page_ocr_error_is_isolated(tmp_path):
    """OCR failure on one page produces placeholder segment; job continues."""
    doc = _make_blank_pdf_doc()
    pages_dir = str(tmp_path / "pages")
    pipeline = _make_erroring_pipeline()

    segments, low_conf = await extract_scanned_pdf_segments(
        doc, job_id="test-job-05", pages_dir=pages_dir, pipeline=pipeline
    )

    # One placeholder segment emitted despite error
    assert len(segments) == 1
    assert segments[0].source_text == "[OCR failed for this page]"
    assert segments[0].confidence == 0.0
    assert segments[0].region_bbox is None
    # Page 0 added to low_confidence_pages
    assert 0 in low_conf
