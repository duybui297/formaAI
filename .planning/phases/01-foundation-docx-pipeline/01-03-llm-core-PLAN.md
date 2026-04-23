---
phase: 01-foundation-docx-pipeline
plan: "03"
type: tdd
wave: 1
depends_on:
  - "02"
files_modified:
  - backend/src/app/llm/__init__.py
  - backend/src/app/llm/client.py
  - backend/src/app/llm/schemas.py
  - backend/src/app/llm/terminology.py
  - backend/src/app/llm/token_budget.py
  - backend/src/app/llm/translator.py
  - backend/tests/llm/__init__.py
  - backend/tests/llm/test_translator.py
  - backend/tests/llm/test_token_budget.py
  - backend/tests/llm/test_terminology.py
autonomous: true
requirements:
  - CORE-01
  - CORE-02
  - CORE-03
  - CORE-04
  - CORE-05
  - CORE-06
  - INFRA-01
  - INFRA-02
  - LANG-01

must_haves:
  truths:
    - "translate_batch enforces CORE-03 segment count assertion on every call"
    - "translate_batch applies NFC normalization to input and output (CORE-04)"
    - "translate_batch replaces whitespace-only and digit-only segments with ⟦T{n}⟧ stubs (CORE-05)"
    - "make_llm_client creates AsyncOpenAI with max_retries=0 and dashscope-intl base_url"
    - "pack_into_batches respects token budget and handles oversized single segments (D-08)"
    - "translate_batch never passes temperature or a system message to qwen-mt-turbo"
    - "terminology dict converts to translation_options.terms list correctly"
  artifacts:
    - path: "backend/src/app/llm/client.py"
      provides: "make_llm_client(settings) -> AsyncOpenAI factory"
      exports: ["make_llm_client"]
    - path: "backend/src/app/llm/translator.py"
      provides: "translate_batch() with all CORE invariants"
      exports: ["translate_batch"]
    - path: "backend/src/app/llm/token_budget.py"
      provides: "estimate_tokens() and pack_into_batches() with D-08 oversized segment handling"
      exports: ["estimate_tokens", "pack_into_batches", "SegmentTooLargeError"]
    - path: "backend/src/app/llm/schemas.py"
      provides: "TranslateBatchRequest, TranslateBatchResponse, assert_segment_count"
      exports: ["TranslateBatchRequest", "TranslateBatchResponse", "assert_segment_count", "TokenUsage"]
    - path: "backend/src/app/llm/terminology.py"
      provides: "glossary_to_terms() mapping"
      exports: ["glossary_to_terms"]
    - path: "backend/tests/llm/test_translator.py"
      provides: "Tests for CORE-03/04/05/06 invariants using mock AsyncOpenAI"
    - path: "backend/tests/llm/test_token_budget.py"
      provides: "Tests for pack_into_batches edge cases including oversized segments"
  key_links:
    - from: "backend/src/app/llm/translator.py"
      to: "AsyncOpenAI.chat.completions.create"
      via: "extra_body={'translation_options': {...}}"
      pattern: "extra_body"
    - from: "backend/src/app/llm/translator.py"
      to: "CORE-03 assertion"
      via: "len(translated_lines) != len(payload_segments)"
      pattern: "CORE-03 violation"
---

<objective>
Implement the complete LLM core: AsyncOpenAI client factory, Pydantic batch schemas, translate_batch() with all four CORE invariants (03/04/05/06), token-budget batch packer, terminology mapper, and comprehensive unit tests for every invariant.

Purpose: This is the translation engine. All pipeline plans (DOCX, worker) depend on translate_batch() being correct before they run.
Output: backend/src/app/llm/ fully implemented and tested. Unit tests pass without any network calls (mock LLM client).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md
@.planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- Exact code patterns from AI-SPEC §3 and §4 — copy verbatim -->

translate_batch signature (AI-SPEC §3):
```python
async def translate_batch(
    client: AsyncOpenAI,
    segments: Sequence[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]:
```

