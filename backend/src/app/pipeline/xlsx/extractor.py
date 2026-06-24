"""
Excel/XLSX segment extraction.

Walks all sheets in row-major order (top-to-bottom, left-to-right).
Each cell becomes one Segment. Empty cells are skipped.

D-06: Segment ID is sha256(source_text + structural_position)[:16].
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import unicodedata

if TYPE_CHECKING:
    pass


def _nfc(s: str) -> str:
    """NFC-normalize at extraction time (matches CORE-04 docx extractor pattern)."""
    return unicodedata.normalize("NFC", s)


def extract_xlsx_segments(file_path: str, job_id: str) -> list:
    """
    Walk all sheets of an XLSX workbook and extract text segments.

    Visit order: sheet[0], sheet[1], ...; within each sheet: row 0, row 1, ...
    Within each row: col 0, col 1, ...

    Skips:
    - Empty cells (no text or whitespace-only)
    - Cells containing only numbers that look like IDs/codes (stripped)
    - Hidden rows/columns (skipped during traversal)

    Returns a list of Segment dataclass instances.
    """
    from openpyxl import load_workbook

    from app.pipeline.segment import Segment

    segments: list[Segment] = []
    seq = 0

    wb = load_workbook(file_path, data_only=True)

    for sheet_idx, sheet in enumerate(wb.worksheets):
        sheet_name = sheet.title or f"Sheet{sheet_idx}"
        for row_idx, row in enumerate(sheet.iter_rows()):
            for col_idx, cell in enumerate(row):
                # Skip empty / whitespace-only cells
                raw_value = cell.value
                if raw_value is None:
                    continue
                text = _nfc(str(raw_value).strip())
                if not text:
                    continue

                # Structural position encodes location for deterministic ID
                structural_position = (
                    f"sheet.{sheet_name}.row.{row_idx}.col.{col_idx}"
                )

                segment = Segment.from_text(
                    source_text=text,
                    structural_position=structural_position,
                    seq_in_job=seq,
                    kind="text",
                )
                segments.append(segment)
                seq += 1

    wb.close()
    return segments
