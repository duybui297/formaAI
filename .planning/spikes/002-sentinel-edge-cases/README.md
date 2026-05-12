---
spike: 002
title: Sentinel '|||' edge cases — collision, scale, whitespace, glossary
status: VALIDATED
verdict: GREEN — escape literal '|||' with ⟦T{n}⟧; whitespace caveat accepted
started: 2026-05-04
completed: 2026-05-04
tags: [pdf, table, sentinel, escape, whitespace, glossary, qwen-mt]
depends_on: 001
---

# Spike 002 — Sentinel `|||` edge cases

Builds on Spike 001 (sentinel `|||` chosen, 100% survival on baseline rows).
Validates four open risks before phase commitment to Option A (row-level
table segments).

## Probes + results

| # | Probe | Verdict | Implication |
|---|-------|---------|-------------|
| A | Cell content contains `\|\|\|` literally; naive join | **HAZARD CONFIRMED** | `Range \|\|\|x\|\|\|` middle cell → naive split yields 5 parts, expected 3. Cannot ship without escape. |
| A' | Same content, pre-escaped with `⟦P0⟧` placeholder before join | **OK** | `Range ⟦P0⟧x⟦P0⟧` survives translation intact; split → restore yields original 3 cells. |
| B | 20-cell row, en→ja (aggressive expansion target) | **OK** | 19/19 `\|\|\|` preserved. Production tables max at ~8 cells/row — 2.5× margin. |
| C | Per-cell whitespace fidelity (leading / trailing / internal) | **FRAGILE** | First cell's leading whitespace dropped (`'  Apple'` → `'Táo'`). Trailing + internal preserved. Tolerable for rect-based PDF reassembly. |
| D | Glossary `terminology` API + `\|\|\|` coexistence | **OK** | `Apple → Táo Đỏ` term applied, 2 sentinels preserved, other cells translated normally. |

## Decisions

1. **Escape literal `|||` in cell content before join.**
   - Pre-pass each cell, replace `|||` with `⟦T{n}⟧` placeholder (CORE-05 pattern,
     already validated in `pipeline/placeholder.py`).
   - After translation + split, restore `⟦T{n}⟧` → `|||` per cell.
   - Numeric suffix is critical — `⟦CELL⟧` would fail per Spike 001.

2. **Cap row width at 50 cells** as a defensive ceiling.
   - 20-cell test passed clean; production max observed is 8 cells/row.
   - If extractor finds a >50-cell row, fall back to per-cell segments for
     that row only.

3. **Accept first-cell leading-whitespace loss.**
   - PyMuPDF cell rects are absolute coordinates; visual cell position is
     rect-based, not whitespace-based.
   - If a future bug surfaces, can mitigate by stripping cells before join
     and storing original padding separately.

4. **Glossary requires no special handling.**
   - `terminology` API param works orthogonally to sentinel-joined input.

## Open follow-ups (deferred to phase plan)

- Verify escape behavior when cell content contains BOTH a literal `|||`
  AND an existing `⟦T{n}⟧` from the CORE-05 placeholder pass (URL, date,
  etc.). Need a placeholder-ID namespace strategy: maybe `⟦C{n}⟧` for cell
  collision-escape vs `⟦T{n}⟧` for CORE-05 mask. Phase Task 1.
- Whitespace-loss mitigation if real PDFs surface a case where it matters
  (none observed today).

## Artifacts

- `run_spike.py` — runnable probe script (5 LLM calls)
- `results.json` — full input/output capture
