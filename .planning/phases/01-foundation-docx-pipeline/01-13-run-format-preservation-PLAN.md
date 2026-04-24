---
phase: 01-foundation-docx-pipeline
plan: "13"
type: tdd
wave: 5
depends_on: []
files_modified:
  - backend/src/app/pipeline/segment.py
  - backend/src/app/pipeline/docx/extractor.py
  - backend/src/app/pipeline/docx/reassembler.py
  - backend/tests/pipeline/test_docx_extractor.py
  - backend/src/app/workers/translate_worker.py
autonomous: true
gap_closure: true
requirements:
  - DOCX-02
  - CORE-01

must_haves:
  truths:
    - "DOCX-02 run-merge preserves per-run character formatting (bold/italic/underline/color/font) across the full translated paragraph — not just the first run's formatting"
  artifacts:
    - path: "backend/src/app/pipeline/segment.py"
      provides: "RunSegment dataclass with run_index field, or Segment extended with optional run_index: int | None"
    - path: "backend/src/app/pipeline/docx/extractor.py"
      provides: "extract_run_segments() — one Segment per run group (consecutive same-format runs merged), preserving run_index"
    - path: "backend/src/app/pipeline/docx/reassembler.py"
      provides: "write_translated_run() — writes translated text back to original run slot by run_index"
    - path: "backend/tests/pipeline/test_docx_extractor.py"
      provides: "TDD fixture: paragraph with 3 distinct formatting runs, round-trip asserts each run's formatting intact"
  key_links:
    - from: "backend/src/app/pipeline/docx/extractor.py:extract_run_segments"
      to: "backend/src/app/pipeline/docx/reassembler.py:write_translated_run"
      via: "Segment.run_index identifies the target run slot"
      pattern: "paragraph\\.runs\\[seg\\.run_index\\]\\.text"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/pipeline/docx/extractor.py"
      via: "extract_run_segments() replaces extract_segments() for DOCX jobs"
      pattern: "extract_run_segments\\("
---

<objective>
Close UAT gap G2: the current run-merge strategy (`runs[0].text = translated; runs[1:].text = ""`) collapses multi-format paragraphs into a single run with the first run's formatting. A paragraph with bold+plain+italic runs becomes entirely bold after translation.

Root cause: the pipeline extracts one Segment per *paragraph*, translating the full paragraph text as a flat string. Reassembly writes into `runs[0]` and blanks the rest, destroying per-run formatting diversity.

Strategy chosen (from UAT analysis): **per-run segment extraction** — extract one Segment per *run group* (consecutive runs with identical formatting are merged to reduce LLM call count; format-change boundaries are split points). Translate each run group's text independently. Write translated text back into the original run slot by `run_index`.

Alternative strategy (document, defer): inline format markers `[[B:]]text[[/B:]]` passed through LLM — more complex parse, more fragile model behavior; deferred to Phase 2+ if per-run approach proves insufficient for cross-run technical terms.

Edge case accepted for PoC: technical terms that span multiple run-formatting-boundary runs (e.g., "text-embedding-ada-002" in italic+underline across 2 runs) will be translated per-run. The literal translation of each run segment may be partial-word in some cases — acceptable for the PoC; preserves formatting fidelity over semantic fidelity at run-boundary level.

Purpose: Every run in the translated DOCX carries its original `<w:rPr>` (bold/italic/underline/color/font) regardless of how many runs a paragraph contains.

Output: Updated `segment.py`, `extractor.py`, `reassembler.py`, expanded test file. Worker file updated to call `extract_run_segments` instead of `extract_segments` for DOCX jobs.
</objective>

## Cost Impact

Per-run segmentation multiplies DashScope call volume relative to paragraph-level
extraction. Documented bounds:

- **Worst case:** every run has distinct formatting → one Segment per run. A doc with N runs
  produces N Segments vs P paragraphs before (N >> P for richly formatted docs).
- **Best case:** all runs in a paragraph share formatting → merged into one Segment (no
  change from current behavior).
