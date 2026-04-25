# Phase 3: PPTX + Native PDF — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 19 (new/modified)
**Analogs found:** 19 / 19

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `backend/src/app/pipeline/pptx/__init__.py` | module-init | — | `backend/src/app/pipeline/docx/__init__.py` | exact (empty) |
| `backend/src/app/pipeline/pptx/extractor.py` | parser | file-I/O → transform | `backend/src/app/pipeline/docx/extractor.py` | exact |
| `backend/src/app/pipeline/pptx/reassembler.py` | reassembler | transform → file-I/O | `backend/src/app/pipeline/docx/reassembler.py` | exact |
| `backend/src/app/pipeline/pptx/smartart.py` | utility | transform | `backend/src/app/pipeline/docx/extractor.py` (helper fns) | role-match |
| `backend/src/app/pipeline/pdf/__init__.py` | module-init | — | `backend/src/app/pipeline/docx/__init__.py` | exact (empty) |
| `backend/src/app/pipeline/pdf/extractor.py` | parser | file-I/O → transform | `backend/src/app/pipeline/docx/extractor.py` | exact |
| `backend/src/app/pipeline/pdf/reassembler.py` | reassembler | transform → file-I/O | `backend/src/app/pipeline/docx/reassembler.py` | exact |
| `backend/src/app/pipeline/pdf/columns.py` | utility | transform | `backend/src/app/pipeline/docx/extractor.py` (helper fns) | role-match |
| `backend/src/app/pipeline/pdf/fonts.py` | utility | config | `backend/src/app/pipeline/docx/extractor.py` (module-level helpers) | role-match |
| `backend/src/app/db/models.py` | data model | — | itself (extend in-place) | self |
| `backend/src/app/workers/translate_worker.py` | dispatcher | event-driven | itself (extend in-place) | self |
| `backend/pyproject.toml` | config | — | itself (extend in-place) | self |
| `backend/tests/pipeline/test_pptx_extractor.py` | test | — | `backend/tests/pipeline/test_docx_extractor.py` | exact |
| `backend/tests/pipeline/test_pptx_reassembler.py` | test | — | `backend/tests/pipeline/test_docx_extractor.py` | exact |
| `backend/tests/pipeline/test_pdf_extractor.py` | test | — | `backend/tests/pipeline/test_docx_extractor.py` | exact |
| `backend/tests/pipeline/test_pdf_reassembler.py` | test | — | `backend/tests/pipeline/test_docx_extractor.py` | exact |
| `backend/tests/pipeline/test_pdf_columns.py` | test | — | `backend/tests/pipeline/test_docx_extractor.py` | exact |
| `frontend/src/lib/formatBreadcrumb.ts` | utility/helper | transform | `frontend/src/lib/detectTrackedChanges.ts` | role-match |
| `frontend/src/__tests__/formatBreadcrumb.test.ts` | test | — | `frontend/src/__tests__/FlagBadge.test.tsx` | exact |
| `frontend/src/components/FlagBadge.tsx` | UI component | — | itself (extend 2 entries) | self |
| `frontend/src/components/SegmentRow.tsx` | UI component | — | itself (extend 3 record entries + breadcrumb render) | self |
| `frontend/src/components/UploadForm.tsx` | UI component | — | itself (surgical edits) | self |
| `frontend/src/lib/types.ts` | type definitions | — | itself (extend FlagType union) | self |

---

## Pattern Assignments

### `backend/src/app/pipeline/pptx/__init__.py` + `backend/src/app/pipeline/pdf/__init__.py`

**Analog:** `backend/src/app/pipeline/docx/__init__.py` (line 1 — empty)

Both new `__init__.py` files are empty markers, identical to the docx package init.

```python
# (empty — package marker only, matching docx/__init__.py)
```

---

### `backend/src/app/pipeline/pptx/extractor.py` (parser, file-I/O → transform)

**Analog:** `backend/src/app/pipeline/docx/extractor.py`

**Imports pattern** (lines 1-26 of analog):
```python
from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.pipeline.segment import Segment, make_segment_id
```

