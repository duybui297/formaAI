# Phase 06: render-strategy-pipeline - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Refactor the PDF segment renderer (`backend/src/app/pipeline/pdf/reassembler.py`) into a named, ordered strategy chain so every translated cell terminates in an explicit, observable outcome. DOCX and PPTX pipelines are explicitly untouched. Frontend `FlagBadge` migrates in plan 06-05. Phase 06 delivers the framework + day-1 strategies (IDENTITY, MATH_PASSTHROUGH, SHRINK_IN_PLACE, PRESERVE_SOURCE) and 3 incremental strategies (WRAP_MULTI_LINE, EXPAND_VERTICAL, RENDER_BELOW_RECT).

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**8 requirements are locked.** See `06-SPEC.md` for full requirements, boundaries, and acceptance criteria.

Downstream agents MUST read `06-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- New module `backend/src/app/pipeline/pdf/render_strategies/` with Protocol, RenderContext, RenderResult, dispatcher, strategy classes
- Refactor `reassemble_pdf` to use the dispatcher
- Day-1 strategies: IDENTITY, MATH_PASSTHROUGH, SHRINK_IN_PLACE (dry-run measurement), PRESERVE_SOURCE
- Incremental strategies: WRAP_MULTI_LINE, EXPAND_VERTICAL, RENDER_BELOW_RECT, RENDER_IN_MARGIN
- Scratch-page measurement helper
- `config.json` `render_strategy_chain` parsing + startup validation
- DB `segment_flags.details` additions: `strategy_used`, `scale_applied`, `failure_reason`
- Frontend strategy chip
- Per-strategy unit tests + integration tests on 5 demo jobs
- Benchmark script enforcing ≤ 30s wallclock budget

**Out of scope (from SPEC.md):**
- DOCX renderer changes (DOCX reflows natively)
- PPTX renderer changes (auto-fit already works in prior UAT)
- OCR / scanned-PDF pipeline
- Glyph-level replacement
- Cross-page text flow
- D-2 text formatting preservation (deferred to Phase 07)
- Speech-bubble OCR fallback
- Per-doc-type chain policies

</spec_lock>

<decisions>
## Implementation Decisions

### Scratch-page lifecycle (controls 30s wallclock budget)
- **D-01:** Per-page scratch document, reused across all cells on that page.
  - Clone source page once at page-iteration boundary via `pymupdf.open()` + `insert_pdf(src_doc, from_page=N, to_page=N)`
  - Same scratch document handles every SHRINK_IN_PLACE measurement on that page
  - `.close()` the scratch doc at page-end (before moving to next page)
  - Memory budget bounded to 1 page × scratch overhead at any moment
  - **Rationale:** per-cell clone (~10ms × 1409 cells = 14s alone) likely blows the 30s budget; per-page reuse is ~5× faster while keeping isolation between pages

### Frontend strategy chip
- **D-02:** Extend `frontend/src/components/FlagBadge.tsx` with a new `strategy` variant.
  - Add `strategy: { label: "STRATEGY", className: "<info palette>" }` to `FLAG_CONFIG`
  - Strategy chip is always informational (slate/blue palette), never warning
  - Tooltip surfaces `strategy_used` + optional `scale_applied` from `segment_flags.details`
  - Reuses existing `Record<FlagType, {label, className}>` extension pattern from Phase 04 (`figure_passthrough`, `ocr_page_error`)
  - Inline flag badge in `SegmentRow.tsx` (which "avoids dependency on FlagBadge.tsx (plan 05 scope)") gets bridged in 06-05

### Plan staging (brief's proposed staging confirmed)
- **D-03:** 06-01 ships dispatcher + 4 day-1 strategies; incremental plans add WRAP/EXPAND/RENDER_BELOW one at a time.

  | Plan | Scope | Effort |
  |------|-------|--------|
  | 06-01 | Protocol + RenderContext + RenderResult + dispatcher + scratch helper + IDENTITY + MATH_PASSTHROUGH + SHRINK_IN_PLACE + PRESERVE_SOURCE + config parsing + per-strategy unit tests + benchmark script | ~2 days |
  | 06-02 | WRAP_MULTI_LINE strategy + tests | ~0.5 day |
  | 06-03 | EXPAND_VERTICAL strategy + collision detection (active segs ∪ image_rects ∪ page bottom) + tests | ~1 day |
  | 06-04 | RENDER_BELOW_RECT strategy + RENDER_IN_MARGIN strategy + D-1 caption regression test + tests | ~1 day |
  | 06-05 | Frontend FlagBadge migration + SegmentRow bridge + remove legacy `overflow warn (no reason)` flag emission | ~0.5 day |
  | 06-06 | Integration UAT on 5 demo jobs (`7f958166`, `b425150a`, `e1dcbbf1`, `9fc558a0`, `0989b344`) + wallclock benchmark validation + tuning | ~1 day |

  Each plan independently testable. 06-01 risk is contained (dispatcher + 4 strategies; if it breaks, no frontend change yet). D-1 (caption) waits until 06-04 — acceptable per SPEC.md.

### Demo-day rollback
- **D-04:** Config-only rollback via `render_strategy_chain = ["IDENTITY", "MATH_PASSTHROUGH", "PRESERVE_SOURCE"]`.
  - No code change required
  - Sets chain to pure preserve-source mode → outputs render source-language text (JA stays JA on failure)
  - Matches phase-03.3 graceful-degrade contract
  - Demo team only needs to edit `config.json` and restart worker container
  - **Why not git revert / feature flag:** git revert loses all 06 work and needs git access during demo; feature-flag doubles maintenance surface and brief explicitly says remove `_estimate_max_fitting_scale` from prod path

### Claude's Discretion
- Module layout inside `render_strategies/`: one file per strategy vs grouped (`shrink.py`, `expand.py`, `fallback.py`) — planner decides based on per-strategy size
- Whether `RenderContext` is a Pydantic model (validation) or a frozen dataclass (perf) — planner picks; Pydantic preferred if cost is < 1ms per construction
- Exact `config.json` schema (top-level key vs nested under `pdf:`) — planner picks; keep consistent with existing config conventions in the file
- Whether `strategy_used` is enum or free-form string at the Python level — enum is safer; planner picks
- Benchmark script implementation: standalone CLI vs pytest marker vs both — planner picks
- Logging granularity per strategy attempt — `debug` level for chain trace, `info` for terminal strategy

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Locked requirements
- `.planning/phases/06-render-strategy-pipeline/06-SPEC.md` — Locked requirements; MUST read before planning. 8 requirements, 12 acceptance criteria, wallclock budget, strategy chain contracts.
- `.planning/phases/06-render-strategy-pipeline/06-SPEC-BRIEF.md` — Original pre-spec brief; useful for strategy descriptions and the per-strategy contract example in §"Per-strategy contract".

### Phase 03 family — prior PDF decisions still in force
- `.planning/phases/03-pptx-native-pdf/03-CONTEXT.md` — original PDF redact-and-reinsert pipeline decisions.
- `.planning/phases/03.2-pdf-table-formula-fidelity/03.2-CONTEXT.md` — `Segment.kind` schema (`text` | `table_cell` | `math_passthrough`); `find_tables()` cell-aware extraction; font-name passthrough allowlist. Day-1 strategies IDENTITY + MATH_PASSTHROUGH use this.
- `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-DEFERRED.md` — D-1 (caption near image) is the explicit driver for RENDER_BELOW_RECT in plan 06-04; D-2 (text formatting) is explicitly deferred to Phase 07.
- `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-01-PLAN.md` — context on the multi-line scale, image-collision pre-check, and `pos_to_block` filter alignment that the strategy chain must preserve.
- `.planning/phases/03.3-native-pdf-table-cell-fidelity/03.3-01-SUMMARY.md` — final state of the heuristic `_estimate_max_fitting_scale` that SHRINK_IN_PLACE replaces.

### Backend code surfaces (refactor targets + reuse)
- `backend/src/app/pipeline/pdf/reassembler.py` — 574-line single function `reassemble_pdf`; primary refactor target. Helpers `_is_identity_translation` (line 80), `_estimate_max_fitting_scale` (line 96, to be removed from prod path), `_clip_rect_away_from_images` (line 148) — first two folded into strategies, third reused by EXPAND_VERTICAL collision check.
- `backend/src/app/pipeline/pdf/extractor.py` — segment extraction; not modified but provides the table cell rect contract SHRINK_IN_PLACE consumes.
- `backend/src/app/pipeline/segment.py` — `Segment` dataclass with `kind` field; strategy chain dispatches on `seg.kind` for IDENTITY + MATH_PASSTHROUGH.
- `backend/src/app/pipeline/pdf/fonts.py` — Noto CSS contract; scratch-page measurement MUST also load this CSS or measurements diverge from real render.
- `backend/src/app/workers/translate_worker.py` — calls `reassemble_pdf(...)`; signature must remain backward-compatible OR worker call site updated atomically with the refactor.

### DB schema
- `backend/src/app/models/segment_flag.py` (or equivalent) — `details` is JSONB; new keys `strategy_used` / `scale_applied` / `failure_reason` are additive (no Alembic migration needed; reading code must tolerate missing keys for legacy rows).

### Frontend code surfaces
- `frontend/src/components/FlagBadge.tsx` — `FLAG_CONFIG: Record<FlagType, {label, className}>` extension pattern; add `strategy` variant here.
- `frontend/src/lib/types.ts:67` — `FlagType` enum; extend with `strategy` literal.
- `frontend/src/components/SegmentRow.tsx:12` — inline flag badge currently bypasses FlagBadge; comment "Inline flag badge — avoids dependency on FlagBadge.tsx (plan 05 scope)" — bridge in 06-05.
- `frontend/src/app/jobs/[id]/review/page.tsx:61` — filter pipeline reads `f.flag_type === activeFilter`; must accept new `strategy` filter (or be excluded if strategy is meta-info, not filter-worthy).
- `frontend/src/__tests__/FlagBadge.test.tsx` — extension test pattern (mirror Phase-04 `phase4-flagbadge.test.tsx`).

### Test fixtures (UAT canonical)
- Job `7f958166` — Japanese biology table-heavy; 1409 segments; baseline for wallclock benchmark (Req 8).
- Job `e1dcbbf1` — ja→en; CJK→Latin 5–9× expansion; 450 overflow flags pre-06; primary SHRINK_IN_PLACE regression target.
- Job `b425150a` — ja→vi same source as `e1dcbbf1`; secondary expansion test.
- Job `9fc558a0` — cited in 03.3-DEFERRED.md UAT list; secondary regression.
- Job `0989b344` — page-5 image-collision case; RENDER_BELOW_RECT regression for D-1 caption fix.

### Architecture
- `.planning/codebase/ARCHITECTURE.md` — codebase architecture map; consult for module boundaries.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_is_identity_translation(source, translated)` → directly becomes IDENTITY strategy's `can_render` test.
- `_clip_rect_away_from_images(rect, image_rects)` → directly reusable for EXPAND_VERTICAL's collision check (extend with "neighbor active-segment bboxes" set, not just image_rects).
- `build_noto_archive_and_css()` in `fonts.py` → scratch-page measurement MUST inject the same CSS or it measures with default fonts and overshoots/undershoots the real scale.
- `Segment.kind ∈ {"text","table_cell","math_passthrough"}` schema → dispatcher routes on `kind`; MATH_PASSTHROUGH strategy is a one-liner `return seg.kind == "math_passthrough"`.
- `FlagBadge` Phase-04 extension pattern (`figure_passthrough`, `ocr_page_error`) → direct template for the strategy chip.
- `find_tables()` walk in `reassemble_pdf:241-264` → cell bbox map is already built; RenderContext consumes it.
- `_block_inside_cell` filter pattern in `reassemble_pdf:272-280` → centroid-in-cell-rect filter required so `pos_to_block` lookups stay aligned between extractor and reassembler (do NOT regress this).

