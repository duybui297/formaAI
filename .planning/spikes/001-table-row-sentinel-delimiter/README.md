---
spike: 001
title: Table row sentinel-delimiter survival across qwen-mt-turbo
status: VALIDATED
verdict: GREEN — `|||` sentinel chosen; row-level segments feasible
started: 2026-05-04
completed: 2026-05-04
tags: [pdf, table, segments, qwen-mt, delimiter, sentinel]
---

# Spike 001 — Table row sentinel-delimiter survival

## Question

Can a row of N table cells be packed into ONE translation call by joining cells
with a sentinel string, and have qwen-mt-* preserve the sentinel count + position
in the output?

If YES → Option A (row-level table segments) is feasible. ~10× fewer segments
on table-heavy PDFs (job 7f958166: 1381 cells → ~150 rows).

## Setup

8 row patterns × 4 sentinel candidates = 32 calls against `qwen-mt-plus`
(env-configured model — same family as `qwen-mt-turbo`). Languages exercised:
`en → vi`, `ja → vi`, `vi → en`, `en → ja`, `zh → vi`.

Sentinel candidates:
- `⟦CELL⟧` — matches CORE-05 placeholder family
- `|||` — ASCII triple-pipe
- `<CELL>` — XML-ish
- `\t` — tab character

## Results

| Sentinel | Survival | Verdict |
|----------|----------|---------|
| `⟦CELL⟧` | 3 / 8 (38%) | FAIL — model translates the word "CELL" inside |
| `\|\|\|` | 8 / 8 (100%) | **WINNER** — pure ASCII, no dictionary surface |
| `<CELL>` | 8 / 8 (100%) | Pass — model treats `<X>` as opaque markup, but "CELL" is risky long-term |
| `\t` | 4 / 8 (50%) | FAIL — `ja->vi` and downstream cases collapse whitespace |

## Key insight

`⟦CELL⟧` fails because the bracket survives but the **dictionary word inside is
translated**:

```
in:  'Year⟦CELL⟧Revenue⟦CELL⟧Growth'      en->vi
out: 'Năm⟦Ô⟧Doanh thu⟦Ô⟧Tăng trưởng'      ← "CELL" → "Ô" (VI for "cell")

in:  'Apple⟦CELL⟧Orange⟦CELL⟧Banana...'  en->ja
out: 'リンゴ⟦細胞⟧オレンジ⟦細胞⟧...'        ← "CELL" → "細胞" (JA for "cellular")
```

This is exactly why CORE-05 uses `⟦T{n}⟧` (numeric suffix) — numbers have no
dictionary surface to translate. The lesson is: **sentinels must contain zero
dictionary tokens.** `|||` qualifies; `<CELL>` only survived because XML-tag
handling overrode the word lookup, but that's an implicit-contract bet.

## Verdict

GREEN — choose `|||` as the row delimiter. Empirically bulletproof on the
8-case suite spanning all PoC target languages.

## Open risks to validate before phase commitment

1. **Content collision** — real PDF cells theoretically could contain `|||` as
   literal content (rare in tables but possible in code snippets, ASCII art).
   Mitigation: pre-scan source; escape literal `|||` to a placeholder before
   join, restore after split. Or pick rarer sentinel like `\|\|@\|\|`.
2. **Large rows** — tested up to 5 cells. Job 7f958166 page-1 table has 672
   cells across 84 rows × 8 cols = 8 cells/row. Within tested range but
   verify with a 20-cell row probe in follow-up.
3. **Whitespace fidelity** — verify trailing/leading cell whitespace is
   preserved across join + split (not asserted in this spike).
4. **Sentinel under glossary terminology** — verify `terminology` API
   parameter doesn't trip over `|||` content.

## Decision

Move to Option A architecture:
- Extractor: emit one `kind="table_row"` segment per row with cells joined by
  `|||`. Keep cell-rect map in `structural_position` for reassembly.
- Reassembler: split translated text on `|||`, distribute back to cell rects.
- Validate the 4 open risks above as a small follow-up spike before the
  architecture phase, or fold them into the phase plan as Task 1.

## Artifacts

- `run_spike.py` — runnable probe script
- `results.json` — full input/output capture for all 32 calls
