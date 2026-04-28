"""Wave 0 RED tests: fpdf2 bilingual PDF composer (OCR-03)."""
import pytest
from app.pipeline.scanned_pdf.composer import compose_bilingual_pdf  # noqa: F401 — RED


@pytest.mark.unit
def test_compose_produces_double_wide_page(tmp_path):
    """Output PDF page width is 2x source page width (D-04-07)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/composer.py")


@pytest.mark.unit
def test_compose_region_positioned_text_on_right_half(tmp_path):
    """Translated text is placed at proportional position on right half (D-04-08)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/composer.py")


@pytest.mark.unit
def test_compose_overflow_flag_when_text_too_long(tmp_path):
    """Segment text that doesn't fit at 8pt minimum produces overflow flag (D-04-29)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/composer.py")


@pytest.mark.unit
def test_compose_produces_three_outputs(tmp_path):
    """Compose stage produces bilingual PDF, translated-only PDF, and DOCX (D-04-22)."""
    raise NotImplementedError("RED: implement pipeline/scanned_pdf/composer.py")