- **Typical case (ICOM_Proposal_JP.docx):** 346 paragraph-level segments observed today.
  Spot-check: most paragraphs have 1-3 uniform-format runs. Estimate ~400-500 run-level
  segments after per-run extraction — 15-45% more calls.
- **Mitigation:** the extractor merges consecutive runs with IDENTICAL formatting into
  ONE Segment before emitting. Format-change boundaries are the only split points.
- **Pace budget:** at DASHSCOPE_PACE_SECONDS=1.2 default, a 500-segment doc needs
  ~10 min wall-clock (vs ~7 min today). Acceptable for PoC; paid-tier bumps pace to 0.2s
  which recovers parity.

Accepted trade-off per D-13 (format fidelity over raw throughput).

<execution_context>
@$HOME/.claire/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-foundation-docx-pipeline/01-UAT.md
@.planning/phases/01-foundation-docx-pipeline/01-04-SUMMARY.md

<interfaces>
<!-- Current Segment dataclass (backend/src/app/pipeline/segment.py) -->
```python
@dataclass
class Segment:
    id: str              # 16-char hex (D-06)
    seq_in_job: int
    source_text: str
    structural_position: str
    is_comment: bool = False
    is_inserted: bool = False
    is_deleted: bool = False
    translated_text: str | None = None
```

<!-- Current extract_segments signature (backend/src/app/pipeline/docx/extractor.py) -->
```python
def extract_segments(doc: Document, job_id: str) -> list[Segment]:
    # One Segment per paragraph (skipping empty)
    # structural_position = f"{loc_tag}.{seq}"
```

<!-- Current write_translated_paragraph (backend/src/app/pipeline/docx/reassembler.py) -->
```python
def write_translated_paragraph(paragraph: Paragraph, translated_text: str) -> None:
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(_nfc(translated_text))
        return
    runs[0].text = _nfc(translated_text)  # BUG: collapses all formatting to runs[0]
    for run in runs[1:]:
        run.text = ""
```

<!-- python-docx Run formatting attributes -->
```python
# run.bold: bool | None  (True/False/None=inherit)
# run.italic: bool | None
# run.underline: bool | None
# run.font.color.rgb: RGBColor | None
# run.font.name: str | None
# run.font.size: Pt | None
# run._r: the lxml <w:r> element — use run._r.get_or_add_rPr() for direct XML access
```

<!-- python-docx run formatting comparison helper -->
```python
def _run_fmt(run) -> tuple:
    """Returns a tuple identifying the run's formatting — use for merge-group detection."""
    return (
        run.bold,
        run.italic,
        run.underline,
        str(run.font.color.rgb) if run.font.color and run.font.color.type else None,
        run.font.name,
        run.font.size,
    )
```
</interfaces>
</context>

