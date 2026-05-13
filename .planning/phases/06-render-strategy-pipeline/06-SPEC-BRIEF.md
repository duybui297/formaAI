---
phase: "06"
slug: render-strategy-pipeline
status: BRIEF (pre-spec — feed to /gsd-spec-phase 06 to refine into SPEC.md)
created: 2026-05-13
prerequisites: [phase-03.3 merged into main at commit 4073150]
---

# Phase 06 — Generic Render-Strategy Pipeline

## Problem (what we keep hitting)

Translation expansion creates a layout mismatch between the source rect
(measured to hug source glyphs) and the rendered translation (1.3×–9×
longer text in en/vi). Every phase since 03 has shipped a patch for some
new failure mode:

- Phase 3.1 — image collision (PDF text overlapping image area)
- Phase 3.2 — table cell extraction (broke long-cell layouts)
- Phase 3.3 — table cell rect inset + adaptive scale (cell-aware)
- Phase 3.3 (today) — multi-line scale, identity-skip, pre-clip,
  pos_to_block alignment

Each patch fixed ONE doc class. The next doc surfaces a new failure
mode. Root cause: there is exactly one render strategy
(`add_redact_annot` → `apply_redactions` → `insert_htmlbox` with a
heuristic scale_low), and every cell must fit it or be skipped.

## Idea (what the phase delivers)

Replace the single-strategy renderer with a **strategy chain**: every
segment is passed through a pipeline of named strategies, in priority
order, and the first one that fits commits the render. Each strategy is
a small isolated module with a uniform interface, so new document
classes are addressed by adding strategies, not by special-casing the
core loop.

### Strategy chain (initial proposal — discuss-phase to refine)

| # | Strategy | Logic | Test |
|---|----------|-------|------|
| 1 | `IDENTITY` | translated == source (whitespace-stripped) → no work | already implemented as `_is_identity_translation` |
| 2 | `MATH_PASSTHROUGH` | seg.kind == math_passthrough → leave source visible | already implemented |
| 3 | `SHRINK_IN_PLACE` | dry-run `insert_htmlbox` on scratch page at scales `[0.7, 0.5, 0.3, 0.2, 0.15]`; commit first scale where `spare_height >= 0` | dry-run uses scratch copy of the page; cost ~5 × 10ms per cell |
| 4 | `WRAP_MULTI_LINE` | if rect is tall enough for body_pt × line_factor × 2, force multi-line via CSS `line-height` adjustment; dry-run measure | covers tall cells with wide-but-short content |
| 5 | `EXPAND_VERTICAL` | nudge rect downward up to N pt (don't overlap any neighbor seg's rect), retry SHRINK_IN_PLACE | covers cells with vertical slack below |
| 6 | `RENDER_BELOW_RECT` | render translation in a new rect placed directly below source (push other content down OR overlay on page bottom margin); leave source visible | covers caption-near-image (D-1 from 03.3 deferred) |
| 7 | `RENDER_IN_MARGIN` | place translation in nearest available page margin with a pointer line | last attempt at translating |
| 8 | `PRESERVE_SOURCE` | always succeeds; emit `untranslated_overflow` flag for review UI | fail-safe |

The chain is configurable in `config.json` (`render_strategy_chain:
[...]`) so per-job or per-doc-type policy is possible later.

### Per-strategy contract

```python
class RenderContext(BaseModel):
    page: pymupdf.Page
    scratch_page: pymupdf.Page  # cloned page for dry-run measurement
    segment: Segment
    translated_html: str
    body_pt: float
    source_rect: pymupdf.Rect
    neighbor_rects: list[pymupdf.Rect]   # for collision tests
    image_rects: list[pymupdf.Rect]
    page_margin_rect: pymupdf.Rect       # below content, available space


class RenderResult(BaseModel):
    strategy: str                # which strategy succeeded
    success: bool
    final_rect: pymupdf.Rect | None
    scale_applied: float | None
    failure_reason: str | None   # populated when success=False


class RenderStrategy(Protocol):
    name: str

    def can_render(self, ctx: RenderContext) -> bool:
        """Cheap pre-check. False → pipeline skips to next strategy."""

    def render(self, ctx: RenderContext) -> RenderResult:
        """Attempt the render. May call ctx.scratch_page first for measurement.
        On success: commits redact + insert on ctx.page. On failure: no
        side effects."""
```

### Observability

`segment_flags.details` gains `strategy_used: str` so review UI can show
"which strategy translated this cell" and reviewers know why the layout
looks how it does. Auto-adjusted, overflow, image_collision flags still
emit as today.

## Scope (what's IN)

- Refactor `reassemble_pdf` to delegate per-segment rendering to the
  strategy chain
- Implement strategies #1–#3 plus #8 (PRESERVE_SOURCE) on day 1
- Add scratch-page measurement helper (clone source page bytes into an
  in-memory `pymupdf.Document`, run insert_htmlbox there, read
  spare_height, discard)
- Add strategies #4–#7 incrementally (each with regression test)
- DB flag detail: `strategy_used`
- Per-strategy unit tests (mocked PyMuPDF or synthetic doc)
- Integration test: re-run job 7f958166 + e1dcbbf1 + b425150a and
  verify no `overflow warn (no reason)` flags fire (every cell either
  fits at some scale, or routes to PRESERVE_SOURCE with an explicit
  flag)

