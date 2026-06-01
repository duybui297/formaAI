# Module: llm

## Purpose
Qwen/DashScope translation engine layer. Wraps the OpenAI-compatible DashScope international endpoint (`qwen-mt-turbo`) to translate batches of text segments with format-fidelity safeguards: NFC normalization, passthrough skipping, CORE-05 placeholder masking, sentinel-batched dedup'd calls, native glossary terminology injection, and token-budgeted batch packing.

## Files
| File | Responsibility |
|------|----------------|
| `client.py` | `AsyncOpenAI` client factory pointed at DashScope intl endpoint (`max_retries=0`, `timeout=60s`). |
| `translator.py` | Core `translate_batch` — NFC, passthrough, sentinel-batched + dedup'd API calls with per-call retry/pacing. |
| `terminology.py` | Maps `{source:target}` glossary dict → DashScope `translation_options.terms` list. |
| `token_budget.py` | `estimate_tokens` (tiktoken cl100k_base) + `pack_into_batches`; enforces 7K-token hard limit. |
| `schemas.py` | Frozen Pydantic request/response contracts + `assert_segment_count` (CORE-03). |

## Key functions
- `make_llm_client(settings) -> AsyncOpenAI` — factory; created once at arq worker startup, stored in `ctx["llm_client"]`. SDK retry disabled (retry owned by worker/translator).
- `translate_batch(client, segments, source_lang, target_lang, glossary=None, model=None) -> list[str]` — main entry; returns translations in input order, length == input. Defaults model to `settings.dashscope_model` (env `DASHSCOPE_MODEL`, default `qwen-mt-turbo`).
- `glossary_to_terms(glossary) -> list[dict]` — `{"contract":"Hợp đồng"}` → `[{"source":"contract","target":"Hợp đồng"}]`.
- `estimate_tokens(text) -> int` — tiktoken cl100k_base approximation (~10-15% off Qwen tokenizer).
- `pack_into_batches(segments, budget_tokens=3000, segment_ids=None) -> list[list]` — token-budgeted packing; accepts `str` or Segment-like (`.source_text`/`.id` duck-typed); never splits a segment.
- `assert_segment_count(request, response)` — CORE-03 length invariant check with diagnostic context.

## Translation logic
- **NFC normalize** (CORE-04): every input AND output string normalized via `unicodedata.normalize("NFC", ...)`.
- **Passthrough detection** (CORE-05): whitespace-only / digit-only segments short-circuit to identity (no API call).
- **Placeholder masking** (CORE-05): URLs, emails, `{{template_vars}}`, `${vars}`, ISO dates, version strings masked to `⟦T{n}⟧` via `pipeline.placeholder.extract_placeholders`, restored after.
- **Dedup**: identical post-NFC segments translated once; result broadcast to all matching indices via `translation_map`.
- **Sentinel batching** (v3): unique translatables packed into groups of `_BATCH_TARGET_SIZE` (default 10, env `DASHSCOPE_BATCH_SIZE`) joined by `|||` (`_BATCH_SEP`, Spike 001-validated as non-translated). Literal `|||` inside a cell escaped to `⟦C{n}⟧` first (`_escape_sentinel_in_cell`, Spike 002). One API call per group → ~50× call reduction vs per-segment.
- **Count-mismatch fallback**: if model's `|||`-split part count != input cell count, logs WARN and falls back to per-segment translation for that batch.
- **Glossary**: native DashScope `translation_options.terms` (not prompt text); DashScope-specific.
- **API call shape** (AI-SPEC §3): no system message, no temperature, non-streaming, `max_tokens=4096`; guards `message.content is None`.
- **Per-call retry**: `_PER_CALL_MAX_RETRIES=6` with exponential backoff (base 1.5, ~31s total) on `RateLimitError` / 5xx `APIStatusError` / `APIConnectionError`; 4xx non-429 raises immediately. Retry lives in translator, not SDK.
- **Concurrency/pacing**: `_PER_CALL_CONCURRENCY=1` (serial — free-tier QPS cap), `_PACE_SECONDS=1.2` sleep per call (~50 RPM; env `DASHSCOPE_PACE_SECONDS=0` to disable on paid tier).
- **Token hard limit** (D-08): `pack_into_batches` raises `SegmentTooLargeError` for any segment > 7000 tokens; never sentence-splits (DOCX-02 invariant).

## Inputs / outputs
- **Consumes**: `AsyncOpenAI` client, sequence of text segments (or Segment-like objects in `token_budget`), source/target language codes, optional `{source:target}` glossary dict, optional model ID, `core.config.Settings`.
- **Produces**: `list[str]` translations same length as input and NFC-normalized; `pack_into_batches` returns batches of input element type; schemas expose `TokenUsage` / `TranslateBatchRequest` / `TranslateBatchResponse`.
- **Raises**: `ValueError` (empty segments / CORE-03 count mismatch), `SegmentTooLargeError` (> 7K tokens), bubbled OpenAI errors after retry exhaustion.

## Dependencies
- `openai.AsyncOpenAI` + error types (`APIConnectionError`, `APIStatusError`, `RateLimitError`)
- `tiktoken` (cl100k_base encoding)
- `pydantic` (frozen `BaseModel`, `Field`, `model_validator`)
- Internal: `app.core.config.Settings` / `get_settings`, `app.llm.terminology.glossary_to_terms`, `app.pipeline.placeholder.extract_placeholders` / `restore_placeholders`
- Stdlib: `asyncio`, `unicodedata`, `logging`, `os`