<feature>
  <name>Per-run segment extraction with format-boundary splitting</name>
  <files>
    backend/src/app/pipeline/segment.py,
    backend/src/app/pipeline/docx/extractor.py,
    backend/src/app/pipeline/docx/reassembler.py,
    backend/tests/pipeline/test_docx_extractor.py
  </files>
  <behavior>
    Given a paragraph with 3 runs: [bold "Hello "], [plain "world"], [italic+underline "end"]
    - extract_run_segments() returns 3 Segments (one per run group — none merge since formats differ)
    - Each Segment has run_index=0, run_index=1, run_index=2 respectively
    - Segment.source_text for index 0 = "Hello ", index 1 = "world", index 2 = "end"
    - After translate + write_translated_run():
      - paragraph.runs[0].text = translated_0; paragraph.runs[0].bold == True
      - paragraph.runs[1].text = translated_1; paragraph.runs[1].bold is None (plain)
      - paragraph.runs[2].text = translated_2; paragraph.runs[2].italic == True, paragraph.runs[2].underline == True

    Given a paragraph with 3 runs all bold: [bold "A"], [bold "B"], [bold "C"]
    - extract_run_segments() returns 1 Segment (all three runs merged — same format)
    - Segment.run_index = 0 (first run of the group)
    - Segment.run_group_size = 3 (reassembler writes into runs[0], blanks runs[1:2])
    - After write_translated_run(): runs[0].text = translated; runs[1].text = ""; runs[2].text = ""; all three still bold

    Given a paragraph with 0 runs (text only):
    - extract_run_segments() returns 1 Segment with run_index=None
    - write_translated_run() falls back to paragraph.add_run(translated_text)

    Given a paragraph with runs that all have empty text (whitespace-only):
    - extract_run_segments() returns [] (same skip logic as extract_segments)

    Empty translated_texts dict (no translation for a segment):
    - reassemble_docx_runs() leaves that paragraph's runs untouched
  </behavior>
  <implementation>
    ## Step 1: Extend Segment (segment.py)

    Add two optional fields to the Segment dataclass (with defaults to preserve backward compat with existing tests and extract_segments callers):
    ```python
    run_index: int | None = None        # which run slot in the paragraph this segment maps to
    run_group_size: int = 1             # how many consecutive same-format runs this segment covers
    ```

    ## Step 2: Add run-format grouping helper (extractor.py)

    Add private function `_run_format_key(run)` returning a tuple:
    ```python
    def _run_format_key(run) -> tuple:
        color = None
        try:
            from docx.dml.color import ColorFormat  # noqa: PLC0415
            if run.font.color and run.font.color.type is not None:
                color = str(run.font.color.rgb)
        except Exception:
            pass
        return (run.bold, run.italic, run.underline, color, run.font.name, run.font.size)
    ```

    ## Step 3: Add extract_run_segments() (extractor.py)

    New public function alongside the existing `extract_segments()`:
    ```python
    def extract_run_segments(doc: Document, job_id: str) -> list[Segment]:
        """
        Like extract_segments() but splits at run-format boundaries within each paragraph.
        Consecutive runs with identical formatting are merged into one Segment (cost optimization).
        Each Segment carries run_index (first run in group) and run_group_size.
        Falls back to paragraph-level extraction for paragraphs with no runs.
        """
    ```

    Algorithm per paragraph:
    1. Get `paragraph.runs` — if empty: emit one Segment with `run_index=None` (same as existing extract_segments for runless paras).
    2. Group consecutive runs by `_run_format_key()`. For each group:
       a. Concatenate run texts → group_text
       b. If group_text.strip() is empty → skip (no Segment)
       c. Emit `Segment.from_text(source_text=_nfc(group_text), structural_position=f"{loc_tag}.{seq}.run{first_run_idx}", seq_in_job=seq, run_index=first_run_idx, run_group_size=len(group))`
       d. Increment seq counter

    CRITICAL: Do NOT remove or modify `extract_segments()` — the existing paragraph-level function must remain for backward compat with existing tests and any callers that don't need per-run granularity.

    ## Step 4: Add write_translated_run() (reassembler.py)

    New public function alongside the existing `write_translated_paragraph()`:
    ```python
    def write_translated_run(paragraph: Paragraph, seg: Segment, translated_text: str) -> None:
        """
        Write translated_text into the specific run slot identified by seg.run_index.
        If run_index is None: falls back to write_translated_paragraph() (no-runs para).
        Validates run_index < len(paragraph.runs) before writing (T-13-01 mitigation).
        Blanks runs[run_index+1 : run_index+run_group_size] to clear the merged group.
        """
    ```

    Safety check (T-13-01): if `seg.run_index >= len(paragraph.runs)`, log a warning and skip — do NOT raise. This handles the case where the document was modified between extraction and reassembly.

    ## Step 5: reassemble_docx_runs() — walk-order matching

    Uses the SAME counter-walk pattern as existing reassemble_docx(). Do NOT parse
    structural_position strings to group segments by paragraph — that fails on cell_para vs
    para location tags, and the format isn't stable across nested structures.

    Algorithm:

    1. Group incoming `list[Segment]` by walk-order paragraph position. Segments emitted by
       extract_run_segments() arrive in document order. Each Segment has `run_index` (the
       first run it covers) and `run_group_size` (how many consecutive runs it spans).
    2. Maintain a `para_seq` counter while walking document via walk_document() in the
       SAME order as extract_run_segments().
    3. For each non-empty paragraph visited, peek at the segments list head: if next
       segment(s) belong to this paragraph (their walk position == current para_seq), pop
       them all off into a paragraph_segments list, then call write_translated_run(paragraph,
       paragraph_segments, translated_texts) once per paragraph.
    4. write_translated_run() iterates the paragraph's runs: for each Segment in
       paragraph_segments, write translated_text into runs[segment.run_index], then blank
       runs[run_index+1 : run_index+run_group_size].
    5. Never call paragraph.text setter (DOCX-02 anti-pattern). Always mutate specific run.text.

    Bounds validation (threat model): before writing to runs[run_index], assert
      0 <= run_index < len(paragraph.runs) AND
      run_index + run_group_size <= len(paragraph.runs)
    If fails, log warning and skip this segment (prevents IndexError crashing the worker on
    malformed docs).

    New public function alongside existing `reassemble_docx()`:
    ```python
    def reassemble_docx_runs(
        doc: Document,
        segments: list[Segment],
        translated_texts: dict[str, str],
    ) -> Document:
        """
        Variant of reassemble_docx() that uses write_translated_run() to preserve
        per-run formatting. segments must have come from extract_run_segments().
        Uses sequential walk-order counter matching, NOT structural_position string parsing.
        """
    ```

    ## Step 6: Update translate_worker.py

    In `translate_worker.py`, replace the call to `extract_segments(doc, job.id)` with `extract_run_segments(doc, job.id)` for the DOCX branch, and replace `reassemble_docx(...)` with `reassemble_docx_runs(...)`.

    Import both new functions:
    ```python
    from app.pipeline.docx.extractor import extract_run_segments
    from app.pipeline.docx.reassembler import reassemble_docx_runs
    ```

    Do NOT remove the old imports — other tests still reference `extract_segments` and `reassemble_docx` directly.

    ## TDD cycle
    RED → GREEN → REFACTOR as per tdd.md. Each commit is atomic.
  </implementation>
