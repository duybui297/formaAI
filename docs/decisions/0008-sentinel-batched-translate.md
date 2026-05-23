# ADR-0008: Sentinel-joined batches at translator layer

**Status**: Accepted
**Date**: 2026-05-13
**Decider(s)**: Thu

## Context

A native PDF with tables can produce hundreds of small cells, each ≤ 20
characters. Translating one cell per API call:

- Burns DashScope rate-limit budget (60 RPM on free tier; even paid
  tiers cap in the hundreds).
- Loses cross-cell context (model translates "Total" in row 7 with no
  knowledge of column header "Sales / Total / Tax").
- Slow: round-trip latency dominates each call.

DashScope's `terminology` parameter operates per-call, so we can batch
without losing glossary support.

## Decision

At the translator layer, **sentinel-join** multiple unique cells with
a delimiter (`|||`) into a single API call. Default batch size: 10
cells. On count mismatch in the response (model dropped a sentinel),
**fall back to per-segment** translation for that batch only.

Batch size tunable via `DASHSCOPE_BATCH_SIZE` env var.

## Alternatives considered

- **No batching (per-cell calls)** — original behaviour. ~50× more API
  calls; hits rate limits constantly on CJK table jobs.
- **Token-budget batching only** — packs by token count alone, no
  delimiter. Model has no way to delimit translations in the response
  — count cannot be validated.
- **Aggressive batch size (25+)** — empirically ~24% mismatch on
  CJK-heavy table jobs (vs ~9% at size 10). Falls back too often to
  be a net win.

## Consequences

- ✅ ~50× reduction in API calls on table-heavy native PDFs.
- ✅ Better cross-cell coherence for similar adjacent cells.
- ✅ Glossary (`terminology`) still applied — per-call parameter.
- ⚠️ Sentinel `|||` may collide with real document content (rare).
  Pre-scan cells for the sentinel; on collision, drop that cell to
  per-segment.
- ⚠️ ~9% per-batch mismatch on CJK tables at default size 10; mitigated
  by automatic per-segment fallback.
- ⚠️ Tune `DASHSCOPE_BATCH_SIZE` lower (e.g. 5) if a specific job
  retries too much.

## References

- `CLAUDE.md` → `.env.example` `DASHSCOPE_BATCH_SIZE` documentation
- `backend/src/app/llm/translator.py`
- Empirical data: job `84546d53` (CJK table benchmark)
