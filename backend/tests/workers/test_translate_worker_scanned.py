"""Wave 0 RED tests: worker dispatch for scanned_pdf format (OCR-04)."""
import pytest


@pytest.mark.unit
async def test_worker_dispatches_scanned_pdf_format(db_session):
    """match job.input_format case 'scanned_pdf' reaches OCR pipeline (D-04-05)."""
    raise NotImplementedError("RED: implement translate_worker.py scanned_pdf case")


@pytest.mark.unit
async def test_worker_ocr_stage_sets_needs_review_on_low_confidence(db_session):
    """Job status transitions to needs_review when OCR stage detects low confidence page (D-04-02)."""
    raise NotImplementedError("RED: implement translate_worker.py needs_review transition")


@pytest.mark.unit
async def test_worker_ocr_stage_retry_budget(db_session):
    """OCR stage retries max 2 times before failing the job (D-04-30)."""
    raise NotImplementedError("RED: implement translate_worker.py retry logic")


@pytest.mark.unit
async def test_worker_sse_publishes_stage_progress(db_session):
    """SSE payload includes stage_progress dict with stage/current/total (D-04-x SSE)."""
    raise NotImplementedError("RED: implement _publish_progress stage_progress field")
