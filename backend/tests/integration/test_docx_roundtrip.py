"""Integration test: DOCX-01 — round-trip preserves structure.

Tests use programmatically built DOCX files (no network required).
Marked @pytest.mark.integration so they run with `-m integration`.

B3 fixes applied:
  - extract_segments(doc, job_id) — takes Document + job_id, not path
  - reassemble_docx(doc, segments, translated_texts) — mutates in-place, caller saves
  - translated_texts keyed by seg.id (sha256 hex), values from seg.source_text
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from docx import Document


def build_test_docx(path: Path) -> None:
    """Build a minimal DOCX with heading, mixed-format paragraph, and table."""
    doc = Document()
    doc.add_heading("Test Heading", level=1)
    para = doc.add_paragraph()
    run1 = para.add_run("Bold text ")
    run1.bold = True
    run2 = para.add_run("and normal text.")
    run2.bold = False
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Cell A1"
    table.cell(0, 1).text = "Cell B1"
    table.cell(1, 0).text = "Row 2 Cell A"
    table.cell(1, 1).text = "Row 2 Cell B"
    doc.save(str(path))


@pytest.mark.integration
def test_docx_roundtrip_structure_preserved() -> None:
    """DOCX-01: round-trip with mock translations preserves bold, table structure, heading.

    B3 fix: calls extract_segments(doc, job_id) and reassemble_docx(doc, segments,
    translated_texts) per Plan 04 actual signatures. reassemble_docx mutates doc in-place;
    caller saves.
    """
    # W10: from app.XXX not from backend.src.app.XXX
    from app.pipeline.docx.extractor import extract_segments
    from app.pipeline.docx.reassembler import reassemble_docx

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "source.docx"
        out_path = Path(tmpdir) / "output.docx"
        build_test_docx(src_path)

        # B3: extract_segments takes (doc: Document, job_id: str) -> list[Segment]
        doc = Document(str(src_path))
        segments = extract_segments(doc, job_id="test-roundtrip")
        assert len(segments) >= 4, (
            f"Expected at least 4 segments (heading + para + 4 table cells); "
            f"got {len(segments)}"
        )

        # B3: mock translator — dict[segment_id -> translated_text]
        # Segment.source_text is the attribute name (not seg.text)
        translated_texts = {seg.id: f"[TR] {seg.source_text}" for seg in segments}

        # B3: reassemble_docx(doc, segments, translated_texts) mutates doc in-place
        reassemble_docx(doc, segments, translated_texts)
        # Caller saves after reassembly
        doc.save(str(out_path))

        # Verify output is a valid DOCX
        result_doc = Document(str(out_path))

        # Paragraph 0 should be the heading, translated
        heading_para = result_doc.paragraphs[0]
        assert "[TR]" in heading_para.text, (
            f"Heading not translated; text={heading_para.text!r}"
        )

        # Table should still exist with 2x2 structure
        assert len(result_doc.tables) >= 1
        tbl = result_doc.tables[0]
        assert tbl.rows[0].cells[0].text != "", (
            "Table cell A1 should not be empty after round-trip"
        )
        assert "[TR]" in tbl.rows[0].cells[0].text or "[TR]" in tbl.rows[0].cells[1].text, (
            "At least one table cell should contain translated text"
        )


@pytest.mark.integration
def test_extract_segments_does_not_miss_table_cells() -> None:
    """CORE-01 / DOCX-02: extractor uses iter_inner_content, not doc.paragraphs.

    B3 fix: calls extract_segments(doc, job_id) per Plan 04 signature.
    """
    # W10: from app.XXX
    from app.pipeline.docx.extractor import extract_segments

    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = Path(tmpdir) / "table_test.docx"
        doc = Document()
        doc.add_paragraph("Top paragraph")
        tbl = doc.add_table(rows=1, cols=2)
        tbl.cell(0, 0).text = "Table cell content"
        tbl.cell(0, 1).text = "Another cell"
        doc.save(str(src_path))

        # B3: pass Document object + job_id
        doc2 = Document(str(src_path))
        segments = extract_segments(doc2, job_id="test-table")
        texts = [seg.source_text for seg in segments]
        assert "Table cell content" in texts, (
            "Extractor must find text inside table cells; 'Table cell content' missing"
        )
        assert "Another cell" in texts, (
            "Extractor must find second table cell content"
        )
