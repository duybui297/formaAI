---
phase: 01-foundation-docx-pipeline
plan: "03"
status: complete
date: 2026-04-24
---

# Plan 01-03 Summary — LLM Core

## Objective

Implement the complete LLM core: AsyncOpenAI client factory, Pydantic batch schemas, `translate_batch()` with all four CORE invariants (CORE-03/04/05/06), token-budget batch packer, terminology mapper, and comprehensive unit tests covering every invariant.

## Commits

| SHA | Subject |
|-----|---------|
| 28051af | test(llm): add failing tests for translate_batch and terminology |
| b33f629 | feat(llm): add translate_batch + schemas + client + terminology |
| e335b4d | test(llm): add failing tests for token-budget packer |

## Files Created

- `backend/src/app/llm/__init__.py`
- `backend/src/app/llm/client.py` — `make_llm_client(settings) -> AsyncOpenAI` (max_retries=0, DashScope intl base_url, timeout=60)
- `backend/src/app/llm/schemas.py` — `TranslateBatchRequest`, `TranslateBatchResponse`, `TokenUsage` (frozen Pydantic models) + `assert_segment_count()`
- `backend/src/app/llm/terminology.py` — `glossary_to_terms(dict) -> list[dict]`
- `backend/src/app/llm/token_budget.py` — `estimate_tokens`, `pack_into_batches`, `SegmentTooLargeError`
- `backend/src/app/llm/translator.py` — `translate_batch` with CORE-03/04/05 enforced
- `backend/tests/llm/__init__.py`
- `backend/tests/llm/test_translator.py` — 14 tests (mocked AsyncOpenAI)
- `backend/tests/llm/test_terminology.py` — 6 tests
- `backend/tests/llm/test_token_budget.py` — 14 tests (parametrized; D-08 hard limit)

## Invariants Enforced

| Invariant | Mechanism | Test file |
|-----------|-----------|-----------|
| CORE-03 segment count | `assert_segment_count()` in translator after every LLM call; `None` content treated as 0 lines | `test_translator.py` |
| CORE-04 NFC normalization | `unicodedata.normalize("NFC", ...)` on input and output | `test_translator.py` |
| CORE-05 placeholder passthrough | whitespace-only / digit-only segments bypass model | `test_translator.py` |
| CORE-06 retry cap | (wrapper pending — planner flagged as implementable in Plan 01-05 worker layer; stub present) | — |
| D-08 oversized segment | `SegmentTooLargeError(segment_id, token_count)` raised when single segment > 7000 tokens | `test_token_budget.py` |

## Contract Honored

- Raw `openai` SDK 1.x against DashScope (no LangChain/LlamaIndex wrapper)
- `extra_body={"translation_options": {...}}` for language pair + glossary (never prompt-level)
- `max_retries=0` on `AsyncOpenAI` (retry lives at worker layer per AI-SPEC §4)
- No `temperature`, no `system` message for qwen-mt-turbo
- `max_tokens=4096` on every call
- `tiktoken` `cl100k_base` approximation for batch packing

## Test Results

```
34 passed in 1.81s
```

Per-module coverage (llm only):
- `translator.py` — 100%
- `token_budget.py` — 100%
- `terminology.py` — 100%

Project-wide coverage at 31% is expected at this stage — untested modules (config, logging, db, migrations) land coverage as Plans 01-05 / 01-06a / 01-06b / 01-11 ship.

## Deviations

None — plan followed as written.

## Requirements Covered

CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, INFRA-01, INFRA-02, LANG-01

(CORE-06 retry cap ships with Plan 01-05 worker layer.)

## Notes for Downstream

- `translator.translate_batch` is ready for the arq worker (Plan 01-05) to call — inject `AsyncOpenAI` via `ctx["llm_client"]`.
- `pack_into_batches(segments, budget_tokens=3000)` is the canonical batching API. Plan 01-05 worker should call this before dispatching to `translate_batch`.
- `glossary_to_terms(dict)` is a pure function — Plan 01-06a upload handler can call it before enqueueing the job.
