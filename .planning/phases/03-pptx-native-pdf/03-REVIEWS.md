---
phase: 3
reviewers: [cursor]
reviewed_at: 2026-04-26T01:25:00+07:00
plans_reviewed:
  - 03-01-PLAN.md
  - 03-02-PLAN.md
  - 03-03-PLAN.md
  - 03-04-PLAN.md
  - 03-05-PLAN.md
  - 03-06-PLAN.md
  - 03-07-PLAN.md
unavailable_reviewers:
  - gemini (auth — needs GEMINI_API_KEY)
  - codex (broken install — missing @openai/codex-linux-x64)
  - claude (self — running inside Claude Code)
---

# Cross-AI Plan Review — Phase 3

## Cursor Review

Here is a structured cross-AI review of the Phase 3 plan set (03-01 through 03-07) as written, with light grounding from the current repo (e.g. `translate_batch` in `backend/src/app/llm/translator.py` matches the HTML probe's call shape; migration `0003` revision is `0003_segment_pk_run` per `backend/src/app/db/migrations/versions/0003_segment_compound_pk_run_fields.py`).

---

### 1. Summary

The seven plans form a **coherent end-to-end spine**: dependencies and enum extension (03-01) → TDD scaffolds (03-02) → PPTX and PDF pipelines (03-03, 03-04) → worker integration with `match`/`case` and `SegmentFlag` persistence (03-05) → frontend breadcrumbs and flags (03-06) → round-trips and coverage/frontend gates (03-07). **Research, CONTEXT decisions, and cross-file contracts** (structural positions, `reassemble_pptx` tuple return, `insert_htmlbox` + `scale_low=0.7`, redact ordering) are unusually well aligned. The main **gaps** are a few **test–intent mismatches** (e.g. "group" fixture without a real group), **flag semantics** (PPTX auto-fit vs overflow both using `FlagType.overflow` in 03-05), **incomplete coverage of roadmap success #1 (master text)**, and **residual risk** on HTML-in-translation and headless PPTX auto-fit that the plans already flag as assumption-driven.

---

### 2. Strengths

- **Clear wave ordering and dependencies**: 03-01/03-02 before implementation; 03-03+03-04 in parallel after 01+02; 03-05 after both pipelines; 03-06 can follow 01+02 in parallel to backend; 03-07 after 05+06 — sound.
- **Strong API and pitfall documentation**: PyMuPDF `clip`+`html`, `scale_low=0.7`, redact → `apply_redactions` → `insert_htmlbox` order, SmartArt before `has_text_frame` — these directly reduce implementation bugs.
- **Explicit cross-plan contracts**: `structural_position` schema (RESEARCH Q15), tuple `(Presentation, list[dict])` for PPTX, `overflow_flags` out-param for PDF, compound FK for flags — good for review and codegen.
- **Wave 0 empirical probes** (Noto `fc-list`, HTML tag survival) de-risk 03-04 before heavy PDF work; **no-DDL** migration for `native_enum=False` is accurate for a VARCHAR enum column.
- **Threat model** in multiple plans: corrupt files, `insert_htmlbox` failure, path scope — appropriate for a PoC.
- **Traceability to requirements** is mostly good; **03-VALIDATION** maps reqs → tests and commands.
- **Grounded probe**: `wave0_html_probe.py`'s use of `translate_batch(client, segments, source_lang, target_lang)` matches the current `translate_batch` signature in `backend/src/app/llm/translator.py` (lines 63–70).

---

### 3. Concerns (with severity)

| Severity | Concern |
|----------|---------|
| **MEDIUM** | **03-02 `group_pptx` fixture** (plan text): builds a **plain text box**, not a nested `GroupShape`, yet **`test_walk_shape_tree_group_recursion_finds_nested_text`** claims group recursion. The test can pass without ever executing the GROUP branch — **false confidence on PPTX-04**. |
| **MEDIUM** | **03-05 worker plan**: PPTX **`auto_adjusted`** cases persist **`FlagType.overflow`** (with `details.auto_adjusted: True`) for both overflow and "safe" auto-fit. **Roadmap** and **D-03-07** distinguish overflow badge vs auto-adjust; the review UI may need to **treat `details.auto_adjusted`** or risk **over-warning**. Same pattern for PDF (`overflow` + `auto_adjusted` in details). |
| **MEDIUM** | **ROADMAP success #1** includes **"master-slide text translated"**; **03-07 `full_pptx` round-trip** (as specified) has **text box, notes, table** but **no explicit master text segment** — end-to-end proof of master handling is **thin** unless 03-03 tests cover masters separately. |
| **MEDIUM** | **HTML strategy fork** (PRESERVED vs placeholder protection): **03-01 probe** uses **`translate_batch`**, which also runs **placeholder / token logic** (see `translator.py` top docstring). A verdict of **CORRUPted** might reflect **translation pipeline** behavior, not raw model HTML fidelity — could **mis-branch** 03-04 unless the probe is documented to mean "end-to-end segment path" or a **direct model** probe is added. |
| **LOW** | **03-01 `must_haves` / `requirements`**: plan tags **PPTX-02, PDF-04, LAYOUT-02, LAYOUT-03** for a plan that is **deps + enum + probes** — **no functional delivery** of those requirements in 03-01 alone; traceability is **confusing** for audits. |
| **LOW** | **Performance**: no tasks for **large** PDFs/PPTX (memory, per-page processing, or streaming); PoC-acceptable but **25 MB uploads** (UPLD-02) could still **OOM** a worker in worst cases. |
| **LOW** | **03-02 `test_empty_pptx`**: `Presentation()` **may or may not** match "zero slides" depending on `python-pptx` behavior; worth **verifying** so the test doesn't become **no-op** or **flaky**. |
| **LOW** | **03-01 Task 3**: `docker compose run --rm api` depends on **image build and Docker**; fallback to host `fc-list` is fine but **WSL/CI** may not match **runtime** — document that **Noto paths must be validated in the same image** that runs the API. |
| **LOW** | **Security**: plans rely on **outer worker `try/except`** and upload size; no explicit **per-page time budget** or **redaction of logs** for document snippets — acceptable for internal PoC. |

*No item rated **HIGH** for this PoC scope: risks are **correctness/UX/audit**-leaning, not obvious critical security gaps given stated boundaries.*

---

### 4. Suggestions (specific, actionable)

1. **03-02 — Fix the group test**: Build a real **nested `GroupShape`** (minimal OOXML) or use a **small committed fixture** with license noted — so **`test_walk_shape_tree_group_recursion_finds_nested_text`** actually requires **GROUP recursion** (PPTX-04).
2. **03-05 / 03-06 — Unify auto-adjusted semantics**: Either add **`FlagType` / UI handling** for "auto-adjusted only" (info, no overflow styling), or **strictly** define in **03-UI-SPEC** that **overflow badge** = `FlagType.overflow` **and** `details.auto_adjusted !== true` (and SegmentRow/FlagBadge follow that). Avoid ambiguous **double meaning** of `overflow`.
3. **03-07 — Align with success criterion #1**: Extend **`test_pptx_full_round_trip`** (or a sibling test) to assert **at least one `master.N...` segment** and **reopened text** in master/slide as appropriate — closes the **master** gap.
4. **03-01 Task 4 — Clarify the HTML probe**: In **`wave-0-html-probe.txt`**, record whether the verdict is **"after full `translate_batch`"**; if the team needs **raw model** tag survival, add a **minimal** `client.chat.completions` probe **or** a `translate_batch` option to bypass masking (only if you add such a path — this is a design note, not an instruction to change code in Ask mode).
5. **03-04 — `test_pdf_reassembler` / LAYOUT-02**: Plan's **`test_overflow_db_flag_persisted`** only checks **`isinstance(overflow_flags, list)`** — it does **not** assert DB persistence. Either **rename** to reflect "**out-param populated**" or add an **integration test with DB** under **`tests/`** (if you have patterns for async DB tests). Same for worker 03-05 vs **LAYOUT-02** wording.
6. **03-05 — `multi_column_degraded` for PDF**: The rule **"`col` not in position"** is **correct** for your extractor (degraded → `page.N.block.B`) vs non-degraded (`page.N.col.C.block.B`). **Add a one-line comment** in the worker when implementing to avoid a future "single-column as block-only" regression if clustering changes.
7. **Column clustering (03-04)**: The reference **`_find_gaps`** in RESEARCH/03-04 **differs** from a naive "gap midpoint" in edge cases; when implementing **`cluster_columns`**, keep **one canonical implementation** and **re-run 2-col/3-col tests** to avoid **false 2-col splits** (RESEARCH open question on uneven columns is already noted).

---

### 5. Risk assessment

**Overall: MEDIUM (justified for a 2–3 week internal PoC)**

- **Layout/PDF text**: PyMuPDF **html + redact + `insert_htmlbox`** is the right class of solution; **residual** risk is **real-world PDFs** (fonts, complex blocks, `rawdict` vs block alignment) — **MEDIUM** until golden PDFs are tested.
- **PPTX**: **Headless** auto-fit and **char-ratio proxy** (D-03-02) may **diverge** from PowerPoint's actual layout; **MEDIUM** for **demo risk**, mitigated by **flags + review UI**.
- **Integration**: **Worker 03-05** is a **single choke point**; mistakes there break all new formats — plan emphasis here is **appropriate**.
- **Coverage gate 80%** (03-07): Achievable if **`translate_worker`**, **error paths**, and **pdf/fonts** edge cases get tests; risk of a **late scramble** in 03-07 if new modules are large — **MEDIUM-LOW** if 03-02 scaffolds stay broad.

**LOW** areas: auth, multi-tenant, production ops — **explicitly** out of scope; plans match that.

---

### Roadmap success criteria (cross-check)

| # | Criterion (from your paste) | Plan coverage |
|---|-----------------------------|---------------|
| 1 | PPTX: boxes, notes, tables, master, lists, groups, SmartArt flagged | **Strong** for boxes/notes/tables/groups (if test fixed) / SmartArt; **weaker** on **master** in **E2E** (see above) |
| 2 | Overflow + badge + `TEXT_TO_FIT_SHAPE` when safe | **03-03, 03-05, 03-06**; **MEDIUM** concern on **flag type vs auto-adjusted** display |
| 3 | Native PDF: PyMuPDF, Noto, 2-col clustering | **03-01, 03-04, 03-05**; prove **2-col** with **synthetic** tests + ideally **one real PDF** in 03-02/07 (plan mentions arXiv — good if a **small** fixture is added where programmatic isn't enough) |
| 4 | PDF/segment unfit → flag; auto-scale recorded | **03-04** (`overflow_flags` + `scale_low=0.7`) + **03-05** + **03-06** orange/slate; **align** **overflow** vs **info** in UI |

---

### Closing note

The plan set is **execution-ready** with **above-average** internal consistency. The **highest-ROI fixes before coding** are: **honest PPTX group test**, **clarify overflow vs auto-adjusted in DB/UI contract**, and **tighten master + HTML probe semantics** so Phase 3 doesn't **pass tests** but **miss demo intent**.

*(Ask mode: only reviewed; no files were changed.)*

---

## Consensus Summary

> Single-reviewer mode (cursor only — gemini/codex unavailable). Treat findings as one strong signal rather than multi-AI consensus.

### Agreed Strengths
- Wave ordering + cross-plan contracts (tuple return, structural_position schema)
- Wave 0 empirical probes de-risking PDF work
- API pitfall documentation (PyMuPDF `scale_low=0.7`, redact ordering, SmartArt detection)

### Top Concerns (MEDIUM priority — actionable before /gsd-execute-phase)
1. **03-02 group fixture** builds plain text box, not nested `GroupShape` — `test_walk_shape_tree_group_recursion_finds_nested_text` can pass without exercising group branch (false PPTX-04 confidence)
2. **03-05 / 03-06 auto-adjusted vs overflow** semantics: both states use `FlagType.overflow` with `details.auto_adjusted` differentiator — UI must consume `details.auto_adjusted` flag to avoid over-warning
3. **03-07 master-slide E2E gap**: `full_pptx` round-trip lacks explicit master-text segment assertion despite ROADMAP success #1 naming master text
4. **03-01 HTML probe semantics**: probe runs through `translate_batch` (which has placeholder/token masking) — verdict may mis-attribute pipeline behavior to raw model HTML fidelity

### Divergent Views
- N/A (single reviewer)

### Recommended Action
Apply suggestions 1–4 (group fixture fix, auto-adjusted UI contract, master E2E assertion, HTML probe documentation) via `/gsd-plan-phase 3 --reviews`. Suggestions 5–7 are LOW priority / wording cleanups that can be folded in during execution.

---

## Resolution Status

**Applied by:** `/gsd-plan-phase 3 --reviews` (revision pass)
**Date:** 2026-04-26

### MEDIUM — Applied

| Item | Plan | Change Made |
|------|------|-------------|
| **M1** — fake group fixture | 03-02 Task 1 | Replaced plain text box with real lxml-injected `<p:grpSp>` OOXML element. Test now asserts `.group.` in `structural_position` — GROUP code path forced. |
| **M2** — overflow vs auto-adjusted contract | 03-05, 03-06, 03-02 Task 3, UI-SPEC | Documented inline comment at SegmentFlag insertion site (worker). FlagBadge Task 2 action updated with `details?.auto_adjusted` differentiation logic. Two new vitest cases added (test_flag_badge_overflow_auto_adjusted_renders_info, test_flag_badge_overflow_unfit_renders_warning). UI-SPEC flag table updated with auto-adjusted rendering rule. |
| **M3** — master text E2E gap | 03-07 Task 1 | `full_pptx` fixture writes text to `prs.slide_master.shapes.add_textbox`. `test_pptx_full_round_trip` asserts `master.` segments. New `test_pptx_master_text_round_trip` tests full master text round-trip (skips gracefully if fixture fails to write). must_haves truth added. |
| **M4** — HTML probe semantics | 03-01 Task 4 | Probe script replaced with dual-path version: PATH 1 = pipeline (`translate_batch` with masking) → `pipeline_verdict`; PATH 2 = raw model (direct API) → `raw_verdict`. Output file format updated. Plan 03-04 read_first notes to use `pipeline_verdict`. |

### LOW — Applied

| Item | Plan | Change Made |
|------|------|-------------|
| **L1** — requirements traceability | 03-01 frontmatter + must_haves | Added comment clarifying PPTX-02/PDF-04/LAYOUT-02/03 are precondition-only; full delivery in 03-03/03-04/03-05/03-06. |
| **L2** — canonical impl comment | 03-04 Task 1 | Added `# L2: Single canonical implementation — referenced by 03-VALIDATION.md PDF-04 tests` comment to `cluster_columns` docstring. Added VALIDATION.md to read_first. |
| **L3** — multi_column_degraded heuristic | 03-05 Task 1 | Added inline comment: `# 'col' absent in structural_position == degraded page (extractor writes page.N.block.B for degraded, page.N.col.C.block.B otherwise)`. |

### SKIP — Accepted

| Item | Reason |
|------|--------|
| Large-file performance / log redaction | Explicitly out of scope per CLAUDE.md PoC bounds |
| `test_empty_pptx` flakiness | Low risk; address only if goes red during execution |
| Docker/WSL Noto path mismatch | Already mitigated by host fallback; runtime container is source of truth |
