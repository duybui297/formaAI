---
phase: 01-foundation-docx-pipeline
plan: "04"
type: tdd
wave: 2
depends_on:
  - "02"
  - "03"
files_modified:
  - backend/src/app/pipeline/__init__.py
  - backend/src/app/pipeline/segment.py
  - backend/src/app/pipeline/placeholder.py
  - backend/src/app/pipeline/docx/__init__.py
  - backend/src/app/pipeline/docx/extractor.py
  - backend/src/app/pipeline/docx/reassembler.py
  - backend/src/app/pipeline/docx/tracked.py
  - backend/tests/pipeline/__init__.py
  - backend/tests/pipeline/test_docx_extractor.py
  - backend/tests/pipeline/test_placeholder.py
  - backend/tests/pipeline/test_tracked_changes.py
  - backend/tests/pipeline/fixtures/simple.docx
  - backend/tests/pipeline/fixtures/table_heavy.docx
autonomous: true
requirements:
  - CORE-01
  - CORE-05
  - DOCX-01
  - DOCX-02
  - DOCX-03
  - DOCX-04

must_haves:
  truths:
    - "DOCX walker visits body paragraphs, table cells (row-major), headers, footers, and comments"
    - "run-merge write-back writes into runs[0].text, blanks runs[1:], never calls paragraph.text setter"
    - "placeholder extraction replaces URLs, emails, template vars, version strings with ⟦T{n}⟧"
    - "placeholder restoration replaces all ⟦T{n}⟧ back to originals; no markers remain"
    - "has_tracked_changes detects <w:ins>/<w:del> in document XML"
    - "Segment ID is sha256(source_text + structural_position)[:16] (D-06)"
  artifacts:
    - path: "backend/src/app/pipeline/segment.py"
      provides: "Segment dataclass with SHA ID generation (D-05/D-06)"
      exports: ["Segment", "make_segment_id"]
    - path: "backend/src/app/pipeline/placeholder.py"
      provides: "extract_placeholders() and restore_placeholders() (CORE-05)"
      exports: ["extract_placeholders", "restore_placeholders"]
    - path: "backend/src/app/pipeline/docx/extractor.py"
      provides: "walk_document() structural tree builder (CORE-01/DOCX-01)"
      exports: ["walk_document", "extract_segments"]
    - path: "backend/src/app/pipeline/docx/reassembler.py"
      provides: "write_translated_paragraph() run-merge write-back (DOCX-02)"
      exports: ["write_translated_paragraph", "reassemble_docx"]
    - path: "backend/src/app/pipeline/docx/tracked.py"
      provides: "has_tracked_changes(), strip_tracked_changes(), preserve_tracked_changes() (DOCX-04)"
      exports: ["has_tracked_changes", "strip_tracked_changes"]
    - path: "backend/tests/pipeline/fixtures/simple.docx"
      provides: "Golden fixture: paragraphs + table + hyperlink for traversal testing"
    - path: "backend/tests/pipeline/fixtures/table_heavy.docx"
      provides: "Golden fixture: nested tables for row-major traversal testing"
  key_links:
    - from: "backend/src/app/pipeline/docx/extractor.py"
      to: "backend/src/app/pipeline/segment.py"
      via: "make_segment_id(source_text, structural_position)"
    - from: "backend/src/app/pipeline/docx/reassembler.py"
      to: "runs[0].text = translated_text"
      via: "write_translated_paragraph DOCX-02 invariant"
      pattern: "runs[0].text"
    - from: "backend/src/app/pipeline/placeholder.py"
      to: "⟦T{n}⟧ markers"
      via: "_PROTECTED_PATTERNS regex list"
      pattern: "⟦T"
---

<objective>
Implement the DOCX document parsing pipeline: Segment dataclass (D-05/D-06), placeholder extraction/restoration (CORE-05), DOCX traversal walker (CORE-01), run-merge write-back (DOCX-02), and tracked-changes handling (DOCX-04). All with TDD using pytest-generated golden DOCX fixtures.

Purpose: The translator needs segments to translate; the worker needs a reassembler to write results. Without this plan, the end-to-end DOCX flow is impossible.
Output: backend/src/app/pipeline/ fully implemented and tested. Tests use real DOCX files created programmatically (no external fixtures needed).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- Exact code patterns from RESEARCH.md §4 and §5 — copy verbatim -->

walk_document pattern (RESEARCH.md §4):
```python
def walk_document(doc: Document):
    yield from _walk_body(doc)                # body paragraphs + tables
    for section in doc.sections:              # headers + footers
        for hf in [section.header, section.footer, ...]:
            if hf is not None and hf.is_linked_to_previous is False:
                yield from _walk_body_element(hf._element)
    # comments via doc.part._comments_part

def _walk_body(doc: Document):
    for block in doc.iter_inner_content():    # NOT doc.paragraphs — misses tables
        if isinstance(block, Paragraph): yield ("para", block)
        elif isinstance(block, Table): yield from _walk_table(block)

def _walk_table(table):
    for row in table.rows:
        for cell in row.cells:
            for block in cell.iter_inner_content():  # NOT cell.paragraphs
                if isinstance(block, Paragraph): yield ("cell_para", block)
                elif isinstance(block, Table): yield from _walk_table(block)
```

run-merge write-back (RESEARCH.md §4, DOCX-02 — NEVER paragraph.text = value):
```python
def write_translated_paragraph(paragraph, translated_text: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(translated_text)
        return
    runs[0].text = nfc(translated_text)  # only touches <w:t>, preserves <w:rPr>
    for run in runs[1:]:
        run.text = ""                    # blank but do NOT remove the <w:r> element
```

has_tracked_changes (RESEARCH.md §4):
```python
def has_tracked_changes(doc: Document) -> bool:
    body_xml = doc._element.xml
    return "<w:ins" in body_xml or "<w:del" in body_xml
```

placeholder extraction (RESEARCH.md §5):
```python
_PROTECTED_PATTERNS = [
    re.compile(r'https?://\S+'),
    re.compile(r'[\w.+-]+@[\w.-]+\.\w{2,}'),
    re.compile(r'\{\{[^}]+\}\}'),
    re.compile(r'\$\{[^}]+\}'),
    re.compile(r'<%=?\s*[^%]+%>'),
    re.compile(r'\d{4}-\d{2}-\d{2}(?:T[\d:Z.+\-]+)?'),
    re.compile(r'v\d+\.\d+[\.\d\w\-]*'),
]
def extract_placeholders(text: str) -> tuple[str, dict[int, str]]: ...
def restore_placeholders(text: str, tokens: dict[int, str]) -> str: ...
```

Segment ID (D-06):
```python
import hashlib
def make_segment_id(source_text: str, structural_position: str) -> str:
    payload = f"{source_text}\x00{structural_position}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

CRITICAL pitfall (RESEARCH.md Pitfall #1):
NEVER call paragraph.text = value — it destroys all run formatting.
Always use: runs[0].text = translated_text; [setattr(r, 'text', '') for r in runs[1:]]

CRITICAL pitfall (RESEARCH.md Pitfall #2):
NEVER use doc.paragraphs — use doc.iter_inner_content() + _walk_table() recursively.
</interfaces>
</context>

<tasks>

<task type="tdd">
  <name>Task 1: Segment Model + Placeholder Protection (CORE-05)</name>
  <files>
    backend/src/app/pipeline/__init__.py
    backend/src/app/pipeline/segment.py
    backend/src/app/pipeline/placeholder.py
    backend/tests/pipeline/__init__.py
    backend/tests/pipeline/test_placeholder.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 5: CORE-05 placeholder taxonomy + extract/restore code)
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (pipeline/segment.py and pipeline/placeholder.py sections)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-05 Segment tree, D-06 Segment ID)
  </read_first>
  <behavior>
    RED — write tests first for placeholder:
    - test_extract_url_produces_placeholder: "Visit https://aicore.vn for info" → marker + {"0": "https://aicore.vn"}
    - test_restore_replaces_marker: restore(extracted_text, tokens) → original text
    - test_no_leftover_markers_after_restore: no "⟦T" in restored output
    - test_extract_email: "contact@aicore.vn works" → marker
    - test_extract_template_var: "Hello {{user_name}}" → marker
    - test_extract_version: "using v2.3.1" → marker
    - test_extract_iso_date: "on 2026-04-23" → marker
    - test_extract_multiple_tokens: URL + email in same text → two markers ⟦T0⟧ and ⟦T1⟧
    - test_restore_missing_key_keeps_marker: tokens missing key → marker stays (fallback behavior)
    - test_segment_id_deterministic: make_segment_id("text","pos") always returns same 16-char hex
    - test_segment_id_length: result is exactly 16 chars
    - test_segment_id_differs_on_different_inputs: different text → different id
  </behavior>
  <action>
RED: Write tests in backend/tests/pipeline/test_placeholder.py.

GREEN: Implement:

`backend/src/app/pipeline/__init__.py` (empty)
`backend/tests/pipeline/__init__.py` (empty)

`backend/src/app/pipeline/segment.py` (D-05/D-06):
```python
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


def make_segment_id(source_text: str, structural_position: str) -> str:
    """D-06: sha256(source_text + structural_position)[:16]"""
    payload = f"{source_text}\x00{structural_position}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class Segment:
    """
    D-05: Rich structural segment. Parent reference enables tree-walk reassembly.
    D-06: Deterministic id from sha256(source_text + structural_position).
    """
    id: str                          # 16-char hex (D-06)
    seq_in_job: int                  # human-readable "segment 5/210"
    source_text: str
    structural_position: str         # e.g. "body.para.0", "body.table.0.row.1.cell.0.para.0"
    is_comment: bool = False         # D-14
    is_inserted: bool = False        # D-13 tracked changes
    is_deleted: bool = False         # D-13 tracked changes
    translated_text: str | None = None

    @classmethod
    def from_text(
        cls,
        source_text: str,
        structural_position: str,
        seq_in_job: int,
        **kwargs,
    ) -> "Segment":
        return cls(
            id=make_segment_id(source_text, structural_position),
            seq_in_job=seq_in_job,
            source_text=source_text,
            structural_position=structural_position,
            **kwargs,
        )
```

`backend/src/app/pipeline/placeholder.py` (RESEARCH.md §5 exact patterns):
```python
from __future__ import annotations
import re

_PROTECTED_PATTERNS = [
    re.compile(r'https?://\S+'),
    re.compile(r'[\w.+-]+@[\w.-]+\.\w{2,}'),
    re.compile(r'\{\{[^}]+\}\}'),
    re.compile(r'\$\{[^}]+\}'),
    re.compile(r'<%=?\s*[^%]+%>'),
    re.compile(r'\d{4}-\d{2}-\d{2}(?:T[\d:Z.+\-]+)?'),
    re.compile(r'v\d+\.\d+[\.\d\w\-]*'),
]

_PLACEHOLDER_RE = re.compile(r'⟦T(\d+)⟧')


def extract_placeholders(text: str) -> tuple[str, dict[int, str]]:
    """
    Replace all non-translatable tokens with ⟦T{n}⟧ markers.
    Returns (modified_text, {n: original_token}).
    Call before sending segment text to translate_batch.
    """
    tokens: dict[int, str] = {}
    counter = 0

    for pattern in _PROTECTED_PATTERNS:
        def replacer(m: re.Match, _counter: list[int] = [counter]) -> str:
            nonlocal counter
            idx = counter
            counter += 1
            tokens[idx] = m.group(0)
            return f"⟦T{idx}⟧"
        text = pattern.sub(replacer, text)

    return text, tokens


def restore_placeholders(text: str, tokens: dict[int, str]) -> str:
    """
    Restore ⟦T{n}⟧ markers back to original tokens.
    Fallback: if marker index missing in tokens, keeps the marker (visible error).
    """
    def restorer(m: re.Match) -> str:
        idx = int(m.group(1))
        return tokens.get(idx, m.group(0))

    return _PLACEHOLDER_RE.sub(restorer, text)