**Module docstring pattern** (lines 1-10 of analog):
```python
"""
PPTX presentation traversal and segment extraction.

PPTX-01: Full shape traversal — text boxes, speaker notes, tables, master slides.
PPTX-02: SmartArt shapes detected (is_smartart()) + flagged; not silently skipped.
PPTX-03: Overflow detection runs post-translate in reassembler.
PPTX-04: GroupShape walker recurses via walk_shape_tree().
D-06:    Segment ID is sha256(source_text + structural_position)[:16].
"""
```

**Core walker function shape** (mirrors `extract_run_segments` lines 111-185):
```python
def extract_pptx_segments(prs: Presentation, job_id: str) -> list[Segment]:
    """
    Walk the presentation and return an ordered Segment list.

    Walk order: master slides (once, deduplicated) → slides[N].shapes →
    notes_slide. Skips empty text. NFC-normalizes at extraction time (CORE-04).
    """
    segments: list[Segment] = []
    seq = [0]  # mutable int in list so nested helpers can increment

    # Master slides first (once per master, deduplicated by seg ID set)
    segments.extend(_extract_master_segments(prs, seq))

    for slide_idx, slide in enumerate(prs.slides):
        for seg in walk_shape_tree(slide.shapes, slide_idx, seq, f"slide.{slide_idx}"):
            segments.append(seg)
        segments.extend(_extract_notes_segments(slide, slide_idx, seq))

    return segments
```

**`_nfc` helper** (lines 28-30 of analog — copy verbatim):
```python
def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time."""
    return unicodedata.normalize("NFC", s)
```

**Empty-text guard** (lines 137-143 of analog):
```python
text = _nfc(para.text.strip())
if not text:
    continue
```

**Segment construction** (lines 143-152 of analog via `Segment.from_text`):
```python
segment = Segment.from_text(
    source_text=text,
    structural_position=pos,
    seq_in_job=seq[0],
)
seq[0] += 1
```

**Key deviation from DOCX analog:** Uses a mutable `seq = [0]` counter (list wrapping int) instead of a plain `seq = 0` integer, because nested helper functions (`walk_shape_tree`, `_extract_notes_segments`) must increment the same counter. DOCX extractor keeps `seq` local to a single flat loop.

---

### `backend/src/app/pipeline/pptx/smartart.py` (utility, transform)

**Analog:** `backend/src/app/pipeline/docx/extractor.py` — `_run_format_key` and `_nfc` helper pattern (lines 95-108)

These are small, focused module-level helper functions. Same pattern: pure function, no state, type-annotated.

**Function shape to copy:**
```python
# pipeline/docx/extractor.py lines 95-108 — pattern for pure helper functions
def _run_format_key(run) -> tuple:  # type: ignore[type-arg]
    """
    Return a tuple that identifies run formatting for merge-group detection.
    T-13-02: color access wrapped in try/except — a malformed <w:rPr> that raises
    on .rgb access must not crash the extraction pipeline.
    """
    color = None
    try:
        if run.font.color and run.font.color.type is not None:
            color = str(run.font.color.rgb)
    except Exception:  # noqa: BLE001
        pass
    return (run.bold, run.italic, run.underline, color, run.font.name, run.font.size)
```

Apply the same defensive `try/except` pattern for `is_smartart()` since lxml element access on malformed XML can raise.

**Concrete smartart.py shape:**
```python
from __future__ import annotations

SMARTART_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"


def is_smartart(shape) -> bool:  # type: ignore[type-arg]
    """
    Definitive SmartArt check. Primary: MSO_SHAPE_TYPE.IGX_GRAPHIC enum.
    Fallback: graphicData URI contains diagram namespace (malformed/edge-case PPTX).
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # noqa: PLC0415
    if shape.shape_type == MSO_SHAPE_TYPE.IGX_GRAPHIC:
        return True
    try:
        graphic_data = shape.element.findall(
            ".//{http://schemas.openxmlformats.org/drawingml/2006/main}graphicData"
        )
        return any(gd.get("uri") == SMARTART_URI for gd in graphic_data)
    except Exception:  # noqa: BLE001
        return False
```

