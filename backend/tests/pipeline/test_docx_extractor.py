"""
Tests for pipeline/docx/extractor.py and pipeline/docx/reassembler.py.

TDD RED: Written before implementation. These tests define the expected behavior
of walk_document, extract_segments, write_translated_paragraph, and reassemble_docx.

Golden fixtures are created programmatically via python-docx — no raw binary commits.
"""
from __future__ import annotations

import pytest
from docx import Document
from docx.oxml.ns import qn

from app.pipeline.docx.extractor import extract_run_segments, extract_segments, walk_document
from app.pipeline.docx.reassembler import (
    reassemble_docx,
    reassemble_docx_runs,
    write_translated_paragraph,
    write_translated_run,
)


# ---------------------------------------------------------------------------
# Programmatic DOCX fixture builders
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def simple_doc(tmp_path_factory):
    """
    Simple DOCX with 3 body paragraphs + a 2×2 table (4 cell paragraphs).
    Total text-bearing locations: 3 body paras + 4 table cell paras = 7.
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
    path = tmp_path_factory.mktemp("fixtures") / "simple.docx"
    doc.save(str(path))
    return path


@pytest.fixture(scope="module")
def table_heavy_doc(tmp_path_factory):
    """
    DOCX with a table where one cell contains a nested table.
    Outer table: 2×2. Inner table in cell(0,0): 2×1 with 'Inner A' and 'Inner B'.
    """
    doc = Document()
    doc.add_paragraph("Outer paragraph")
    outer_table = doc.add_table(rows=2, cols=2)
    # Cell (0,0): add nested table
    cell_00 = outer_table.cell(0, 0)
    # Clear default empty paragraph first — add nested table
    nested_table = cell_00.add_table(rows=2, cols=1)
    nested_table.cell(0, 0).text = "Inner A"
    nested_table.cell(1, 0).text = "Inner B"
    outer_table.cell(0, 1).text = "Outer B1"
    outer_table.cell(1, 0).text = "Outer A2"
    outer_table.cell(1, 1).text = "Outer B2"
    path = tmp_path_factory.mktemp("fixtures") / "table_heavy.docx"
    doc.save(str(path))
    return path


@pytest.fixture(scope="module")
def bold_italic_doc(tmp_path_factory):
    """
    DOCX with a paragraph containing 3 runs: bold, normal, italic.
    Used to verify run-merge write-back preserves formatting.
    """
    doc = Document()
    para = doc.add_paragraph()
    run1 = para.add_run("Bold text ")
    run1.bold = True
    run2 = para.add_run("normal text ")
    run3 = para.add_run("italic text")
    run3.italic = True
    path = tmp_path_factory.mktemp("fixtures") / "bold_italic.docx"
    doc.save(str(path))
    return path


# ---------------------------------------------------------------------------
# walk_document / traversal tests (DOCX-01)
# ---------------------------------------------------------------------------


def test_walk_body_visits_all_body_paragraphs(simple_doc):
    """walk_document must yield all 3 body paragraphs."""
    doc = Document(str(simple_doc))
    all_paras = [p for tag, p in walk_document(doc) if tag == "para"]
    texts = [p.text for p in all_paras]
    assert "Hello world" in texts
    assert "This is paragraph two" in texts
    assert "Third paragraph here" in texts


def test_walk_body_visits_table_cells(simple_doc):
    """walk_document must yield all 4 table cell paragraphs in row-major order."""
    doc = Document(str(simple_doc))
    cell_paras = [p for tag, p in walk_document(doc) if tag == "cell_para"]
    texts = [p.text for p in cell_paras]
    assert "Cell A1" in texts
    assert "Cell B1" in texts
    assert "Cell A2" in texts
    assert "Cell B2" in texts


def test_walk_visits_in_row_major_order(simple_doc):
    """Table cells must be visited row-major: A1, B1 before A2, B2."""
    doc = Document(str(simple_doc))
    cell_paras = [p for tag, p in walk_document(doc) if tag == "cell_para"]
    texts = [p.text for p in cell_paras]
    # Row 0 comes before row 1
    assert texts.index("Cell A1") < texts.index("Cell A2")
    assert texts.index("Cell B1") < texts.index("Cell B2")


def test_walk_nested_table_visits_inner_cells(table_heavy_doc):
    """walk_document must recurse into nested tables and visit their cells."""
    doc = Document(str(table_heavy_doc))
    cell_paras = [p for tag, p in walk_document(doc) if tag == "cell_para"]
    texts = [p.text for p in cell_paras]
    assert "Inner A" in texts
    assert "Inner B" in texts
    assert "Outer B1" in texts
    assert "Outer A2" in texts
    assert "Outer B2" in texts


def test_doc_paragraphs_misses_table_cells_regression(simple_doc):
    """
    Regression guard (DOCX-01 Pitfall #2): doc.paragraphs misses table cells.

    doc.paragraphs only returns 3 body paras; walk_document returns 7 (3 + 4 cells).
    This test documents and guards against the anti-pattern.
    """
    doc = Document(str(simple_doc))
    # The anti-pattern: doc.paragraphs misses table cells
    doc_paragraphs_texts = [p.text for p in doc.paragraphs if p.text.strip()]
    # The correct approach: walk_document
    walk_texts = [p.text for _, p in walk_document(doc) if p.text.strip()]

    # doc.paragraphs MUST miss the table cells
    assert "Cell A1" not in doc_paragraphs_texts
    assert "Cell B1" not in doc_paragraphs_texts
    # walk_document MUST include them
    assert "Cell A1" in walk_texts
    assert "Cell B1" in walk_texts
    # walk finds more than doc.paragraphs
    assert len(walk_texts) > len(doc_paragraphs_texts)


# ---------------------------------------------------------------------------
# extract_segments tests
# ---------------------------------------------------------------------------


def test_extract_segments_assigns_seq_in_job(simple_doc):
    """Segments must have sequential seq_in_job starting at 0."""
    doc = Document(str(simple_doc))
    segments = extract_segments(doc, job_id="test-job-01")
    seqs = [s.seq_in_job for s in segments]
    assert seqs == list(range(len(segments)))


def test_extract_segments_generates_stable_ids(simple_doc):
    """Extracting the same doc twice must produce identical segment IDs."""
    doc1 = Document(str(simple_doc))
    doc2 = Document(str(simple_doc))
    segments1 = extract_segments(doc1, job_id="job-a")
    segments2 = extract_segments(doc2, job_id="job-b")  # different job_id, same IDs
    ids1 = [s.id for s in segments1]
    ids2 = [s.id for s in segments2]
    assert ids1 == ids2


def test_extract_segments_skips_empty_paragraphs():
    """Empty paragraphs (whitespace-only) must not become segments."""
    doc = Document()
    doc.add_paragraph("Real content")
    doc.add_paragraph("")  # empty
    doc.add_paragraph("   ")  # whitespace-only
    doc.add_paragraph("More content")
    segments = extract_segments(doc, job_id="test-job")
    texts = [s.source_text for s in segments]
    assert "Real content" in texts
    assert "More content" in texts
    assert "" not in texts
    assert "   " not in texts
    assert len(segments) == 2


def test_extract_segments_visits_all_locations(simple_doc):
    """extract_segments must include text from both body paras and table cells."""
    doc = Document(str(simple_doc))
    segments = extract_segments(doc, job_id="test-job")
    texts = [s.source_text for s in segments]
    assert "Hello world" in texts
    assert "Cell A1" in texts
    assert "Cell B2" in texts


def test_extract_segments_count(simple_doc):
    """simple_doc has 3 body paras + 4 table cell paras = 7 text segments."""
    doc = Document(str(simple_doc))
    segments = extract_segments(doc, job_id="test-job")
    assert len(segments) == 7


# ---------------------------------------------------------------------------
# write_translated_paragraph tests (DOCX-02)
# ---------------------------------------------------------------------------


def test_write_translated_paragraph_preserves_bold(bold_italic_doc):
    """
    DOCX-02: After write-back, the first run must still be bold.
    run-merge never touches <w:rPr>, only <w:t>.
    """
    doc = Document(str(bold_italic_doc))
    para = doc.paragraphs[0]
    assert para.runs[0].bold is True, "Test precondition: run 0 is bold"

    write_translated_paragraph(para, "Translated text")

    assert para.runs[0].bold is True, "Bold must be preserved after write-back"


def test_write_translated_paragraph_multi_run_blanks_remaining(bold_italic_doc):
    """
    DOCX-02: runs[0] gets translated text; runs[1] and runs[2] become empty strings.
    The <w:r> elements are preserved (not removed).
    """
    doc = Document(str(bold_italic_doc))
    para = doc.paragraphs[0]
    assert len(para.runs) == 3, "Test precondition: 3 runs"

    write_translated_paragraph(para, "All text now in first run")

    assert para.runs[0].text == "All text now in first run"
    assert para.runs[1].text == ""
    assert para.runs[2].text == ""
    # The run elements must still exist (not removed from the XML)
    assert len(para.runs) == 3


def test_write_translated_paragraph_no_runs():
    """write_translated_paragraph on a para with no runs must add a run."""
    doc = Document()
    para = doc.add_paragraph()  # empty para, no runs
    assert len(para.runs) == 0

    write_translated_paragraph(para, "New text")

    assert para.text == "New text"


def test_paragraph_text_setter_destroys_formatting_anti_pattern(bold_italic_doc):
    """
    DOCX-02 anti-pattern documentation: paragraph.text = value destroys bold.

    This negative test demonstrates WHY the run-merge strategy is mandatory.
    If this test starts failing (paragraph.text stops destroying formatting),
    remove the anti-pattern guard — but it should never happen per OOXML spec.
    """
    doc = Document(str(bold_italic_doc))
    para = doc.paragraphs[0]
    assert para.runs[0].bold is True, "Test precondition"

    # Anti-pattern: paragraph.text = value
    para.text = "Set via paragraph.text"

    # All formatting must be gone — this is the documented destruction
    assert para.runs[0].bold is None or para.runs[0].bold is False


# ---------------------------------------------------------------------------
# Full pipeline round-trip test
# ---------------------------------------------------------------------------


def test_reassemble_docx_writes_translation(simple_doc):
    """
    Full pipeline: extract_segments → identity translate → reassemble_docx.
    Verifies paragraph count and translated text is written back.
    """
    doc = Document(str(simple_doc))
    segments = extract_segments(doc, job_id="roundtrip-job")

    # Identity translation: each segment id → source text (unchanged)
    translated_texts = {s.id: s.source_text for s in segments}

    reassemble_docx(doc, segments, translated_texts)

    # After reassembly, text should still be present
    walk_texts = [p.text for _, p in walk_document(doc) if p.text.strip()]
    assert "Hello world" in walk_texts
    assert "Cell A1" in walk_texts


def test_reassemble_docx_actually_translates(simple_doc):
    """
    reassemble_docx must write the translated text (not the original) back.
    """
    doc = Document(str(simple_doc))
    segments = extract_segments(doc, job_id="translate-test")

    # Translate first paragraph only
    first_seg = next(s for s in segments if s.source_text == "Hello world")
    translated_texts = {first_seg.id: "Xin chào thế giới"}

    reassemble_docx(doc, segments, translated_texts)

    walk_texts = [p.text for _, p in walk_document(doc)]
    assert "Xin chào thế giới" in walk_texts


# ---------------------------------------------------------------------------
# Per-run segment extraction tests (G2 gap closure — plan 01-13)
# ---------------------------------------------------------------------------


def test_extract_run_segments_multi_format_paragraph():
    """
    extract_run_segments must split at format boundaries and assign run_index.

    Paragraph: bold "Bold text " | plain "plain text " | italic+underline "italic-underline"
    → 3 segments, one per run, each with correct run_index and source_text.
    """
    doc = Document()
    para = doc.add_paragraph()
    run0 = para.add_run("Bold text ")
    run0.bold = True
    run1 = para.add_run("plain text ")
    # run1 has no bold/italic — plain formatting (defaults)
    _ = run1  # suppress unused variable warning
    run2 = para.add_run("italic-underline")
    run2.italic = True
    run2.underline = True

    segments = extract_run_segments(doc, "job1")

    assert len(segments) == 3
    assert segments[0].source_text == "Bold text "
    assert segments[0].run_index == 0
    assert segments[1].source_text == "plain text "
    assert segments[1].run_index == 1
    assert segments[2].source_text == "italic-underline"
    assert segments[2].run_index == 2


def test_extract_run_segments_uniform_format_merges():
    """
    extract_run_segments must merge consecutive runs with identical formatting.

    Paragraph: bold "A" | bold "B" | bold "C"
    → 1 segment covering all 3 runs (run_index=0, run_group_size=3).
    """
    doc = Document()
    para = doc.add_paragraph()
    for ch in ("A", "B", "C"):
        run = para.add_run(ch)
        run.bold = True

    segments = extract_run_segments(doc, "job1")

    assert len(segments) == 1
    assert segments[0].source_text == "ABC"
    assert segments[0].run_index == 0
    assert segments[0].run_group_size == 3


def test_write_translated_run_preserves_formatting():
    """
    write_translated_run must write into the target run slot only.

    Writing to run_index=2 must not alter run 0's formatting or text.
    """
    doc = Document()
    para = doc.add_paragraph()
    run0 = para.add_run("Bold text ")
    run0.bold = True
    para.add_run("plain text ")
    run2 = para.add_run("italic-underline")
    run2.italic = True
    run2.underline = True

    # Build a minimal Segment pointing at run_index=2
    from app.pipeline.segment import Segment

    seg = Segment.from_text(
        source_text="italic-underline",
        structural_position="para.0.run2",
        seq_in_job=2,
        run_index=2,
        run_group_size=1,
    )

    write_translated_run(para, seg, "translated_end")

    assert para.runs[2].text == "translated_end"
    assert para.runs[2].italic is True
    assert para.runs[2].underline is True
    # run 0 must be untouched
    assert para.runs[0].text == "Bold text "
    assert para.runs[0].bold is True


def test_write_translated_run_run_index_out_of_bounds_skips():
    """
    write_translated_run must not raise when run_index >= len(paragraph.runs).

    A malformed Segment with run_index=99 on a 1-run paragraph should be silently
    skipped without raising IndexError (T-13-01 mitigation).
    """
    doc = Document()
    para = doc.add_paragraph()
    para.add_run("only run")

    from app.pipeline.segment import Segment

    seg = Segment.from_text(
        source_text="only run",
        structural_position="para.0.run99",
        seq_in_job=0,
        run_index=99,
        run_group_size=1,
    )

    # Must not raise
    write_translated_run(para, seg, "should be ignored")

    # Original text must be unchanged
    assert para.runs[0].text == "only run"


def test_reassemble_docx_runs_round_trip():
    """
    Full round-trip: extract_run_segments → reassemble_docx_runs must preserve
    per-run formatting while writing back translated text.

    Paragraph: bold "Hello " | plain "world" | italic "end"
    After round-trip:
      - runs[0].text == "TRANS_0"; bold is True
      - runs[1].text == "TRANS_1"; bold is None (plain)
      - runs[2].text == "TRANS_2"; italic is True
    """
    doc = Document()
    para = doc.add_paragraph()
    run0 = para.add_run("Hello ")
    run0.bold = True
    para.add_run("world")
    run2 = para.add_run("end")
    run2.italic = True

    segs = extract_run_segments(doc, "j1")
    assert len(segs) == 3, f"Expected 3 segments, got {len(segs)}"

    translated_texts = {seg.id: f"TRANS_{i}" for i, seg in enumerate(segs)}
    reassemble_docx_runs(doc, segs, translated_texts)

    assert para.runs[0].text == "TRANS_0"
    assert para.runs[0].bold is True
    assert para.runs[1].text == "TRANS_1"
    assert para.runs[1].bold is None  # plain — no bold set
    assert para.runs[2].text == "TRANS_2"
    assert para.runs[2].italic is True
