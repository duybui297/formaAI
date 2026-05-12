# Spikes — AI Translation PoC

Overall idea: shrink PDF segment count by 10× via row-level table segments,
without losing cell-level layout fidelity.

| # | Spike | Status | Verdict |
|---|-------|--------|---------|
| 001 | Table row sentinel-delimiter survival | VALIDATED | GREEN — `\|\|\|` chosen, 100% survival across en/vi/ja/zh |

## Frontier candidates (not yet spiked)

- **002 — Content collision + escape strategy:** verify behavior when cell
  content contains the chosen `|||` sentinel literally; design escape /
  pre-scan path.
- **003 — Large-row stress:** translate a 20-cell row to confirm sentinel
  count preservation scales beyond the 5-cell test ceiling.
- **004 — Whitespace fidelity:** assert leading/trailing whitespace inside a
  cell survives the join → translate → split round-trip.
- **005 — Glossary interaction:** translate row with `terminology` API param
  active; verify sentinel + terminology cooperate.