---

### `backend/src/app/pipeline/pptx/reassembler.py` (reassembler, transform → file-I/O)

**Analog:** `backend/src/app/pipeline/docx/reassembler.py`

**Module docstring pattern** (lines 1-11 of analog):
```python
"""
PPTX reassembler — write translated text back into a Presentation.

PPTX pitfall: NEVER set paragraph.text = value — it calls paragraph.clear()
which destroys ALL <p:rPr> run formatting (bold, italic, font, color).
Same run-merge write-back as DOCX: para.runs[0].text = translated,
para.runs[1:].text = "" (keep <a:r> elements, change only <a:t>).
"""
```

**`write_translated_paragraph` shape** (lines 28-55 of analog — copy structure, adapt imports):
```python
def write_paragraph_runs(paragraph, translated_text: str) -> None:
    """
    PPTX run-merge write-back. Mirrors DOCX write_translated_paragraph exactly.
    python-pptx paragraph.runs returns list of Run objects with .text attribute.
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run().text = _nfc(translated_text)
        return
    runs[0].text = _nfc(translated_text)
    for run in runs[1:]:
        run.text = ""
```

**Main reassembler function shape** (lines 101-168 of analog):
```python
def reassemble_pptx(
    prs: Presentation,
    segments: list[Segment],
    translated_map: dict[str, str],
) -> Presentation:
    """
    Write translations back into prs in-place. Returns prs for symmetry with DOCX.
    SmartArt segments (.smartart suffix in structural_position) are SKIPPED (D-03-01).
    Overflow detection runs per shape after write-back (D-03-02, LAYOUT-03).
    """
    seg_by_pos = {s.structural_position: s for s in segments}
    for slide_idx, slide in enumerate(prs.slides):
        _write_back_shapes(slide.shapes, translated_map, seg_by_pos, f"slide.{slide_idx}")
    return prs
```

**Key deviation:** Position-keyed lookup (`seg_by_pos`) replaces the sequential walk-counter matching used in DOCX reassembler, because PPTX structural positions encode absolute coordinates (`slide.N.shape.M.tf.0.para.K`) rather than a sequential para index.

---

### `backend/src/app/pipeline/pdf/extractor.py` (parser, file-I/O → transform)

**Analog:** `backend/src/app/pipeline/docx/extractor.py`

**Imports pattern:**
```python
from __future__ import annotations

import unicodedata
from collections.abc import Iterator

import pymupdf

from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.segment import Segment, make_segment_id
```

**Main function shape** (mirrors `extract_run_segments` lines 111-185):
```python
def extract_pdf_segments(doc: pymupdf.Document, job_id: str) -> list[Segment]:
    """
    Walk all pages; extract text blocks; cluster columns; build Segment list.

    - Filters image blocks (type==1) — only text blocks (type==0) become Segments.
    - NFC-normalizes source_text at extraction time (CORE-04).
    - structural_position: page.N.col.C.block.B (2-col) or page.N.block.B (degraded).
    """
    segments: list[Segment] = []
    seq = [0]

    for page_num, page in enumerate(doc):
        blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
        column_groups, is_degraded = cluster_columns(blocks, page.rect.width)

        for col_idx, col_blocks in enumerate(column_groups):
            for block_idx, block in enumerate(col_blocks):
                raw = page.get_text("rawdict", clip=pymupdf.Rect(block["bbox"]))
                html = _spans_to_html(raw["blocks"][0] if raw["blocks"] else {})
                text = _nfc(html.strip())
                if not text:
                    continue
                pos = (
                    f"page.{page_num}.block.{block_idx}"
                    if is_degraded
                    else f"page.{page_num}.col.{col_idx}.block.{block_idx}"
                )
                segments.append(Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                ))
                seq[0] += 1

    return segments
```

**Empty-text guard, NFC, and Segment.from_text** — identical to DOCX extractor pattern.

---

### `backend/src/app/pipeline/pdf/reassembler.py` (reassembler, transform → file-I/O)