</feature>

<tasks>

<task type="tdd">
  <name>RED: Write failing tests for per-run extraction and run-slot write-back</name>
  <files>backend/tests/pipeline/test_docx_extractor.py</files>
  <read_first>
    - backend/tests/pipeline/test_docx_extractor.py (full file — existing fixtures, test patterns, import style)
    - backend/src/app/pipeline/segment.py (current Segment fields — need to see which fields exist)
    - backend/src/app/pipeline/docx/extractor.py (current extract_segments signature)
    - backend/src/app/pipeline/docx/reassembler.py (current write_translated_paragraph)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, second gap — exact failure description: "text-embedding-ada-002 or equivalent need to underline and italic but translated document it became normal")
  </read_first>
  <behavior>
    Test: test_extract_run_segments_multi_format_paragraph
    - Build a Document with one paragraph containing 3 runs:
        run0: bold=True, text="Bold text "
        run1: bold=None (plain), italic=None, text="plain text "
        run2: italic=True, underline=True, text="italic-underline"
    - Call extract_run_segments(doc, "job1")
    - Assert: len(segments) == 3
    - Assert: segments[0].source_text == "Bold text "
    - Assert: segments[0].run_index == 0
    - Assert: segments[1].source_text == "plain text "
    - Assert: segments[1].run_index == 1
    - Assert: segments[2].source_text == "italic-underline"
    - Assert: segments[2].run_index == 2

    Test: test_extract_run_segments_uniform_format_merges
    - Build a Document with one paragraph containing 3 runs all bold:
        run0: bold=True, text="A"
        run1: bold=True, text="B"
        run2: bold=True, text="C"
    - Call extract_run_segments(doc, "job1")
    - Assert: len(segments) == 1
    - Assert: segments[0].source_text == "ABC"
    - Assert: segments[0].run_index == 0
    - Assert: segments[0].run_group_size == 3

    Test: test_write_translated_run_preserves_formatting
    - Build a Document with one paragraph containing 3 distinct-format runs (bold / plain / italic+underline)
    - Call write_translated_run(paragraph, seg_at_index_2, "translated_end")
    - Assert: paragraph.runs[2].text == "translated_end"
    - Assert: paragraph.runs[2].italic is True
    - Assert: paragraph.runs[2].underline is True
    - Assert: paragraph.runs[0].text unchanged (still "Bold text " or whatever was set)
    - Assert: paragraph.runs[0].bold is True (formatting not destroyed by writing run 2)

    Test: test_write_translated_run_run_index_out_of_bounds_skips
    - Build a Document with 1-run paragraph
    - Create a Segment with run_index=99
    - Assert: write_translated_run(paragraph, seg, "text") does NOT raise
    - Assert: paragraph.runs[0].text is unchanged

    Test: test_reassemble_docx_runs_round_trip
    - Build a Document with one paragraph: [bold "Hello "], [plain "world"], [italic "end"]
    - Extract with extract_run_segments(doc, "j1") → 3 segments
    - Build translated_texts = {seg.id: f"TRANS_{i}" for i, seg in enumerate(segs)}
    - Call reassemble_docx_runs(doc, segs, translated_texts)
    - Assert: paragraph.runs[0].text == "TRANS_0"; runs[0].bold is True
    - Assert: paragraph.runs[1].text == "TRANS_1"; runs[1].bold is None (plain)
    - Assert: paragraph.runs[2].text == "TRANS_2"; runs[2].italic is True
  </behavior>
  <action>
