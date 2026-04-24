"""
Core translation function — one API call per segment.

Prior impl joined segments with '\\n' and sent one batched call, parsing the
response by splitting on '\\n'. qwen-mt-turbo does not reliably preserve line
count — real-world Japanese documents produced 151 output lines for 142 input
segments (model inserted line breaks inside translations). That's an
unfixable correctness gap for batched newline-delimited I/O.

Switch to per-segment calls with bounded concurrency. Cost is negligible
(~$0.003 extra per 10K-segment document at qwen-mt-turbo pricing) and
correctness is guaranteed: each response maps 1:1 to its input.

Pitfalls (AI-SPEC §3):
- No system message (qwen-mt-turbo treats it as text to translate)
- No temperature (not supported by MT models; may cause rejection)
- Non-streaming (simpler; each call is short)
- Guard message.content in case model returns None
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
from typing import Sequence

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.llm.terminology import glossary_to_terms

logger = logging.getLogger(__name__)

# Bounded concurrency inside translate_batch. DashScope intl free tier has a tight
# QPS cap — empirically concurrency >= 2 triggers persistent HTTP 429 on 300+-segment
# docs. Keep at 1 (serial) for the PoC; DashScope paid tier can bump this via env.
_PER_CALL_CONCURRENCY = 1

# Per-segment retry: transient 429 / 5xx / connection errors get retried in-place
# without bubbling up to the worker's batch-level retry. This avoids losing the
# 3/4 successful segments in a batch when one segment trips the rate limit.
_PER_CALL_MAX_RETRIES = 6
_PER_CALL_BACKOFF_BASE = 1.5  # 1.5s, 2.25s, 3.4s, 5s, 7.6s, 11.4s (~31s total)

# Forced pacing between successful calls — DashScope intl free tier caps around 60 RPM.
# Sleep 1.2s per call gives ~50 RPM steady-state, comfortably below the limit.
# Set DASHSCOPE_PACE_SECONDS=0 in env to disable (for paid-tier accounts).
import os as _os
_PACE_SECONDS = float(_os.environ.get("DASHSCOPE_PACE_SECONDS", "1.2"))


def _nfc(s: str) -> str:
    """CORE-04: NFC Unicode normalization."""
    return unicodedata.normalize("NFC", s)


def _is_passthrough(seg: str) -> bool:
    """CORE-05: skip non-translatable segments (whitespace-only, digit-only)."""
    stripped = seg.strip()
    return not stripped or stripped.isdigit()


async def translate_batch(
    client: AsyncOpenAI,
    segments: Sequence[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]:
    """
    Translate a batch of text segments via one qwen-mt-turbo call per segment.

    Invariants enforced:
    - CORE-03: returned list length == input length (guaranteed by per-segment calls,
               no parsing step that could miscount)
    - CORE-04: NFC normalization applied to every input AND output string
    - CORE-05: whitespace-only / digit-only segments are passed through unchanged

    Args:
        client: AsyncOpenAI instance pointed at DashScope intl endpoint
        segments: non-empty sequence of text segments to translate
        source_lang: source language code (e.g. "en", "vi", "ja")
        target_lang: target language code
        glossary: optional {source_term: target_term} dict for terminology control
        model: DashScope model ID (default: qwen-mt-turbo)

    Returns:
        list[str] of translated segments, same length as input, NFC-normalized

    Raises:
        ValueError: if segments is empty
    """
    if not segments:
        raise ValueError("translate_batch: segments must be non-empty")

    # CORE-04: NFC-normalize all input segments
    normalised = [_nfc(seg) for seg in segments]

    translation_options: dict = {"source_lang": source_lang, "target_lang": target_lang}
    if glossary:
        translation_options["terms"] = glossary_to_terms(glossary)

    sem = asyncio.Semaphore(_PER_CALL_CONCURRENCY)

    async def _translate_one(text: str) -> str:
        # CORE-05: passthrough — never send to the model
        if _is_passthrough(text):
            return text

        last_exc: Exception | None = None
        for attempt in range(_PER_CALL_MAX_RETRIES):
            async with sem:
                try:
                    # NEVER pass temperature (AI-SPEC Pitfall #3 — not supported by MT models)
                    # NEVER add a system message (AI-SPEC Pitfall #2 — treated as text to translate)
                    # max_tokens=4096 required (AI-SPEC §4b.3)
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": text}],
                        extra_body={"translation_options": translation_options},
                        max_tokens=4096,
                    )
                    content = response.choices[0].message.content
                    # Forced pacing — spaces out successful calls to stay under RPM cap
                    if _PACE_SECONDS > 0:
                        await asyncio.sleep(_PACE_SECONDS)
                    return _nfc(content) if content is not None else ""
                except RateLimitError as exc:
                    last_exc = exc
                except APIStatusError as exc:
                    # 4xx (non-429): bad input — no point retrying
                    if exc.status_code < 500:
                        raise
                    last_exc = exc
                except APIConnectionError as exc:
                    last_exc = exc
            # Sleep OUTSIDE the semaphore so other concurrent calls can proceed
            wait = _PER_CALL_BACKOFF_BASE ** (attempt + 1)
            logger.warning(
                "per_call_retry attempt=%d wait=%.1fs err=%s",
                attempt + 1, wait, type(last_exc).__name__,
            )
            await asyncio.sleep(wait)

        assert last_exc is not None
        raise last_exc

    results = await asyncio.gather(*(_translate_one(seg) for seg in normalised))

    # CORE-03 guarantee by construction — asyncio.gather preserves input order and
    # length, and every coroutine returns exactly one str.
    assert len(results) == len(normalised), "translate_batch length invariant violated"
    return results