```

REFACTOR: Fix any closure scoping issues in extract_placeholders (the `counter` nonlocal pattern).
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      uv run pytest tests/pipeline/test_placeholder.py -v --no-header 2>&amp;1 | tail -5
    </automated>
  </verify>
  <done>
    All placeholder tests pass.
    extract_placeholders replaces URLs, emails, template vars, version strings, ISO dates with ⟦T{n}⟧.
    restore_placeholders returns original text with no remaining ⟦T{n}⟧ markers.
    make_segment_id returns deterministic 16-char hex string.
  </done>
</task>

<task type="tdd">
  <name>Task 2: DOCX Extractor + Reassembler + Tracked Changes</name>
  <files>
    backend/src/app/pipeline/docx/__init__.py
    backend/src/app/pipeline/docx/extractor.py
    backend/src/app/pipeline/docx/reassembler.py
    backend/src/app/pipeline/docx/tracked.py
    backend/tests/pipeline/test_docx_extractor.py
    backend/tests/pipeline/test_tracked_changes.py
    backend/tests/pipeline/fixtures/simple.docx
    backend/tests/pipeline/fixtures/table_heavy.docx
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 4: full traversal + run-merge + tracked-changes patterns, Code Examples section)
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (docx/extractor.py, docx/reassembler.py, docx/tracked.py sections)
    backend/src/app/pipeline/segment.py (Segment.from_text interface)
  </read_first>
  <behavior>
    RED — write fixture-creation helpers + tests first:
    - Fixture creation: use python-docx to create simple.docx programmatically (3 paras + 1 table)
    - test_walk_body_visits_all_paragraphs: simple.docx → all 3 paras yielded
    - test_walk_body_visits_table_cells: simple.docx with 2x2 table → 4 cell paras yielded
    - test_walk_nested_table: table_heavy.docx with nested table → inner cells also visited
    - test_doc_paragraphs_misses_table_cells: show doc.paragraphs only sees 3, not 7 (regression guard)
    - test_extract_segments_assigns_seq_in_job: segments have seq 0,1,2... in order
    - test_extract_segments_generates_stable_ids: same doc extracted twice → same segment IDs
    - test_write_translated_paragraph_preserves_bold: para with bold run → after write-back run is still bold
    - test_write_translated_paragraph_no_runs: empty para → add_run called, text set
    - test_write_translated_paragraph_multi_run: 3 runs → runs[0] has translated text, runs[1] and [2] are ""
    - test_paragraph_text_setter_MUST_NOT_BE_USED: negative test — paragraph.text = "x" destroys formatting (document the anti-pattern)
    - test_has_tracked_changes_detects_ins: doc with <w:ins> in XML → True
    - test_has_tracked_changes_returns_false_for_clean_doc: clean doc → False
  </behavior>
  <action>
RED: Write fixture-generation helpers (create simple.docx and table_heavy.docx programmatically in conftest or test file) and tests.

GREEN: Implement:

`backend/src/app/pipeline/docx/__init__.py` (empty)

`backend/src/app/pipeline/docx/extractor.py` (RESEARCH.md §4 exact pattern):
```python
from __future__ import annotations
import unicodedata
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from app.pipeline.segment import Segment, make_segment_id


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time (Pitfall #7 in RESEARCH.md)."""
    return unicodedata.normalize("NFC", s)


def walk_document(doc: Document):
    """
    Yield all (location_tag, paragraph_object) pairs in document order.
    Visits: body paragraphs, table cells (row-major), headers, footers.
    CRITICAL: Uses doc.iter_inner_content(), NOT doc.paragraphs (Pitfall #2).
    """
    yield from _walk_body(doc)
    for section in doc.sections:
        for hf in [
            section.header, section.footer,
            section.even_page_header, section.even_page_footer,
            section.first_page_header, section.first_page_footer,
        ]:
            if hf is not None and not hf.is_linked_to_previous:
                yield from _walk_element_paragraphs(hf._element, "header")


def _walk_body(doc: Document):
    for block in doc.iter_inner_content():
        if isinstance(block, Paragraph):
            yield ("para", block)
        elif isinstance(block, Table):
            yield from _walk_table(block)


def _walk_table(table: Table):
    for row in table.rows:
        for cell in row.cells:
            for block in cell.iter_inner_content():  # NOT cell.paragraphs
                if isinstance(block, Paragraph):
                    yield ("cell_para", block)
                elif isinstance(block, Table):
                    yield from _walk_table(block)


def _walk_element_paragraphs(element, location_tag: str):
    """Walk raw lxml element yielding Paragraph objects found inside."""
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph as DocxParagraph
    for p_elem in element.iter(qn("w:p")):
        yield (location_tag, DocxParagraph(p_elem, None))


def extract_segments(doc: Document, job_id: str) -> list[Segment]:
    """
    Walk the document and build an ordered Segment list.
    Skips empty paragraphs (no runs or whitespace-only text).
    NFC-normalizes source_text at extraction (CORE-04, Pitfall #7).
    """
    segments: list[Segment] = []
    seq = 0
    for loc_tag, paragraph in walk_document(doc):
        text = _nfc(paragraph.text)
        if not text.strip():
            continue
        structural_position = f"{loc_tag}.{seq}"
        segment = Segment.from_text(
            source_text=text,
            structural_position=structural_position,
            seq_in_job=seq,
        )
        segments.append(segment)
        seq += 1
    return segments
```

`backend/src/app/pipeline/docx/reassembler.py` (RESEARCH.md §4 run-merge pattern):
```python
from __future__ import annotations
import unicodedata
from docx import Document
from docx.text.paragraph import Paragraph
from app.pipeline.segment import Segment


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def write_translated_paragraph(paragraph: Paragraph, translated_text: str) -> None:
    """
    DOCX-02 run-merge write-back.
    NEVER calls paragraph.text = value (destroys all run formatting per CLAUDE.md anti-pattern).
    Only touches <w:t> inside existing <w:r> elements; <w:rPr> is preserved intact.
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(_nfc(translated_text))
        return
    runs[0].text = _nfc(translated_text)   # only <w:t> touched, <w:rPr> preserved
    for run in runs[1:]:
        run.text = ""                       # blank text but keep <w:r> element


def reassemble_docx(
    doc: Document,
    segments: list[Segment],
    translated_texts: dict[str, str],  # segment_id -> translated_text
) -> Document:
    """
    Write translated text back into the document using run-merge strategy.
    translated_texts is keyed by segment.id (D-06 sha256 ID).
    """
    seq = 0
    for _, paragraph in _walk_doc_for_reassembly(doc):
        text = paragraph.text
        if not text.strip():
            continue
        if seq < len(segments):
            seg = segments[seq]
            translated = translated_texts.get(seg.id)
            if translated:
                write_translated_paragraph(paragraph, translated)
        seq += 1
    return doc


def _walk_doc_for_reassembly(doc: Document):
    """Mirror of walk_document() for write-back. Must visit in same order as extraction."""
    from app.pipeline.docx.extractor import walk_document
    yield from walk_document(doc)
```

`backend/src/app/pipeline/docx/tracked.py` (RESEARCH.md §4):
```python
from __future__ import annotations
from docx import Document


def has_tracked_changes(doc: Document) -> bool:
    """
    DOCX-04: Detect <w:ins> or <w:del> in the document body XML.
    Called on upload to determine whether to show the tracked-changes modal (D-13).
    """
    body_xml = doc._element.xml
    return "<w:ins" in body_xml or "<w:del" in body_xml


def strip_tracked_changes(doc: Document) -> Document:
    """
    D-13 strip option: remove tracked changes.
    - <w:ins>: move child <w:r> elements out, remove wrapper
    - <w:del>: remove entirely (deleted text is gone)
    Returns the modified document.
    """
    from lxml import etree
    from docx.oxml.ns import qn

    body = doc._element.body
    # Handle insertions: unwrap <w:ins>, keep children
    for ins in body.findall(f".//{qn('w:ins')}"):
        parent = ins.getparent()
        idx = list(parent).index(ins)
        for child in list(ins):
            parent.insert(idx, child)
            idx += 1
        parent.remove(ins)

    # Handle deletions: remove entirely
    for del_elem in body.findall(f".//{qn('w:del')}"):
        del_elem.getparent().remove(del_elem)

    return doc
```

For golden fixtures: create them programmatically in a test conftest fixture or in the test files:
```python
# In test_docx_extractor.py
import pytest
from docx import Document

@pytest.fixture(scope="module")
def simple_docx(tmp_path_factory):
    doc = Document()
    doc.add_paragraph("Hello world")
    doc.add_paragraph("This is paragraph two")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Cell A1"
    table.cell(0, 1).text = "Cell B1"
    table.cell(1, 0).text = "Cell A2"
    table.cell(1, 1).text = "Cell B2"
    path = tmp_path_factory.mktemp("fixtures") / "simple.docx"
    doc.save(str(path))
    return path
```

Save static fixtures to backend/tests/pipeline/fixtures/ using python-docx in a setup script.
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      uv run pytest tests/pipeline/test_docx_extractor.py tests/pipeline/test_tracked_changes.py -v --no-header 2>&amp;1 | tail -10
    </automated>
  </verify>
  <done>
    All DOCX extractor and tracked-changes tests pass.
    walk_document uses iter_inner_content() not doc.paragraphs.
    write_translated_paragraph uses runs[0].text = ..., not paragraph.text = ...; bold preserved after write-back.
    has_tracked_changes detects <w:ins> and <w:del> in XML.
    strip_tracked_changes removes <w:del> elements and unwraps <w:ins> elements.
    extract_segments assigns sequential seq_in_job and stable SHA IDs.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| User DOCX → pipeline | Untrusted XML from uploaded document; lxml parsing |
| lxml tree manipulation | strip_tracked_changes mutates document XML; must not corrupt structure |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-04-01 | Tampering | lxml tree manipulation in strip_tracked_changes | mitigate | Only operates on <w:ins>/<w:del> elements; tested with golden fixtures; source file preserved separately at input_path |
| T-04-02 | Denial of Service | walk_document on adversarially-nested DOCX | accept | PoC scope — no external users; recursion on nested tables is bounded by practical DOCX document depth |
| T-04-03 | Tampering | placeholder restoration — missing marker | mitigate | Fallback: keeps ⟦T{n}⟧ marker visible in output (error surfaced to reviewer, not silently dropped) |
| T-04-04 | Information Disclosure | source_text in Segment | accept | Internal PoC; segments stored in DB for Phase 2 review UI |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/pipeline/ -v` — all tests pass
2. `grep -q "paragraph.text =" backend/src/app/pipeline/docx/reassembler.py` — returns nothing (anti-pattern absent)
3. `grep -q "iter_inner_content" backend/src/app/pipeline/docx/extractor.py` — passes
4. `grep -q "doc.paragraphs" backend/src/app/pipeline/docx/extractor.py` — returns nothing (misuse absent)
5. `grep -q "⟦T" backend/src/app/pipeline/placeholder.py` — passes (placeholder pattern present)
</verification>

<success_criteria>
- All pipeline unit tests pass (min 15 tests across 3 test files)
- write_translated_paragraph writes into runs[0].text only, never calls paragraph.text setter
- walk_document visits table cells via iter_inner_content(), not doc.paragraphs
- extract_placeholders replaces all 7 pattern categories with ⟦T{n}⟧ markers
- restore_placeholders leaves no ⟦T{n}⟧ markers in the output
- has_tracked_changes returns True for docs with <w:ins> or <w:del> XML
- Segment.from_text generates deterministic 16-char hex IDs via sha256
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-04-SUMMARY.md`
</output>