Add the 5 test functions to `test_docx_extractor.py` importing `extract_run_segments` from `app.pipeline.docx.extractor` and `write_translated_run`, `reassemble_docx_runs` from `app.pipeline.docx.reassembler`.

At this RED stage, the imports will fail with ImportError — that is the correct RED state.

Run to confirm RED:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/test_docx_extractor.py -x -q 2>&1 | tail -15
```
Confirm output contains "ImportError" or "ModuleNotFoundError" or "AttributeError" for the new symbols. Commit: `test(docx): add failing tests for per-run segment extraction`
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/test_docx_extractor.py -x -q 2>&1 | grep -E "ERROR|FAILED|ImportError|error" | head -10</automated>
  </verify>
  <done>New test functions exist in test_docx_extractor.py AND pytest exits non-zero (RED confirmed)</done>
</task>

<task type="tdd">
  <name>GREEN: Implement per-run extraction + run-slot write-back</name>
  <files>
    backend/src/app/pipeline/segment.py,
    backend/src/app/pipeline/docx/extractor.py,
    backend/src/app/pipeline/docx/reassembler.py,
    backend/src/app/workers/translate_worker.py
  </files>
  <read_first>
    - backend/src/app/pipeline/segment.py (add run_index and run_group_size fields)
    - backend/src/app/pipeline/docx/extractor.py (add _run_format_key, extract_run_segments)
    - backend/src/app/pipeline/docx/reassembler.py (add write_translated_run, reassemble_docx_runs)
    - backend/src/app/workers/translate_worker.py (update import + call site for DOCX branch)
    - backend/tests/pipeline/test_docx_extractor.py (RED tests — must pass after this task)
  </read_first>
  <action>
Implement in this exact order to satisfy all RED tests:

### 1. segment.py — add optional fields (backward compat required)
```python
run_index: int | None = None      # run slot in paragraph (None = paragraph-level segment)
run_group_size: int = 1           # consecutive same-format runs merged into this segment
```
The `from_text` factory passes `**kwargs` so run_index and run_group_size can be injected without changing the factory signature.

### 2. extractor.py — add _run_format_key() and extract_run_segments()

`_run_format_key(run)` — returns (bold, italic, underline, color_str_or_None, font_name, font_size).
Color: access via `run.font.color.type` first (avoids AttributeError when color is unset); use `str(run.font.color.rgb)` only when type is not None.

`extract_run_segments(doc, job_id)`:
- Same walk_document() traversal as extract_segments()
- Per paragraph:
  - runs = paragraph.runs
  - If no runs: emit one Segment with run_index=None (NFC source = paragraph.text, skip if blank)
  - Otherwise: group consecutive runs by _run_format_key()
    - For each group: concatenate texts → if blank, skip; else emit Segment with run_index=group_start_idx, run_group_size=len(group)
- structural_position for run-level segments: `f"{loc_tag}.{para_seq}.run{first_run_idx}"`
  (para_seq is a running counter per document walk, same as extract_segments' seq)

CRITICAL: Do NOT modify extract_segments(). Both functions must coexist.

### 3. reassembler.py — add write_translated_run() and reassemble_docx_runs()

`write_translated_run(paragraph, seg, translated_text)`:
```python
if seg.run_index is None:
    write_translated_paragraph(paragraph, translated_text)  # fallback
    return