**Analog:** `backend/src/app/pipeline/docx/reassembler.py`

**Imports pattern:**
```python
from __future__ import annotations

import pymupdf

from app.pipeline.pdf.fonts import build_noto_archive_and_css
from app.pipeline.segment import Segment
```

**Main function shape** (mirrors `reassemble_docx` lines 170-199):
```python
def reassemble_pdf(
    doc: pymupdf.Document,
    segments: list[Segment],
    translated_map: dict[str, str],
    output_path: str,
) -> None:
    """
    Redact-reinsert per page. Critical ordering per RESEARCH.md Pitfall #3:
      1. add_redact_annot all blocks on a page
      2. apply_redactions (images=PDF_REDACT_IMAGE_NONE)
      3. insert_htmlbox for each block
    NEVER interleave steps 2 and 3.
    """
    arch, css = build_noto_archive_and_css()
    seg_by_pos = {s.structural_position: s for s in segments}
    ...
    doc.subset_fonts()
    doc.save(output_path, garbage=3, deflate=True)
```

**SegmentFlag insertion for overflow** — follows the `run_post_check` pattern from `backend/src/app/services/glossary_service.py`: build `SegmentFlag` objects with `segment_job_id` and `session.add_all(flags)`. The reassembler receives the session or returns a list of flag dicts for the caller (worker) to persist — same boundary as DOCX (reassembler is pure document mutation; DB writes owned by the worker).

---

### `backend/src/app/pipeline/pdf/columns.py` (utility, transform)

**Analog:** `backend/src/app/pipeline/docx/extractor.py` helper function pattern (lines 59-92)

Small, focused module with a single public function + private helper. No imports outside stdlib.

```python
# pipeline/docx/extractor.py lines 59-92 — helper function shape to mirror
def _walk_table(table: Table) -> Iterator[tuple[str, Paragraph]]:
    """
    Walk table cells in row-major order.
    Recurses into nested tables via cell.iter_inner_content().
    """
    for row in table.rows:
        for cell in row.cells:
            for block in cell.iter_inner_content():
                ...
```

`columns.py` has the same shape: pure function, takes typed inputs, returns typed outputs, private `_find_gaps` helper. No class, no state.

**Public API:**
```python
def cluster_columns(
    text_blocks: list[dict],
    page_width: float,
    gap_threshold: float = 0.30,
) -> tuple[list[list[dict]], bool]:
    """
    Returns (column_groups, is_degraded).
    column_groups: list of block lists per column (left-to-right order).
    is_degraded: True if 3+ columns or ambiguous — D-03-03.
    """
```

---

### `backend/src/app/pipeline/pdf/fonts.py` (utility, config)

**Analog:** module-level constant + single factory function (matches `_nfc` + `_run_format_key` pattern in docx/extractor.py)

```python
from __future__ import annotations

import pymupdf

NOTO_FONT_DIR = "/usr/share/fonts/truetype/noto"


def build_noto_archive_and_css() -> tuple[pymupdf.Archive, str]:
    """
    Build PyMuPDF Archive and @font-face CSS string for Noto fonts.
    Call once per reassembly job and pass arch+css into insert_htmlbox calls.
    Discovers exact filenames at runtime via fc-list (see Wave 0 task).
    """
    arch = pymupdf.Archive(NOTO_FONT_DIR)
    css = """
    @font-face { font-family: noto; src: url(NotoSans-Regular.ttf); }
    @font-face { font-family: noto; src: url(NotoSans-Bold.ttf); font-weight: bold; }
    @font-face { font-family: noto-cjk; src: url(NotoSansCJK-Regular.ttc); }
    * { font-family: noto, noto-cjk, sans-serif; }
    """
    return arch, css
```

**Wave 0 task:** Run `docker run --rm <image> fc-list | grep Noto` to discover exact filenames before hardcoding in this function.

---

### `backend/src/app/db/models.py` — extend `FlagType` enum

**Self-modification.** Lines 151-155 of the current file:

