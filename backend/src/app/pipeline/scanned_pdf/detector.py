"""
Scanned PDF detection heuristic (D-04-17).

Classifies a PDF as scanned if extractable text chars per page
fall below the configured threshold. Default 50 chars/page.
"""
from __future__ import annotations

import pymupdf
import structlog

log = structlog.get_logger()


def detect_scanned_pdf(doc: pymupdf.Document, threshold: float = 50.0) -> bool:
    """
    D-04-17: Return True if total_chars / page_count < threshold.

    Edge cases:
    - Empty doc (0 pages): returns False (not scanned, just empty).
    - Form PDFs with AcroForm text: classified as native (get_text includes form text).
    - PDFs with hidden OCR layer: classified as native (hidden text is real text).
    User override is applied upstream in the upload route.
    """
    page_count = len(doc)
    if page_count == 0:
        return False
    total_chars = sum(len(page.get_text().strip()) for page in doc)
    chars_per_page = total_chars / page_count
    is_scanned = chars_per_page < threshold
    log.debug(
        "scanned_pdf_detection",
        total_chars=total_chars,
        page_count=page_count,
        chars_per_page=round(chars_per_page, 1),
        threshold=threshold,
        is_scanned=is_scanned,
    )
    return is_scanned