runs = paragraph.runs
if seg.run_index >= len(runs):
    import logging; logging.getLogger(__name__).warning(
        "write_translated_run: run_index %d out of bounds (para has %d runs) — skipping",
        seg.run_index, len(runs)
    )
    return
runs[seg.run_index].text = _nfc(translated_text)
end = min(seg.run_index + seg.run_group_size, len(runs))
for r in runs[seg.run_index + 1 : end]:
    r.text = ""
```

`reassemble_docx_runs(doc, segments, translated_texts)`:
- Use a sequential `para_seq` counter while walking document via `walk_document()`
  in the SAME order as `extract_run_segments()`. Do NOT parse `structural_position`
  strings — same pattern as existing `reassemble_docx()` counter-walk.
- For each non-empty paragraph visited, peek at the head of the segments list; pop
  all segments whose walk-position matches the current `para_seq` into
  `paragraph_segments`.
- For each segment in `paragraph_segments`, call `write_translated_run()` if
  `translated_texts` has a value for `seg.id`.
- See Step 5 in the `<implementation>` block above for the governing algorithm.

### 4. translate_worker.py — update DOCX call site

Find the section that calls `extract_segments(doc, job.id)` and `reassemble_docx(...)`.
Replace with:
```python
from app.pipeline.docx.extractor import extract_run_segments
from app.pipeline.docx.reassembler import reassemble_docx_runs
# ...
segments = extract_run_segments(doc, job.id)
# ...
reassemble_docx_runs(doc, segments, translated_texts)
```
Keep old imports intact for other callers.

Run tests to confirm GREEN:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/test_docx_extractor.py -x -q 2>&1 | tail -15
```
Confirm all tests pass. Commit: `feat(docx): implement per-run segment extraction and run-slot write-back`
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/test_docx_extractor.py -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    All test_docx_extractor.py tests pass (0 failed) AND:
    - `grep -n "run_index" backend/src/app/pipeline/segment.py` shows the field
    - `grep -n "def extract_run_segments\|def _run_format_key" backend/src/app/pipeline/docx/extractor.py` shows both
    - `grep -n "def write_translated_run\|def reassemble_docx_runs" backend/src/app/pipeline/docx/reassembler.py` shows both
    - `grep -n "extract_run_segments\|reassemble_docx_runs" backend/src/app/workers/translate_worker.py` shows the updated call site
    - Existing extract_segments() still present: `grep -n "def extract_segments" backend/src/app/pipeline/docx/extractor.py`
  </done>
</task>

<task type="auto">
  <name>Task 3: Run full backend test suite; fix any regressions</name>
  <files>backend/tests/pipeline/test_docx_extractor.py</files>
  <read_first>
    - backend/src/app/pipeline/docx/extractor.py (final implementation)
    - backend/src/app/pipeline/docx/reassembler.py (final implementation)
  </read_first>
  <action>
