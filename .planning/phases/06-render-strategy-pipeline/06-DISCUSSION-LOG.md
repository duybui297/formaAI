# Phase 06: render-strategy-pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-13
**Phase:** 06-render-strategy-pipeline
**Areas discussed:** Scratch-page lifecycle, Frontend strategy chip, Plan staging, Demo-day rollback

---

## Scratch-page lifecycle (controls 30s wallclock budget)

| Option | Description | Selected |
|--------|-------------|----------|
| Per-page scratch, reused across all cells on that page | Clone page once at page boundary; same scratch handles N cells; pymupdf.Document.close() at page end; minimal memory, ~5x faster than per-cell clone | ✓ |
| Per-cell scratch, fresh clone each time | Simplest; ~10ms clone × 1409 cells = 14s alone; likely blows 30s budget; safest isolation | |
| Per-document scratch, one scratch doc cloned once | Lowest memory; risk of scratch state leaking between cells; need explicit page-clear between measurements; complex | |

**User's choice:** Per-page scratch, reused across all cells on that page (Recommended)
**Notes:** D-01 in CONTEXT.md. If page-level scratch still exceeds the 30s budget, plan 06-01 must add a (rect_w, rect_h, char_count_bucket) measurement cache before the plan can close.

---

## Frontend strategy chip — reuse FlagBadge or new component?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend FlagBadge with strategy variant | New 'strategy' flag_type rendering colored chip + label 'STRATEGY' + tooltip showing strategy_used + scale_applied; reuses FLAG_CONFIG pattern; minimal frontend churn | ✓ |
| New StrategyChip component, sibling to FlagBadge | Cleaner separation; strategy = always informational, never warning; renders next to FlagBadge in SegmentRow; ~50 LOC new component | |
| Inline chip in SegmentRow | SegmentRow.tsx already has inline flag badge avoiding FlagBadge dep; consistent with phase-02 convention; less reusable elsewhere | |

**User's choice:** Extend FlagBadge with strategy variant (Recommended)
**Notes:** D-02 in CONTEXT.md. Mirrors Phase-04's FLAG_CONFIG extension pattern (`figure_passthrough`, `ocr_page_error`). Inline SegmentRow flag badge gets bridged in plan 06-05.

---

## Plan staging

| Option | Description | Selected |
|--------|-------------|----------|
| Brief's staging — 06-01 dispatcher+4 strategies, 06-02 WRAP, 06-03 EXPAND, 06-04 RENDER_BELOW, 06-05 frontend, 06-06 UAT | Each plan is independently testable; smallest 06-01 risk; D-1 (caption) waits until 06-04 — acceptable per SPEC | ✓ |
| Compressed — 06-01 all strategies + dispatcher + frontend; 06-02 UAT | Faster to demo-ready; 06-01 is bigger plan (~3 days); rollback granularity worse | |
| Closer-first — 06-01 dispatcher+4 strategies, 06-02 RENDER_BELOW (closes D-1 caption next), 06-03 EXPAND, 06-04 WRAP, 06-05 frontend, 06-06 UAT | Prioritizes D-1 fix over D-3 fix; matches 'biggest UX win' rationale from 03.3-DEFERRED.md; demo-visible faster | |

**User's choice:** Brief's staging (Recommended)
**Notes:** D-03 in CONTEXT.md. 6 plans total, ~1 week effort. Plan-checker should verify each plan is independently shippable.

---

## Demo-day rollback

| Option | Description | Selected |
|--------|-------------|----------|
| Config-only rollback via render_strategy_chain = ["IDENTITY", "MATH_PASSTHROUGH", "PRESERVE_SOURCE"] | No code change; sets chain to pure preserve-source; outputs are JA/source-language readable; matches phase-03.3 graceful-degrade behavior; cheapest | ✓ |
| Git revert to phase-03.3 tag (main-backup-pre-phase-03.3-merge) | Full revert; loses 06 work; ~2 min ops; demo team needs git access | |
| Feature flag — RENDER_STRATEGY_ENABLED env var; old code path stays in tree | Cleanest fallback; doubles maintenance surface during dev; brief said remove _estimate_max_fitting_scale from prod path | |

**User's choice:** Config-only rollback (Recommended)
**Notes:** D-04 in CONTEXT.md. Rollback procedure MUST be documented in 06-06 UAT artifact so demo team can execute from `config.json` without code/git access.

---

## Claude's Discretion

- Module layout inside `render_strategies/` package: one file per strategy vs grouped — planner picks based on per-strategy LOC.
- `RenderContext` as Pydantic model vs frozen dataclass — planner picks; Pydantic preferred if construction cost < 1ms.
- `config.json` schema location (top-level vs nested under `pdf:`) — planner picks; match existing conventions.
- `strategy_used` as enum vs free-form string at Python level — enum preferred for type-safety; planner picks.
- Benchmark script implementation: standalone CLI vs pytest marker vs both — planner picks.
- Logging granularity per strategy attempt (`debug` for chain trace, `info` for terminal strategy).

## Deferred Ideas

- D-2 text formatting preservation (color/bold/italic/font family) — Phase 07 per SPEC.md.
- Speech-bubble OCR fallback for native PDFs — separate phase.
- Glyph-level PDF content stream rewrite — PoC v2 / production phase.
- Cross-page text flow — deferred.
- Per-doc-type chain policies — config knob exists, only default chain ships.
- DOCX/PPTX Strategy Protocol adoption — Protocol is future-extensible but no code change this phase.
- Level-3 row-level segmentation — likely obviated by 06; reassess after 06-06 UAT.