```python
# Current (lines 151-155):
class FlagType(str, enum.Enum):
    overflow = "overflow"
    glossary_violation = "glossary_violation"
    placeholder_mismatch = "placeholder_mismatch"
    llm_refusal = "llm_refusal"

# After Phase 3 — add two values:
class FlagType(str, enum.Enum):
    overflow = "overflow"
    glossary_violation = "glossary_violation"
    placeholder_mismatch = "placeholder_mismatch"
    llm_refusal = "llm_refusal"
    smartart = "smartart"
    multi_column_degraded = "multi_column_degraded"
```

`SegmentFlag` uses `SAEnum(FlagType, native_enum=False)` (line 235) — adding enum values requires an Alembic migration to extend the CHECK constraint values (or DROP+RECREATE the enum type in PostgreSQL). The migration file pattern matches `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py`.

---

### `backend/src/app/workers/translate_worker.py` — add `match job.input_format`

**Self-modification.** Lines 267-278 currently hardcode DOCX:

```python
# Current (lines 267-278) — the section to replace:
doc = Document(job.input_path)

# D-13: strip tracked changes before extraction if user chose strip
if job.has_tracked_changes and job.tracked_changes_action == "strip":
    doc = strip_tracked_changes(doc)

segments = extract_run_segments(doc, job_id)
```

**Replace with match/case dispatch block** (RESEARCH.md Q14 pattern):
```python
match job.input_format:
    case "docx":
        from app.pipeline.docx.extractor import extract_run_segments  # noqa: PLC0415
        from app.pipeline.docx.reassembler import reassemble_docx_runs  # noqa: PLC0415
        _doc = Document(job.input_path)
        if job.has_tracked_changes and job.tracked_changes_action == "strip":
            _doc = strip_tracked_changes(_doc)
        segments = extract_run_segments(_doc, job_id)
        ...
    case "pptx":
        ...
    case "pdf":
        ...
    case _:
        raise ValueError(f"Unsupported format: {job.input_format!r}")
```

The worker's `SegmentORM` persistence block (lines 306-334) and `run_post_check` call (lines 385-397) are **unchanged** — they operate on `list[Segment]` regardless of format. Only the parse and reassemble stages are dispatched by format.

---

## Test File Patterns

### `backend/tests/pipeline/test_pptx_extractor.py`

**Analog:** `backend/tests/pipeline/test_docx_extractor.py`

**Fixture pattern** (lines 29-46 of analog — programmatic, no binary files):
```python
@pytest.fixture(scope="module")
def simple_pptx(tmp_path_factory):
    """
    Simple PPTX with text box + speaker notes + 2×2 table.
    Programmatic — no binary commits.
    """
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    txBox = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    txBox.text_frame.text = "Hello PPTX"
    notes = slide.notes_slide.notes_text_frame
    notes.text = "Speaker note"
    table_shape = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1))
    table_shape.table.cell(0, 0).text = "Cell A"
    path = tmp_path_factory.mktemp("fixtures") / "simple.pptx"
    prs.save(str(path))
    return path
```

**Test function naming convention** (lines 95-215 of analog):
```
test_<function>_<scenario>_<expected>
# e.g.:
test_extract_pptx_segments_text_box_produces_segment
test_extract_pptx_segments_notes_produces_segment
test_walk_shape_tree_group_recursion_finds_nested_text
test_smartart_flagged_not_silently_skipped  # PPTX-02
```

**Round-trip test shape** (lines 290-325 of analog):
```python
def test_reassemble_pptx_identity_round_trip(simple_pptx):
    from pptx import Presentation
    from app.pipeline.pptx.extractor import extract_pptx_segments
    from app.pipeline.pptx.reassembler import reassemble_pptx
    prs = Presentation(str(simple_pptx))
    segments = extract_pptx_segments(prs, job_id="test-job")
    translated_map = {s.id: s.source_text for s in segments}  # identity
    reassemble_pptx(prs, segments, translated_map)
    # Verify text still present after round-trip
```

### `backend/tests/pipeline/test_pdf_extractor.py`, `test_pdf_reassembler.py`, `test_pdf_columns.py`

**Analog:** `backend/tests/pipeline/test_docx_extractor.py` (same fixture + test function structure)

**PDF fixture pattern** (RESEARCH.md Q16):
```python
@pytest.fixture(scope="module")
def single_col_pdf(tmp_path_factory):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello PDF world")
    path = tmp_path_factory.mktemp("fixtures") / "single.pdf"
    doc.save(str(path))
    return path
```

For 2-column PDF: store a small public-domain or self-generated arXiv-style PDF in `backend/tests/pipeline/fixtures/` as a tracked binary (< 50KB target).

**Column test assertions** (same style as line 170-172 of analog):
```python
def test_cluster_columns_single_col_returns_one_group(single_col_pdf):
    import pymupdf
    doc = pymupdf.open(str(single_col_pdf))
    blocks = [b for b in doc[0].get_text("dict")["blocks"] if b["type"] == 0]
    groups, is_degraded = cluster_columns(blocks, doc[0].rect.width)
    assert len(groups) == 1
    assert is_degraded is False
```

---

## Frontend Test Patterns

### `frontend/src/__tests__/formatBreadcrumb.test.ts`

**Analog:** `frontend/src/__tests__/FlagBadge.test.tsx` (lines 1-11)

```typescript
// FlagBadge.test.tsx — the stub/todo pattern to elevate to real tests:
import { describe, it, expect } from "vitest"

describe("FlagBadge", () => {
  it.todo("renders overflow badge with amber color class")
  ...
})
```

**Real test pattern for formatBreadcrumb:**
```typescript
import { describe, it, expect } from "vitest"
import { formatBreadcrumb } from "@/lib/formatBreadcrumb"

describe("formatBreadcrumb", () => {
  it("formats PPTX body position", () => {
    expect(formatBreadcrumb("slide.3.shape.1.tf.0.para.2")).toBe("Slide 3 / Shape 2 / ¶2")
  })
  it("formats PPTX notes position", () => {
    expect(formatBreadcrumb("slide.3.notes.para.1")).toBe("Slide 3 / Notes / ¶1")
  })
  it("formats PDF 2-col position", () => {
    expect(formatBreadcrumb("page.2.col.1.block.5")).toBe("Page 2 / Col 1 / Block 5")
  })
  it("formats PDF degraded position", () => {
    expect(formatBreadcrumb("page.2.block.7")).toBe("Page 2 / Block 7")
  })
  it("returns raw string for unknown format (fallback)", () => {
    const unknown = "unknown.format.string"
    expect(formatBreadcrumb(unknown)).toBe(unknown)
  })
})
```

---

## Shared Patterns

### Segment Construction (all new extractors)
**Source:** `backend/src/app/pipeline/segment.py` lines 45-60
**Apply to:** `pptx/extractor.py`, `pdf/extractor.py`
```python
segment = Segment.from_text(
    source_text=text,      # already _nfc() normalized
    structural_position=pos,
    seq_in_job=seq[0],     # mutable counter pattern for nested helpers
)
seq[0] += 1
```

### Run-Merge Write-Back (PPTX reassembler)
**Source:** `backend/src/app/pipeline/docx/reassembler.py` lines 28-55
**Apply to:** `pptx/reassembler.py` — identical pattern, `python-pptx` paragraph API is the same
```python
# NEVER: paragraph.text = translated  (destroys <p:rPr>)
# ALWAYS:
runs[0].text = _nfc(translated_text)
for run in runs[1:]:
    run.text = ""
```

### SegmentFlag Insertion (PDF/PPTX overflow + smartart flags)
**Source:** `backend/src/app/services/glossary_service.py` (run_post_check pattern) + `backend/src/app/db/models.py` lines 216-247
**Apply to:** worker's `_run_translation` after `reassemble_pptx`/`reassemble_pdf`

Critical: `SegmentFlag` requires `segment_job_id` (compound FK). The pattern from Phase 2:
```python
flag = SegmentFlag(
    segment_id=seg.id,
    segment_job_id=job_id,         # compound FK — NEVER omit this
    flag_type=FlagType.smartart,   # or FlagType.overflow / FlagType.multi_column_degraded
    severity=FlagSeverity.warn,
    details={"reason": "smartart_write_back_skipped"},
)
```

### NFC Normalization (all new extractors)
**Source:** `backend/src/app/pipeline/docx/extractor.py` lines 28-30
**Apply to:** `pptx/extractor.py`, `pdf/extractor.py`
```python
def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time."""
    return unicodedata.normalize("NFC", s)
```

### FlagBadge FLAG_CONFIG Extension
**Source:** `frontend/src/components/FlagBadge.tsx` lines 5-10
**Apply to:** `FlagBadge.tsx` (add 2 entries), `SegmentRow.tsx` (extend 3 parallel Records)

Current record shape to mirror exactly:
```typescript
// FlagBadge.tsx FLAG_CONFIG — copy this entry shape:
overflow: { label: "Overflow", className: "text-amber-600 bg-amber-50 border-amber-200" },

// New entries:
smartart:              { label: "SMART",     className: "text-orange-700 bg-orange-50 border-orange-200" },
multi_column_degraded: { label: "MULTI-COL", className: "text-slate-600 bg-slate-100 border-slate-300" },
```

```typescript
// SegmentRow.tsx — three parallel Records to extend (lines 11-43):
// FLAG_BADGE_STYLES — add:
smartart: "bg-orange-100 text-orange-800 border-orange-300",
multi_column_degraded: "bg-slate-100 text-slate-600 border-slate-300",

// FLAG_LABELS — add:
smartart: "SMART",
multi_column_degraded: "MULTI-COL",

// LEFT_BORDER — add:
smartart: "border-l-orange-500",
multi_column_degraded: "border-l-slate-400",
```

### FlagType Union Extension
**Source:** `frontend/src/lib/types.ts` line 57, `frontend/src/lib/review-types.ts` lines 5-9
**Apply to:** Both files (both define `FlagType` — both must be extended)

```typescript
// types.ts line 57 (current):
export type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal"

// After Phase 3 (add to BOTH files):
export type FlagType =
  | "overflow"
  | "glossary_violation"
  | "placeholder_mismatch"
  | "llm_refusal"
  | "smartart"
  | "multi_column_degraded"
```

### UploadForm Surgical Edits
**Source:** `frontend/src/components/UploadForm.tsx` lines 17, 52-54, 72-74, 165-167, 200-201
**Apply to:** `UploadForm.tsx` (4 surgical string/constant changes + 1 guard)

```typescript
// Line 17 — ALLOWED_EXTS:
const ALLOWED_EXTS = new Set([".docx", ".pptx", ".pdf"])

// Line 52-54 — error message:
"Unsupported file type. Accepted formats: .docx, .pptx, .pdf"

// Line 72-74 — tracked changes guard (DOCX only):
const hasTC = ext === ".docx" ? await detectTrackedChanges(f) : false
setHasTrackedChanges(hasTC)

// Line 165-167 — drop zone idle text:
"Drop your document here — DOCX, PPTX, or native PDF"

// Line 200-201 — file input accept attribute:
accept=".docx,.pptx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/pdf"
```

### Breadcrumb Badge in SegmentRow Source Cell
**Source:** `frontend/src/components/SegmentRow.tsx` lines 150-155 (source cell div)
**Apply to:** `SegmentRow.tsx` — insert before the `{segment.source_text}` render

```tsx
{/* Source cell: monospace, read-only */}
<div
  className="flex-[40] py-2 px-2 text-xs font-mono text-[#111111] bg-slate-50 border-r border-slate-100 select-text min-h-[48px] whitespace-pre-wrap"
  style={{ fontFamily: "var(--font-pt-mono, monospace)" }}
>
  {/* Phase 3: breadcrumb badge above source text */}
  {segment.structural_position && (
    <span className="text-xs text-slate-400 font-mono mb-1 block select-none">
      {formatBreadcrumb(segment.structural_position)}
    </span>
  )}
  {segment.source_text}
</div>
```