Key invariants (AI-SPEC §3):
- CORE-04: nfc = lambda s: unicodedata.normalize("NFC", s); apply to input AND output
- CORE-05: stripped.isdigit() or not stripped → passthrough stub ⟦T{n}⟧
- CORE-03: len(translated_lines) != len(payload_segments) → raise ValueError("CORE-03 violation: ...")
- No system message, no temperature, guard response.choices[0].message.content with "or ''"

make_llm_client (AI-SPEC §4):
```python
def make_llm_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=str(settings.dashscope_base_url),
        max_retries=0,   # CORE-06 retry is in the worker, not the SDK
        timeout=60.0,
    )
```

pack_into_batches (AI-SPEC §4):
```python
def pack_into_batches(segments: list[str], budget_tokens: int = 3000) -> list[list[str]]:
    # oversized single segment: if estimate_tokens(seg) > 7000 → raise SegmentTooLargeError
```

CORE-06 retry (AI-SPEC §4, to be used by worker — defined in translator as translate_batch, retry in worker):
  _MAX_RETRIES = 3; _BACKOFF_BASE = 2.0 (sleep 2s, 4s, 8s)
  Retry on: RateLimitError, APIStatusError where status >= 500, APIConnectionError
  Do NOT retry: 4xx except 429

Pitfalls (MUST avoid):
  - NEVER add {"role": "system", ...} — qwen-mt-turbo treats as text to translate
  - NEVER pass temperature= parameter
  - NEVER use streaming for translate_batch (need full response for CORE-03)
  - max_tokens=4096 on every call (AI-SPEC §4b.3)
</interfaces>
</context>

<tasks>

<task type="tdd">
  <name>Task 1: Implement LLM Core (translate_batch + schemas + client + terminology)</name>
  <files>
    backend/src/app/llm/__init__.py
    backend/src/app/llm/client.py
    backend/src/app/llm/schemas.py
    backend/src/app/llm/terminology.py
    backend/tests/llm/__init__.py
    backend/tests/llm/test_translator.py
    backend/tests/llm/test_terminology.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 3 translate_batch full excerpt, Section 4 client factory, Section 4b.1 Pydantic schemas, Section 4b.3 prompt discipline)
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (llm/client.py, llm/translator.py, llm/schemas.py pattern sections)
    backend/src/app/core/config.py (Settings class interface)
  </read_first>
  <behavior>
    RED — write tests first:
    - test_translate_batch_returns_same_count: mock client returns 2 lines for 2 segments → assert len(result)==2
    - test_translate_batch_core03_raises_on_mismatch: mock returns 1 line for 2 segments → assert ValueError("CORE-03 violation")
    - test_translate_batch_core04_nfc_normalizes_output: mock returns NFD Vietnamese string → result[0] is NFC form
    - test_translate_batch_core05_whitespace_passthrough: segment is "   " → not sent to model, returned as-is
    - test_translate_batch_core05_digit_passthrough: segment is "42" → not sent to model, returned as-is
    - test_translate_batch_no_system_message: capture call args → assert no "role"=="system" in messages
    - test_translate_batch_no_temperature: capture call args → assert "temperature" not in call kwargs
    - test_translate_batch_with_glossary: glossary={"term": "термин"} → extra_body contains "terms" list
    - test_translate_batch_empty_segments_raises: segments=[] → ValueError
    - test_translate_batch_none_content_triggers_core03: mock returns content=None → ValueError (CORE-03 on 0 lines)
    - test_glossary_to_terms_converts_dict: {"a": "b", "c": "d"} → [{"source":"a","target":"b"},{"source":"c","target":"d"}]
    - test_glossary_to_terms_empty_dict_returns_empty: {} → []
  </behavior>
  <action>
RED: Write all tests in backend/tests/llm/test_translator.py and test_terminology.py (see behavior block).

GREEN: Implement the production code:

`backend/src/app/llm/__init__.py` (empty)
`backend/tests/llm/__init__.py` (empty)

