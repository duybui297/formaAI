# Phase 06: Render-Strategy Pipeline — Specification

**Created:** 2026-05-13
**Ambiguity score:** 0.132
**Requirements:** 8 locked

## Goal

Replace the single-shot PDF segment renderer with a named, ordered strategy chain so every translated cell terminates in an explicit, observable outcome — eliminating the `overflow warn (no reason)` bucket and making new failure modes addressable by adding strategies instead of patching the core loop.

## Background

Current state in `backend/src/app/pipeline/pdf/reassembler.py` (574 lines):

- One render path per segment: `add_redact_annot` → `apply_redactions` → `insert_htmlbox(scale_low=heuristic)`.
- `_estimate_max_fitting_scale` is a multi-line geometric heuristic (closed-form, not measured) that decides scale or skip.
- `_clip_rect_away_from_images` clips the right/bottom edges only.
- `_is_identity_translation` short-circuits identical translations.
- If the heuristic says "won't fit at `_MIN_ADAPTIVE_SCALE = 0.15`," the cell is skipped and flagged `overflow warn (no reason)` — frontend `FlagBadge` renders this opaquely.

Each phase since 03 has shipped a patch for one new failure mode (image collision in 3.1; cell extraction in 3.2; adaptive scale + multi-line geometry in 3.3). The next document surfaces the next failure mode. Job `e1dcbbf1` (ja→en) produced 450 cells in the `overflow warn (no reason)` bucket due to CJK→Latin 5–9× expansion at narrow cells.

DOCX/PPTX pipelines are NOT in this state:

- **DOCX** has no overflow logic — Word reflows paragraphs natively.
- **PPTX** has `detect_pptx_overflow()` + `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` auto-fit; reportedly almost-perfect in prior UAT.

The painful pipeline is PDF, because rendered glyph rects are frozen and translation expansion has no natural reflow path.

## Requirements

1. **Strategy Protocol**: A `RenderStrategy` Protocol exists with uniform `can_render(ctx) -> bool` + `render(ctx) -> RenderResult` interface.
   - Current: No Protocol; renderer logic inlined in `reassemble_pdf`.
   - Target: `RenderContext`, `RenderResult`, and `RenderStrategy` (Pydantic + `typing.Protocol`) defined in a new module `backend/src/app/pipeline/pdf/render_strategies/`. Each strategy is a small isolated class implementing the Protocol.
   - Acceptance: `pyright` clean; unit test asserts every shipped strategy class satisfies the Protocol; `pytest backend/tests/pipeline/pdf/render_strategies/` passes.

2. **Strategy Chain Dispatcher**: `reassemble_pdf` delegates each segment to a chain; the first strategy where `can_render` is True AND `render` succeeds wins.
   - Current: Inline single-path logic in `reassemble_pdf`.
   - Target: New `dispatch_render(ctx, chain) -> RenderResult` function iterates the chain in order, short-circuits on first success, returns the successful `RenderResult`. On full chain failure, returns `PRESERVE_SOURCE` result.
   - Acceptance: Unit test feeds a 3-strategy chain where strategy #2 succeeds; verifies dispatcher returns strategy #2 result and skips strategy #3. Integration test on a synthetic 1-page PDF asserts every segment has `strategy_used` set.

3. **Day-1 Strategy Set (IDENTITY, MATH_PASSTHROUGH, SHRINK_IN_PLACE, PRESERVE_SOURCE)**: Four strategies ship in the first plan; demo jobs route through them.
   - Current: Identity + math handled inline; shrink is heuristic; preserve-source is implicit "skip + flag."
   - Target: All four exist as named strategy classes. `SHRINK_IN_PLACE` uses measurement (Req 4), not heuristic. `PRESERVE_SOURCE` always succeeds and emits an `untranslated_overflow` flag.
   - Acceptance: Each strategy has ≥1 unit test (synthetic `RenderContext`). Integration test on job `7f958166` confirms every segment terminates in one of the 4 strategies.

