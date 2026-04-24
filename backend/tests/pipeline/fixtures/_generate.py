"""
Programmatic DOCX fixture generator for pipeline tests.

Run this script to (re)generate the golden .docx files in this directory.
Fixtures are deterministic — running twice produces byte-identical files
(python-docx preserves element order; timestamps are not embedded).

Usage:
    cd backend && uv run tests/pipeline/fixtures/_generate.py

The generated files are committed to the repo so tests can run without
running this script. Re-run only if you need to update the fixture content.
"""
from __future__ import annotations

import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from lxml import etree

FIXTURES_DIR = Path(__file__).parent


def generate_simple() -> None:
    """
    simple.docx: 3 body paragraphs + 2×2 table (4 cell paras).
    Total non-empty segments: 7.
    Tests: basic traversal, seg count, row-major order.
    """
    doc = Document()
    doc.add_paragraph("Hello world")
    doc.add_paragraph("This is paragraph two")
    doc.add_paragraph("Third paragraph here")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Cell A1"
    table.cell(0, 1).text = "Cell B1"
    table.cell(1, 0).text = "Cell A2"
    table.cell(1, 1).text = "Cell B2"
    doc.save(str(FIXTURES_DIR / "simple.docx"))
    print("Generated simple.docx")


def generate_table_heavy() -> None:
    """
    table_heavy.docx: 1 body paragraph + outer 2×2 table with nested 2×1 table.
    Tests: nested table traversal, inner cell visit.
    """
    doc = Document()
    doc.add_paragraph("Outer paragraph")
    outer_table = doc.add_table(rows=2, cols=2)
    # Cell (0,0): inject nested table
    cell_00 = outer_table.cell(0, 0)
    nested_table = cell_00.add_table(rows=2, cols=1)
    nested_table.cell(0, 0).text = "Inner A"
    nested_table.cell(1, 0).text = "Inner B"
    outer_table.cell(0, 1).text = "Outer B1"
    outer_table.cell(1, 0).text = "Outer A2"
    outer_table.cell(1, 1).text = "Outer B2"
    doc.save(str(FIXTURES_DIR / "table_heavy.docx"))
    print("Generated table_heavy.docx")


def generate_tracked_changes() -> None:
    """
    tracked_changes.docx: a DOCX with <w:ins> and <w:del> nodes injected.
    Tests: has_tracked_changes detection, strip_tracked_changes.
    """
    doc = Document()
    para = doc.add_paragraph("Base text. ")

    ins_xml = (
        '<w:ins xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="1" w:author="Generator" w:date="2026-04-23T00:00:00Z">'
        "<w:r><w:t>inserted addition</w:t></w:r>"
        "</w:ins>"
    )
    del_xml = (
        '<w:del xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="2" w:author="Generator" w:date="2026-04-23T00:00:00Z">'
        '<w:r><w:delText>deleted removal</w:delText></w:r>'
        "</w:del>"
    )
    para._element.append(etree.fromstring(ins_xml))
    para._element.append(etree.fromstring(del_xml))
    doc.save(str(FIXTURES_DIR / "tracked_changes.docx"))
    print("Generated tracked_changes.docx")


if __name__ == "__main__":
    generate_simple()
    generate_table_heavy()
    generate_tracked_changes()
    print("All fixtures generated.")