`backend/src/app/llm/client.py` — exact pattern from AI-SPEC §4:
```python
from __future__ import annotations
from openai import AsyncOpenAI
from app.core.config import Settings


def make_llm_client(settings: Settings) -> AsyncOpenAI:
    """
    Factory for the shared AsyncOpenAI client.
    Create ONCE at arq worker startup; store in ctx["llm_client"].
    max_retries=0: CORE-06 retry lives in translate_worker, not the SDK.
    """
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=str(settings.dashscope_base_url),
        max_retries=0,
        timeout=60.0,
    )
```

`backend/src/app/llm/schemas.py` — exact from AI-SPEC §4b.1:
```python
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator


class TokenUsage(BaseModel, frozen=True):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TranslateBatchRequest(BaseModel, frozen=True):
    segments: list[str] = Field(..., min_length=1)
    source_lang: str
    target_lang: str
    glossary: dict[str, str] | None = None
    model: str = "qwen-mt-turbo"


class TranslateBatchResponse(BaseModel, frozen=True):
    segments: list[str]
    usage: TokenUsage

    @model_validator(mode="after")
    def _validate_non_empty(self) -> "TranslateBatchResponse":
        if not self.segments:
            raise ValueError("TranslateBatchResponse.segments must be non-empty")
        return self


def assert_segment_count(
    request: TranslateBatchRequest,
    response: TranslateBatchResponse,
) -> None:
    """CORE-03: raises ValueError with full context on count mismatch."""
    if len(response.segments) != len(request.segments):
        raise ValueError(
            f"CORE-03 segment count mismatch: "
            f"expected={len(request.segments)}, got={len(response.segments)}, "
            f"model={request.model}, src={request.source_lang}, tgt={request.target_lang}"
        )
```

`backend/src/app/llm/terminology.py`:
```python
from __future__ import annotations


def glossary_to_terms(glossary: dict[str, str]) -> list[dict[str, str]]:
    """
    Convert {source_term: target_term} dict to qwen-mt-turbo translation_options.terms list.
    Documents migration cost: this format is DashScope-specific.
    If swapping to Azure OpenAI, inject glossary as prompt text instead.
    """
    return [{"source": src, "target": tgt} for src, tgt in glossary.items()]
```

`backend/src/app/llm/translator.py` — full translate_batch from AI-SPEC §3, verbatim:
```python
from __future__ import annotations
import unicodedata
from typing import Sequence
from openai import AsyncOpenAI


_PLACEHOLDER_PREFIX = "⟦T"
_PLACEHOLDER_SUFFIX = "⟧"


def _nfc(s: str) -> str:
    """CORE-04: NFC Unicode normalization."""
    return unicodedata.normalize("NFC", s)


async def translate_batch(
    client: AsyncOpenAI,
    segments: Sequence[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]:
    """
    Translate a batch of segments in a single qwen-mt-turbo call.
    Enforces CORE-03/04/05. Retry (CORE-06) lives in translate_worker.

    Pitfalls (AI-SPEC §3):
    - No system message (qwen-mt-turbo treats it as text to translate)
    - No temperature (not supported by MT models)
    - Non-streaming (CORE-03 needs full response)
    - Guard message.content with "or ''"
    """
    if not segments:
        raise ValueError("translate_batch: segments must be non-empty")

    # CORE-04: NFC-normalise input
    normalised = [_nfc(seg) for seg in segments]

    # CORE-05: whitespace-only / digit-only → passthrough stubs
    passthrough_indices: set[int] = set()
    payload_segments: list[str] = []
    for i, seg in enumerate(normalised):
        stripped = seg.strip()
        if not stripped or stripped.isdigit():
            passthrough_indices.add(i)
            payload_segments.append(f"{_PLACEHOLDER_PREFIX}{i}{_PLACEHOLDER_SUFFIX}")
        else:
            payload_segments.append(seg)

    user_content = "\n".join(payload_segments)

    translation_options: dict = {"source_lang": source_lang, "target_lang": target_lang}
    if glossary:
        from app.llm.terminology import glossary_to_terms
        translation_options["terms"] = glossary_to_terms(glossary)

    # NEVER pass temperature (AI-SPEC Pitfall #3)
    # NEVER add system message (AI-SPEC Pitfall #2)
    # max_tokens required (AI-SPEC §4b.3)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        extra_body={"translation_options": translation_options},
        max_tokens=4096,
    )

    raw_output = response.choices[0].message.content or ""
    translated_lines = raw_output.split("\n")

    # CORE-03: segment count assertion
    if len(translated_lines) != len(payload_segments):
        raise ValueError(
            f"CORE-03 violation: sent {len(payload_segments)} segments, "
            f"received {len(translated_lines)} translated lines. "
            f"model={model}, source_lang={source_lang}, target_lang={target_lang}"
        )

    result: list[str] = []
    for i, (orig, translated) in enumerate(zip(normalised, translated_lines)):
        if i in passthrough_indices:
            result.append(orig)
        else:
            result.append(_nfc(translated))  # CORE-04: NFC output

    return result
```