Import `formatBreadcrumb` from `"@/lib/formatBreadcrumb"` at the top of the file.

### `formatBreadcrumb.ts` Pure Helper Shape
**Source:** `frontend/src/lib/detectTrackedChanges.ts` (pure exported function pattern)
**Apply to:** `frontend/src/lib/formatBreadcrumb.ts` (new file)

```typescript
// detectTrackedChanges.ts — shape to mirror (exported pure function, no state):
export async function detectTrackedChanges(file: File): Promise<boolean> { ... }

// formatBreadcrumb.ts follows same pattern but sync:
export function formatBreadcrumb(structuralPosition: string): string {
  if (structuralPosition.startsWith("slide.") || structuralPosition.startsWith("master.")) {
    return _formatPptx(structuralPosition)
  }
  if (structuralPosition.startsWith("page.")) {
    return _formatPdf(structuralPosition)
  }
  return _formatDocx(structuralPosition)
}
```

Detection prefix table (from RESEARCH.md Q15):
- `slide.` or `master.` → PPTX
- `page.` → PDF
- anything else → DOCX

Shape index is displayed 1-based (`shape_idx + 1`) per 03-UI-SPEC.md.

---

## Alembic Migration (new file)

**Analog:** `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py`

A new migration file `0004_flagtype_smartart_multi_column.py` is needed to extend the `FlagType` enum in PostgreSQL. The existing migration pattern:

```python
# 0003 — migration shape to copy (check actual file for exact op_core_migration pattern):
def upgrade() -> None:
    op.execute("ALTER TYPE flagtype ADD VALUE IF NOT EXISTS 'smartart'")
    op.execute("ALTER TYPE flagtype ADD VALUE IF NOT EXISTS 'multi_column_degraded'")

def downgrade() -> None:
    pass  # PostgreSQL cannot remove enum values without DROP/RECREATE
```

Note: `SAEnum(FlagType, native_enum=False)` in `SegmentFlag` (line 235 of models.py) means the enum is stored as VARCHAR, not as a PostgreSQL native ENUM type — so no DDL ALTER needed. Verify by checking the existing migration: if the flag column is VARCHAR with a CHECK constraint, update the CHECK constraint instead.

---

## No Analog Found

All files have analogs. None require purely greenfield invention.

---

## Pitfalls the Planner Must Surface in Task Descriptions

| Pitfall | File | Guard |
|---|---|---|
| `paragraph.text = value` destroys PPTX formatting | `pptx/reassembler.py` | Run-merge: `runs[0].text = translated`, `runs[1:].text = ""` |
| `insert_htmlbox` default `scale_low=0` never reports overflow | `pdf/reassembler.py` | Always pass `scale_low=0.7` |
| `apply_redactions` must precede `insert_htmlbox` on same page | `pdf/reassembler.py` | Per-page: all `add_redact_annot` → `apply_redactions` → all `insert_htmlbox` |
| `clip` ignored for `"html"` format | `pdf/extractor.py` | Use `page.get_text("rawdict", clip=bbox)` not `"html"` |
| SmartArt `has_text_frame` is False | `pptx/extractor.py` | Check `is_smartart(shape)` BEFORE `shape.has_text_frame` |
| PDF image blocks lack `"lines"` key | `pdf/extractor.py` | Filter: `[b for b in blocks if b["type"] == 0]` |
| `SegmentFlag` missing `segment_job_id` | worker dispatch | Always include `segment_job_id=job_id` in SegmentFlag constructor |
| Noto font filenames vary by Docker base | `pdf/fonts.py` | Wave 0 task: `fc-list \| grep Noto` in container |

---

## Metadata

**Analog search scope:** `backend/src/app/pipeline/`, `backend/src/app/db/`, `backend/src/app/workers/`, `backend/tests/pipeline/`, `frontend/src/components/`, `frontend/src/lib/`, `frontend/src/__tests__/`
**Files scanned:** 18 existing files
**Pattern extraction date:** 2026-04-25
