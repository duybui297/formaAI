# Spikes — AI Translation PoC

Overall idea: shrink PDF segment count by 10× via row-level table segments,
without losing cell-level layout fidelity.

| # | Spike | Status | Verdict |
|---|-------|--------|---------|
| 001 | Table row sentinel-delimiter survival | VALIDATED | GREEN — `\|\|\|` chosen, 100% survival across en/vi/ja/zh |
| 002 | Sentinel edge cases — collision, scale, whitespace, glossary | VALIDATED | GREEN — escape with `⟦T{n}⟧`; 20-cell safe; whitespace caveat accepted |

## Architecture decision (post-002)

Option A (row-level table segments with `|||` delimiter) is **green-lit**.
Required machinery:

1. **Extractor** — emit one `kind="table_row"` segment per row. Cell content
   pre-escaped: any literal `|||` masked to `⟦T{n}⟧` placeholder. Cell rects
   stored alongside (extend `structural_position` or new column).
2. **Translator** — unchanged. Operates on opaque text per segment.
3. **Reassembler** — split translated row by `|||`; restore `⟦T{n}⟧` placeholders
   per cell; distribute cell strings to cell rects (existing Pass 3 table_cell
   branch from phase 03.3).
4. **DB schema** — may need a `cell_rects` JSON column on Segment, or encode
   in `structural_position`.

## Frontier candidates (not yet spiked, low priority)

- **003 — Placeholder-namespace conflict:** verify behavior when a cell
  contains BOTH literal `|||` AND a CORE-05 placeholder (URL/date). Plan a
  `⟦C{n}⟧` vs `⟦T{n}⟧` namespace, or single shared counter. Deferred to
  phase Task 1.