REFACTOR: ensure all tests still pass after any cleanup.
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      uv run pytest tests/llm/test_translator.py tests/llm/test_terminology.py -v --no-header 2>&amp;1 | tail -5
    </automated>
  </verify>
  <done>
    All translator and terminology unit tests pass (no network calls — mock LLM used).
    translate_batch raises ValueError("CORE-03 violation") on count mismatch.
    translate_batch applies NFC to input and output strings.
    Whitespace-only and digit-only segments pass through without LLM call.
    No system message or temperature in API call.
    glossary_to_terms converts dict to [{source, target}] list.
  </done>
</task>

<task type="tdd">
  <name>Task 2: Implement Token Budget Packer (token_budget.py)</name>
  <files>
    backend/src/app/llm/token_budget.py
    backend/tests/llm/test_token_budget.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 4 Context Window Strategy — pack_into_batches + estimate_tokens full excerpt, D-08 oversized segment)
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (token_budget.py pattern section)
  </read_first>
  <behavior>
    RED — write tests first:
    - test_pack_single_small_segment: ["hello"] → [[["hello"]]], one batch
    - test_pack_multiple_segments_one_batch: 5 short segments under budget → 1 batch
    - test_pack_splits_when_budget_exceeded: many short segments → correct multi-batch split
    - test_pack_oversized_single_segment_own_batch: segment with 6000 tokens alone → own batch (no error, just alone)
    - test_pack_oversized_exceeds_hard_limit_raises: segment > 7000 tokens → raises SegmentTooLargeError
    - test_pack_empty_segments_returns_empty: [] → []
    - test_estimate_tokens_non_empty: "hello world" → positive int
    - test_estimate_tokens_empty_string: "" → 0
    - test_oversized_error_contains_segment_info: SegmentTooLargeError has segment_id and token_count attributes
    - test_pack_cjk_heavy_text: 10-char CJK string → fewer tokens than 10-char Latin (ratio difference)
  </behavior>
  <action>
RED: Write tests in backend/tests/llm/test_token_budget.py.

GREEN: Implement backend/src/app/llm/token_budget.py (exact AI-SPEC §4 excerpt):