4. **SHRINK_IN_PLACE uses Dry-Run Measurement (replaces heuristic)**: Scale selection is measured via `insert_htmlbox` on a scratch page, not estimated.
   - Current: `_estimate_max_fitting_scale` returns closed-form geometric estimate; PyMuPDF then accepts it as-is.
   - Target: SHRINK_IN_PLACE clones the source page into a scratch `pymupdf.Document` (via `insert_pdf(src_doc, from_page=N, to_page=N)`), calls `insert_htmlbox(rect, html, scale_low=s, scale_high=s)` over candidate scales `[0.7, 0.5, 0.3, 0.2, 0.15]`, and commits the first scale where `spare_height >= 0` on the real page. `_estimate_max_fitting_scale` is removed from the prod code path.
   - Acceptance: SHRINK_IN_PLACE unit test asserts the chosen scale is the largest of the candidate list that returns `spare_height >= 0`. Integration test on a known-overflow cell from job `e1dcbbf1` confirms strategy commits at a measured scale and no `overflow warn (no reason)` flag is emitted.

5. **Strategy Chain is config.json-driven**: The chain order is declared in `config.json` under `render_strategy_chain: [...]`; code ships a sensible default.
   - Current: No config knob; renderer behavior is hardcoded.
   - Target: `config.json` gains `render_strategy_chain: ["IDENTITY", "MATH_PASSTHROUGH", "SHRINK_IN_PLACE", "WRAP_MULTI_LINE", "EXPAND_VERTICAL", "RENDER_BELOW_RECT", "RENDER_IN_MARGIN", "PRESERVE_SOURCE"]` (or a subset matching what's implemented at SPEC time). The renderer reads this list at startup; missing strategy names cause a hard failure at boot.
   - Acceptance: Removing `SHRINK_IN_PLACE` from the config list causes job `e1dcbbf1` to route shrink-eligible cells directly to `PRESERVE_SOURCE`. Unknown strategy name in config fails app startup with a clear error.

6. **Observable Strategy Outcomes via `segment_flags.details.strategy_used`**: Every segment exposes which strategy rendered it.
   - Current: `segment_flags.details` tracks `overflow`, `auto_adjusted`, `char_ratio`, `image_collision`. No strategy attribution.
   - Target: New key `strategy_used: str` carries the strategy name. Optional `scale_applied: float` when SHRINK_IN_PLACE wins. `failure_reason: str` when PRESERVE_SOURCE wins.
   - Acceptance: After running job `7f958166`, every segment in `segment_flags` table has `strategy_used` populated; `SELECT strategy_used, COUNT(*) FROM segment_flags GROUP BY strategy_used` returns a non-empty histogram.

7. **Frontend FlagBadge migration**: Frontend renders `strategy_used` chip; legacy `overflow warn (no reason)` is gone.
   - Current: `FlagBadge` reads `flag_type=overflow, severity=warn` and shows opaque "overflow" badge.
   - Target: `FlagBadge` (or a sibling component) renders strategy chip with name + optional scale. Legacy `overflow warn (no reason)` flag is no longer emitted by backend; frontend no longer expects it.
   - Acceptance: After Phase 06 lands, frontend review UI on job `e1dcbbf1` shows a strategy chip on every segment with a flag; no segment shows the bare "overflow" chip. Frontend type-check passes with old flag type removed/aliased.

8. **Wallclock budget**: Strategy chain adds ≤ 30 seconds total wallclock on the largest demo job (`7f958166`, 1409 segments).
   - Current: Baseline wallclock for job `7f958166` reassemble step is the reference (measure during 06-01 spike before committing the budget).
   - Target: Total reassemble wallclock for job `7f958166` is ≤ baseline + 30s. SHRINK_IN_PLACE dry-runs dominate the new cost; chain dispatcher overhead is negligible.
   - Acceptance: A reproducible benchmark script in `backend/scripts/bench_reassemble.py` measures wallclock on job `7f958166` pre- and post-Phase 06 and asserts the delta is ≤ 30s. If delta exceeds 30s, plan 06-01 adds caching (scratch-page reuse across same-page cells) until budget is met.

## Boundaries

**In scope:**

- New module: `backend/src/app/pipeline/pdf/render_strategies/` with Protocol, RenderContext, RenderResult, dispatcher, and strategy classes.
- Refactor `reassemble_pdf` to use the dispatcher.
- Day-1 strategy classes: IDENTITY, MATH_PASSTHROUGH, SHRINK_IN_PLACE (with dry-run measurement), PRESERVE_SOURCE.
- Incremental strategies (separate plans): WRAP_MULTI_LINE, EXPAND_VERTICAL (with collision rule below), RENDER_BELOW_RECT (with fall-through behavior below), RENDER_IN_MARGIN.
- Scratch-page measurement helper.
- `config.json` `render_strategy_chain` parsing + startup validation.
- DB `segment_flags.details` schema additions: `strategy_used`, `scale_applied`, `failure_reason`.
- Frontend migration: strategy chip replaces opaque overflow badge.
- Per-strategy unit tests (≥ 1 per strategy).
- Integration tests on demo jobs: `7f958166`, `b425150a`, `e1dcbbf1`, `9fc558a0`, `0989b344`.
- Benchmark script enforcing the wallclock budget (Req 8).
- SPEC.md notes the Protocol is shaped so DOCX/PPTX could adopt it later (no code change in this phase).

**EXPAND_VERTICAL collision rule (locked):** A "neighbor" that blocks vertical growth = other active segment bboxes (in the same render pass) ∪ image_rects ∪ page bottom margin. EXPAND_VERTICAL shrinks/aborts when the proposed expanded rect would overlap any of these.

**RENDER_BELOW_RECT below-occupied behavior (locked):** When the space below the source rect is also occupied, RENDER_BELOW_RECT's `can_render` returns False — the chain falls through to RENDER_IN_MARGIN, then PRESERVE_SOURCE. Force-overlay and "push page content down" are explicitly excluded.

**Out of scope:**

- DOCX renderer changes — DOCX has natural paragraph reflow; no overflow problem to solve. Protocol is documented as future-extensible only.
- PPTX renderer changes — `detect_pptx_overflow` + `MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE` already work (almost-perfect in prior UAT). Touching them risks regression for zero demo benefit.
- OCR pipeline / scanned-PDF composer — separate code path; out of scope.
- Glyph-level replacement (per-char PDF content stream rewrite) — multi-week engineering; deferred to PoC v2.
- Cross-page text flow (translation spans pages) — deferred.
- D-2 (text formatting preservation: color/bold/italic/font family in translated PDF) — deferred to Phase 07.
- Speech-bubble OCR fallback for image-baked text in native PDFs — deferred.
- Per-doc-type chain policies (different chain order for academic papers vs slides) — config knob exists in `config.json`, but only one default chain ships; per-doc-type routing is not implemented.

## Constraints

- **PyMuPDF version**: pinned at `1.26.x` (project default). Scratch-page measurement relies on `insert_pdf` + `insert_htmlbox` semantics from 1.26.x; if a later major upgrade changes return-value contract, SHRINK_IN_PLACE must be re-validated.
- **Wallclock budget**: ≤ 30s overhead on `7f958166` (Req 8). If scratch-page-per-cell exceeds this, scratch reuse across same-page cells is mandatory before the phase can ship.
- **Memory budget**: Scratch documents must be `.close()`d after each measurement to avoid leaking on 1000+ segment jobs.
- **Backward DB compatibility**: New keys in `segment_flags.details` are additive (JSONB column). Existing rows from phases 1–04 remain valid; reading code must tolerate missing `strategy_used` for legacy rows.
- **Config validation at boot**: Unknown or duplicated strategy names in `render_strategy_chain` cause a hard startup failure; no silent fallback to defaults.
- **Frontend compatibility**: Frontend migration is part of this phase (plan 06-05); backend and frontend land together. No alias period — old `overflow warn (no reason)` flag is removed.

## Acceptance Criteria

- [ ] `RenderStrategy` Protocol + `RenderContext` + `RenderResult` exist in `backend/src/app/pipeline/pdf/render_strategies/` and pyright is clean.
- [ ] Strategy chain dispatcher routes each segment to the first matching strategy; unit test verifies short-circuit behavior.
- [ ] Day-1 strategies (IDENTITY, MATH_PASSTHROUGH, SHRINK_IN_PLACE, PRESERVE_SOURCE) ship with ≥ 1 unit test each.
- [ ] SHRINK_IN_PLACE uses dry-run measurement via scratch `pymupdf.Document`; `_estimate_max_fitting_scale` is removed from the prod call path.
- [ ] `config.json` `render_strategy_chain` controls chain order; unknown strategy name fails boot with a clear error.
- [ ] DB `segment_flags.details` gains `strategy_used`, optional `scale_applied`, optional `failure_reason`.
- [ ] Frontend review UI renders strategy chip; no segment shows opaque "overflow warn (no reason)" badge after re-running job `e1dcbbf1`.
- [ ] Re-running demo jobs `7f958166`, `b425150a`, `e1dcbbf1`, `9fc558a0`, `0989b344` produces zero segments with `strategy_used = NULL` and zero `overflow warn (no reason)` flag emissions.
- [ ] Benchmark script confirms reassemble wallclock on `7f958166` is ≤ baseline + 30s.
- [ ] EXPAND_VERTICAL collision check uses (active-segment bboxes ∪ image_rects ∪ page bottom margin); unit test covers a cell with a neighbor above, below, and at page bottom.
- [ ] RENDER_BELOW_RECT falls through to RENDER_IN_MARGIN → PRESERVE_SOURCE when below is occupied; unit test covers the occupied-below case.
- [ ] All existing tests still pass (213 baseline); ≥ 10 new tests added across strategies + dispatcher + frontend chip.

## Ambiguity Report

| Dimension          | Score | Min  | Status | Notes                                                  |
|--------------------|-------|------|--------|--------------------------------------------------------|
| Goal Clarity       | 0.92  | 0.75 | ✓      | Outcome is named, measurable, demo-job-bounded         |
| Boundary Clarity   | 0.92  | 0.70 | ✓      | DOCX/PPTX excluded with reason; D-2 deferred to 07     |
| Constraint Clarity | 0.78  | 0.65 | ✓      | 30s wallclock budget locked; scratch-page cost TBD     |
| Acceptance Criteria| 0.80  | 0.70 | ✓      | 12 pass/fail criteria; benchmark script enforces perf  |
| **Ambiguity**      | 0.132 | ≤0.20| ✓      |                                                        |

**Note on Constraint dim (0.78):** Real scratch-page cost is not yet measured. Plan 06-01 includes a measurement spike on job `7f958166` before committing to the 30s budget. If measurement shows the budget is impossible without caching, scratch-page reuse becomes mandatory inside 06-01 (not a follow-up plan).

## Interview Log

| Round | Perspective     | Question summary                                                 | Decision locked                                                                                  |
|-------|-----------------|------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| 1     | Researcher      | Wallclock budget for dry-run measurement?                        | ≤ 30s extra on job `7f958166` (1409 segs); caching mandatory if naive impl exceeds budget        |
| 1     | Researcher      | Backward-compat with phase-03.3 `overflow warn (no reason)`?     | Frontend migration in plan 06-05; clean break; no alias period                                   |
| 1     | Researcher      | DOCX/PPTX scope?                                                 | PDF-only; SPEC documents Protocol as future-extensible; no DOCX/PPTX code touched                |
| 2     | Boundary Keeper | Strategy chain order — hardcoded or configurable?                | Configurable via `config.json` `render_strategy_chain`; hard fail on unknown strategy            |
| 2     | Boundary Keeper | EXPAND_VERTICAL collision boundary?                              | Active segment bboxes ∪ image_rects ∪ page bottom margin                                         |
| 2     | Boundary Keeper | RENDER_BELOW_RECT when below is occupied?                        | Fall through to RENDER_IN_MARGIN → PRESERVE_SOURCE; force-overlay and push-page-down excluded    |

---

*Phase: 06-render-strategy-pipeline*
*Spec created: 2026-05-13*
*Next step: /gsd-discuss-phase 06 — implementation decisions (scratch-page lifecycle, dispatcher signature, frontend chip styling, etc.)*