### Established Patterns
- **JSONB additive evolution** — `segment_flags.details` has been extended multiple times (`auto_adjusted`, `char_ratio`, `image_collision`, etc.) without migration. Continue this pattern; readers tolerate missing keys.
- **Per-block CSS wrapper** — `spans_to_html` emits a per-block CSS size wrapper (added in 03.1 hotfix); SHRINK_IN_PLACE measurement MUST wrap the test HTML the same way.
- **Out-parameter list for flags** — `reassemble_pdf` takes `overflow_flags: list[dict]` as an out-parameter that the worker drains into DB. Strategy chain results funnel into this same list — preserve the worker contract.
- **Module structure** — pipeline packages follow `{pipeline_kind}/__init__.py + extractor.py + reassembler.py + fonts.py`. New `render_strategies/` package fits naturally beside the existing files.

### Integration Points
- `reassemble_pdf(doc, segments, translated_map, output_path, overflow_flags)` → the refactor preserves this signature. Internally, the per-segment redact-and-insert logic becomes `dispatch_render(ctx, chain)`.
- Worker (`translate_worker.py`) → no signature change needed if `reassemble_pdf` keeps its current parameters; otherwise update worker call site atomically.
- Frontend review page filter (`page.tsx:61`) → strategy chip is meta-info; decide whether to add it to the filter list or skip filter integration (defer to planner).

</code_context>

<specifics>
## Specific Ideas

- Wallclock benchmark MUST measure on job `7f958166` specifically (1409 segments). If the per-page scratch optimization (D-01) still exceeds 30s, plan 06-01 adds a further optimization (e.g., cache scratch-page measurements by `(rect_w, rect_h, char_count_bucket)` tuple) before plan can close.
- Strategy chip is always informational (slate/blue palette). It is NOT a warning. Warning chips (overflow, glossary_violation) keep their existing palette.
- Demo-day rollback method MUST be documented in 06-06 UAT artifact so the demo team can execute it from `config.json` without code/git access.

</specifics>

<deferred>
## Deferred Ideas

- **D-2 text formatting preservation** (color/bold/italic/font family) — explicitly Phase 07 per 03.3-DEFERRED.md and SPEC.md.
- **Speech-bubble OCR fallback for native PDFs** — separate phase; not D-1, not D-3.
- **Glyph-level PDF content stream rewrite** — multi-week engineering; deferred to PoC v2 / production phase.
- **Cross-page text flow** — translation spanning multiple pages; deferred.
- **Per-doc-type chain policies** (different chain order for academic papers vs slides) — config knob exists, but only one default chain ships; per-doc-type routing deferred.
- **DOCX/PPTX Strategy Protocol adoption** — Protocol is shaped to allow it, but no DOCX/PPTX code changes this phase. Revisit if a regression surfaces.
- **Level-3 row-level segmentation** (deferred from 03.3) — probably obviated by the new pipeline since per-cell render correctness is no longer the bottleneck. Reassess after 06-06 UAT.

</deferred>

---

*Phase: 06-render-strategy-pipeline*
*Context gathered: 2026-05-13*