```python
from __future__ import annotations
import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")
_HARD_LIMIT = 7000   # AI-SPEC §4: segments > 7K tokens → SegmentTooLargeError (D-08)


class SegmentTooLargeError(Exception):
    """Raised when a single segment exceeds the 7K input token hard limit (D-08)."""
    def __init__(self, segment_id: str, token_count: int, source_text_excerpt: str) -> None:
        self.segment_id = segment_id
        self.token_count = token_count
        self.source_text_excerpt = source_text_excerpt
        super().__init__(
            f"Segment {segment_id} has {token_count} tokens, exceeding the 7000-token limit. "
            f"Text excerpt: {source_text_excerpt[:200]!r}"
        )


def estimate_tokens(text: str) -> int:
    """
    Fast token estimate using tiktoken cl100k_base as qwen tokenizer approximation.
    Accurate to ~10-15%; suitable for batch budget estimation.
    """
    if not text:
        return 0
    return len(_ENC.encode(text))


def pack_into_batches(
    segments: list[str],
    budget_tokens: int = 3000,
    segment_ids: list[str] | None = None,
) -> list[list[str]]:
    """
    Pack segments into token-budgeted batches for qwen-mt-turbo.
    A segment alone exceeding budget_tokens is placed in its own batch.
    A segment exceeding _HARD_LIMIT (7000) raises SegmentTooLargeError (D-08).
    Never splits a segment mid-sentence — DOCX-02 invariant.
    """
    if not segments:
        return []

    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens: int = 0

    for i, seg in enumerate(segments):
        seg_tokens = estimate_tokens(seg)
        seg_id = (segment_ids[i] if segment_ids else None) or f"seg_{i}"

        # D-08: hard limit check
        if seg_tokens > _HARD_LIMIT:
            raise SegmentTooLargeError(
                segment_id=seg_id,
                token_count=seg_tokens,
                source_text_excerpt=seg,
            )

        if current_batch and (current_tokens + seg_tokens > budget_tokens):
            batches.append(current_batch)
            current_batch = [seg]
            current_tokens = seg_tokens
        else:
            current_batch.append(seg)
            current_tokens += seg_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
```

REFACTOR: ensure coverage of edge cases and cleanup.
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      uv run pytest tests/llm/test_token_budget.py -v --no-header 2>&amp;1 | tail -5
    </automated>
  </verify>
  <done>
    All token_budget unit tests pass.
    pack_into_batches respects budget_tokens, handles oversized-but-below-hard-limit segments as own batch, raises SegmentTooLargeError for >7000-token segments.
    estimate_tokens returns 0 for empty string, positive int for non-empty.
    SegmentTooLargeError has segment_id and token_count attributes.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| segment text → qwen-mt-turbo | User document content crosses to external Alibaba Cloud LLM |
| qwen response → pipeline | LLM output must be count-validated before use |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-01 | Tampering | translate_batch CORE-03 assertion | mitigate | Assert len(translated_lines) == len(payload_segments) before any write-back; raise ValueError on mismatch |
| T-03-02 | Information Disclosure | DASHSCOPE_API_KEY in make_llm_client | mitigate | settings.dashscope_api_key.get_secret_value() — never passed as string literal; never logged |
| T-03-03 | Denial of Service | SegmentTooLargeError (D-08) | mitigate | Raise immediately with clear error rather than sending oversized batch that could hold worker slot |
| T-03-04 | Tampering | Placeholder restoration after translation | mitigate | Assertion: no unreplaced ⟦T{n}⟧ markers in restored output (placeholder.py in Plan 05) |
| T-03-05 | Information Disclosure | User document content sent to DashScope | accept | Internal PoC; flagged in CONTEXT.md for AICore data-residency review before external use |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/llm/ -v` — all tests pass, 0 failures
2. `grep -q "max_retries=0" backend/src/app/llm/client.py` — passes
3. `grep -q "CORE-03 violation" backend/src/app/llm/translator.py` — passes
4. `grep -q "temperature" backend/src/app/llm/translator.py` — returns nothing (temperature not set)
5. `grep -q "SegmentTooLargeError" backend/src/app/llm/token_budget.py` — passes
6. `grep -q '{"role": "system"' backend/src/app/llm/translator.py` — returns nothing (no system message)
</verification>

<success_criteria>
- All LLM unit tests pass (min 12 tests across 3 test files)
- translate_batch raises ValueError("CORE-03 violation") when response line count mismatches
- translate_batch applies unicodedata.normalize("NFC", ...) to every input and output string
- translate_batch sends no temperature, no system message to qwen-mt-turbo
- pack_into_batches raises SegmentTooLargeError for segments > 7000 tokens
- make_llm_client sets max_retries=0 and base_url=dashscope-intl.aliyuncs.com endpoint
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-03-SUMMARY.md`
</output>