## Scope (what's OUT)

- DOCX / PPTX renderers — different mechanism (run-level replacement,
  shape redraw); leave alone. Strategy pipeline is PDF-only for now.
- OCR pipeline (scanned PDF composer) — separate code path.
- Glyph-level replacement (per-char rewrite of PDF content stream) —
  acknowledged as ideal but multi-week engineering; deferred to a
  future "PoC v2 / production" phase.
- Cross-page text flow (translation spans pages) — deferred.

## Success criteria

1. Generic — adding a new strategy is a small isolated PR; core loop
   doesn't change.
2. On the demo doc set (jobs `7f958166`, `b425150a`, `e1dcbbf1`,
   `9fc558a0`, `0989b344`), zero cells fall into the
   `overflow warn (no reason)` bucket — every cell terminates in a
   named strategy outcome (SHRINK with measured scale,
   EXPAND_VERTICAL with delta, RENDER_BELOW_RECT, or PRESERVE_SOURCE
   with `untranslated_overflow`).
3. Per-segment `flag_type=overflow severity=warn` is replaced by
   informational flags carrying `strategy_used` + `scale_applied` (or
   reason if strategy was PRESERVE_SOURCE).
4. Wallclock overhead < 2× baseline for the largest demo job (job
   `7f958166` 1409 segments). Dry-run renders are the main cost;
   target ≤ 60s extra for that job.
5. Test suite: existing 213 tests still pass; ≥10 new tests covering
   each new strategy + chain dispatcher.

## Verification plan (UAT after execute)

| Test PDF | Coverage |
|----------|----------|
| job 7f958166 (Japanese biology table-heavy) | dense CJK table cells |
| job b425150a (same source ja→vi) | CJK→Latin expansion |
| job e1dcbbf1 (same source ja→en) | CJK→Latin 5–9× expansion |
| job 0989b344 (page 5 with image+caption) | image-collision strategy chain |
| BMC academic paper | multi-column, math passthrough |
| Phase 04 scanned PDF samples | OCR path NOT affected |

Pass when each test produces an output PDF where every translated
segment is either rendered legibly OR explicitly flagged
`untranslated_overflow` with source preserved.

## Open questions (for spec-phase to resolve)

1. **Scratch page cost** — does cloning a page object for measurement
   work, or do we need a full document copy? Measure on 1-page PDF
   first; if cheap, use per-cell scratch; if expensive, batch.
2. **Strategy chain order** — should it be hard-coded or per-doc-type
   configurable? Probably configurable but with a sensible default.
3. **EXPAND_VERTICAL collision boundary** — how do we define
   "neighbor rects" cleanly? Other active segments' bboxes, plus
   image_rects, plus page bottom?
4. **RENDER_BELOW_RECT** when below is also occupied — push everything
   down (recompute page layout) or render at margin? Choose one.
5. **Backwards compat with phase 03.3 flags** — `overflow warn (no
   reason)` is read by the frontend FlagBadge. Do we keep the old flag
   names as aliases or do a frontend migration?
6. **DOCX/PPTX** — they have analogous overflow problems
   (`detect_pptx_overflow`, auto-fit). Should the strategy framework
   generalize to all 3 pipelines (refactor), or stay PDF-only this
   phase?

## Estimated breakdown

| Plan | Description | Effort |
|------|-------------|--------|
| 06-01 | Strategy core: protocol, context, result, pipeline dispatcher; refactor existing PDF renderer to use strategies #1–#3 + #8 | 2 days |
| 06-02 | Strategy #4 WRAP_MULTI_LINE + tests | 0.5 day |
| 06-03 | Strategy #5 EXPAND_VERTICAL + collision detection + tests | 1 day |
| 06-04 | Strategy #6 RENDER_BELOW_RECT for caption-near-image (closes D-1 from 03.3 deferred) + tests | 1 day |
| 06-05 | Frontend: extend FlagBadge / review UI with `strategy_used` chip | 0.5 day |
| 06-06 | Integration UAT on 5+ jobs + tuning | 1 day |
| Total | | ~1 week |

## Notes for the planner

- Reuse `_clip_rect_away_from_images` — it's the right primitive for
  EXPAND_VERTICAL.
- Reuse `_is_identity_translation` as-is for strategy IDENTITY.
- Drop the heuristic `_estimate_max_fitting_scale` — replaced by
  measurement. (Keep around as comment/reference; remove from prod
  code path.)
- `_MIN_ADAPTIVE_SCALE = 0.15` becomes the SHRINK_IN_PLACE lowest
  candidate scale — no longer a "skip-or-render" decision boundary.
- Scratch page creation: `pymupdf.open()` + `insert_pdf(src_doc,
  from_page=N, to_page=N)` to copy a single page. Discard after
  measurement.

## After this phase

If 06 lands successfully, remaining 03.3-deferred:
- D-2 (text formatting preservation) becomes phase 07.
- Speech-bubble OCR fallback becomes a future phase.
- Level 3 row-level segmentation (deferred from 03.3 spike) probably
  obviated by the new pipeline since per-cell render correctness is no
  longer the bottleneck.