Run full pipeline test suite:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/ -q 2>&1
```

If any existing test_docx_extractor.py tests fail because they call `write_translated_paragraph` and now expect different behavior — do NOT modify those tests. Instead, verify that `write_translated_paragraph` is still present and unchanged in reassembler.py. The new `write_translated_run` and `reassemble_docx_runs` are additive; nothing was removed.

If any test fails due to the new `run_index` / `run_group_size` fields on Segment — add them with `= None` / `= 1` defaults in `Segment.from_text`'s kwargs (they already go through **kwargs, so no change needed). Verify with:
```bash
grep -n "run_index\|run_group_size" backend/src/app/pipeline/segment.py
```

Run the complete backend test suite to check for wider regressions:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest -q 2>&1 | tail -20
```

Document any intentional deviations in SUMMARY.md.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/ -q 2>&1 | tail -10</automated>
  </verify>
  <done>
    - `uv run pytest tests/pipeline/ -q` exits 0 (all pipeline tests pass)
    - `uv run pytest -q` exits 0 or only pre-existing failures (no new regressions introduced by this plan)
    - Test count in tests/pipeline/test_docx_extractor.py is ≥ 21 (was 16 + 5 new)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| DOCX file → extractor | Attacker-controlled DOCX enters extract_run_segments() |
| segments list → reassembler | run_index derived from extraction; must be validated before array access |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-13-01 | Tampering | write_translated_run — run_index array access | mitigate | Validate `seg.run_index < len(paragraph.runs)` before writing; log warning and skip if out-of-bounds. Never raise — a malformed DOCX that shifts run counts between extraction and reassembly should produce a degraded (partially-translated) document, not a crash. |
| T-13-02 | Denial of Service | _run_format_key — color attribute access | mitigate | Wrap color access in try/except; fall back to `None` for color key. A malformed `<w:rPr>` that raises on `.rgb` access must not crash the extraction pipeline. |
| T-13-03 | Information Disclosure | translate_worker.py — new import path | accept | No new auth surface. extract_run_segments reads the same files as extract_segments; no new file paths or secrets accessed. |
</threat_model>

<verification>
Backend pipeline tests:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/pipeline/ -v 2>&1 | tail -30
```
Expected: all tests pass, new tests present.

Grep assertions:
```bash
# New fields on Segment
grep -n "run_index\|run_group_size" backend/src/app/pipeline/segment.py

# New functions in extractor
grep -n "def extract_run_segments\|def _run_format_key" backend/src/app/pipeline/docx/extractor.py

# New functions in reassembler
grep -n "def write_translated_run\|def reassemble_docx_runs" backend/src/app/pipeline/docx/reassembler.py

# Old functions still present (backward compat)
grep -n "def extract_segments\|def write_translated_paragraph\|def reassemble_docx" backend/src/app/pipeline/docx/extractor.py backend/src/app/pipeline/docx/reassembler.py

# Worker updated
grep -n "extract_run_segments\|reassemble_docx_runs" backend/src/app/workers/translate_worker.py
```
</verification>

<success_criteria>
- `Segment` dataclass has `run_index: int | None = None` and `run_group_size: int = 1` fields
- `extract_run_segments()` exists in extractor.py and is called by translate_worker.py for DOCX jobs
- `write_translated_run()` and `reassemble_docx_runs()` exist in reassembler.py
- Old `extract_segments()`, `write_translated_paragraph()`, `reassemble_docx()` are preserved unchanged
- 5 new tests pass: multi-format extraction (3 segments), uniform-format merge (1 segment), format-preserving write-back, out-of-bounds skip, round-trip round-trip
- All existing 43 pipeline tests still pass (0 regressions)
- `write_translated_run` validates run_index < len(runs) before array access
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-13-SUMMARY.md`
</output>
