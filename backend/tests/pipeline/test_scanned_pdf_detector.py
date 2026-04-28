"""Wave 0 RED tests: D-04-17 text-density scanned PDF detection heuristic."""
import pytest
from app.pipeline.scanned_pdf.detector import detect_scanned_pdf  # noqa: F401 — RED: module doesn't exist yet


@pytest.mark.unit
def test_detect_native_pdf_returns_false(tmp_path):
    """PDF with plenty of text is classified as native (not scanned)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/detector.py")


@pytest.mark.unit
def test_detect_scanned_pdf_returns_true(tmp_path):
    """PDF with no extractable text is classified as scanned."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/detector.py")


@pytest.mark.unit
def test_detect_uses_configurable_threshold(tmp_path):
    """Text density threshold is configurable via threshold parameter."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/detector.py")
