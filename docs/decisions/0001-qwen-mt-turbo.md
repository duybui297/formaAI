# ADR-0001: Use `qwen-mt-turbo` over generic Qwen models

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu (project owner)

## Context

The PoC needs a translation engine that handles VN ↔ EN ↔ JA ↔ ZH at
demo quality, supports a native glossary mechanism, fits a 2–3-week
timeline, and has predictable per-job cost. Alibaba's DashScope catalog
offers several models; cost differs by ~10× between tiers.

Verified DashScope intl pricing (per 1M tokens, input / output):

| Model | Input | Output | Notes |
|---|---|---|---|
| `qwen-mt-turbo` | $0.16 | $0.49 | Translation-specialized |
| `qwen-mt-plus` | $2.46 | $7.37 | Highest MT quality |
| `qwen3.5-plus` | $0.40 | $2.40 | General-purpose |
| `qwen3-max` | $1.20 | $6.00 | General-purpose |

## Decision

Use **`qwen-mt-turbo`** as the default translation model. Allow override
per deployment via `DASHSCOPE_MODEL` env var. `qwen-mt-plus` is the
documented fallback for jobs that need higher quality.

## Alternatives considered

- **`qwen-mt-plus`** — 15× more expensive than turbo on output tokens;
  reserve for critical-quality jobs, not the default.
- **`qwen3.5-plus`** — general-purpose model, no native `terminology` API
  parameter; glossary would have to live in the prompt (lossy).
- **`qwen3-max`** — 10× the cost of turbo for *inferior* MT quality on
  CJK pairs per Alibaba's own benchmarks.
- **`qwen-turbo` (legacy)** — explicitly deprecated by Alibaba; migrate
  to `qwen-flash` per docs.

## Consequences

- ✅ Lowest cost in the catalog for the use case.
- ✅ Native `terminology` API parameter — first-class glossary support
  ([ADR-0008](0008-sentinel-batched-translate.md) builds on this).
- ✅ 1M token context — enough headroom for any practical batch.
- ⚠️ MT-family-specific: switching to `qwen3.5-plus` or `qwen3-max`
  disables native glossary; falls back to prompt-level
  injection.
- ⚠️ DashScope intl endpoint required — China-region key fails with
  cryptic 401 (documented in `.env.example`).

## References

- `CLAUDE.md` → *1. Qwen Model Selection*
- `.env.example` → `DASHSCOPE_MODEL`
- Alibaba pricing: https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio
