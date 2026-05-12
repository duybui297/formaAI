"""
Core translation function — sentinel-batched + dedup'd API calls.

Evolution:
  v1: joined segments with '\\n' → BROKE on real Japanese docs (line count drift)
  v2: per-segment calls (one API call per unique post-NFC segment) — correct
      but expensive on table-heavy PDFs (job 7f958166: ~830 calls/run, ~25 min)
  v3 (current): sentinel-batched per-call after dedup. Pack uniques into
      groups of ~_BATCH_TARGET_SIZE joined by '|||' (validated by Spike 001 —
      100% sentinel survival across en/vi/ja/zh). Literal '|||' inside a cell
      is escaped to ⟦C{n}⟧ before join (validated by Spike 002). On count
      mismatch (model dropped or added a sentinel) falls back to per-segment
      for that batch. ~50× call reduction on the demo job.

Pitfalls (AI-SPEC §3):
- No system message (qwen-mt-turbo treats it as text to translate)
- No temperature (not supported by MT models; may cause rejection)
- Non-streaming (simpler; each call is short)
- Guard message.content in case model returns None
- Sentinels must contain ZERO dictionary tokens (Spike 001: '⟦CELL⟧' fails
  because 'CELL' is translated to Ô / 細胞 / TẾ BÀO). '|||' is pure ASCII
  punctuation and ⟦C{n}⟧ uses numeric suffix — both safe.
"""
from __future__ import annotations

import asyncio
import logging
import unicodedata
from typing import Sequence

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from app.llm.terminology import glossary_to_terms
from app.pipeline.placeholder import extract_placeholders, restore_placeholders

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

# Sentinel for sentinel-batched translation. Spike 001 validated 100% survival
# across en/vi/ja/zh on qwen-mt-plus + qwen-mt-turbo. NEVER change this without
# re-running the spike — the choice depends on the empirical property that the
# model does NOT translate the token (no dictionary surface).
_BATCH_SEP = "|||"

# Max uniques per batched call. Empirically tuned: batch=25 produced ~24%
# mismatch rate on job 84546d53 (model occasionally drops a sentinel between
# adjacent short CJK cells). Drop probability is roughly independent per
# sentinel, so larger batches multiply the failure chance.
#   Batch 10 → ~9% mismatch (per-segment fallback for 9% of batches)
#   Batch  5 → ~4% mismatch
# Override via DASHSCOPE_BATCH_SIZE env. Smaller is safer at the cost of more
# API calls; tune up if your model + language pair shows low drop rates.
_BATCH_TARGET_SIZE = int(_os.environ.get("DASHSCOPE_BATCH_SIZE", "10"))


def _nfc(s: str) -> str:
    """CORE-04: NFC Unicode normalization."""
    return unicodedata.normalize("NFC", s)


def _is_passthrough(seg: str) -> bool:
    """CORE-05: skip non-translatable segments (whitespace-only, digit-only)."""
    stripped = seg.strip()
    return not stripped or stripped.isdigit()


def _escape_sentinel_in_cell(text: str) -> tuple[str, dict[int, str]]:
    """
    Escape literal '|||' occurrences inside a cell so they survive the join+split
    round-trip. Each occurrence becomes ⟦C{n}⟧ (numeric suffix, per Spike 001
    rule on no-dictionary tokens). Returns (escaped_text, restore_map).

    Spike 002 confirmed: ⟦P0⟧-style escapes survive qwen-mt-* en→vi end-to-end.
    """
    if _BATCH_SEP not in text:
        return text, {}
    tokens: dict[int, str] = {}
    parts = text.split(_BATCH_SEP)
    rebuilt = parts[0]
    for i, p in enumerate(parts[1:]):
        marker = f"⟦C{i}⟧"
        tokens[i] = _BATCH_SEP
        rebuilt += marker + p
    return rebuilt, tokens


def _restore_sentinel_in_cell(text: str, tokens: dict[int, str]) -> str:
    """Reverse of _escape_sentinel_in_cell. Replaces ⟦C{n}⟧ → '|||' per token."""
    for idx in tokens:
        text = text.replace(f"⟦C{idx}⟧", _BATCH_SEP)
    return text


async def translate_batch(
    client: AsyncOpenAI,
    segments: Sequence[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str | None = None,
) -> list[str]:
    """
    Translate a batch of text segments via sentinel-batched DashScope calls.

    Invariants enforced:
    - CORE-03: returned list length == input length (guaranteed by mapping back
               through translation_map; never split-from-model-response)
    - CORE-04: NFC normalization applied to every input AND output string
    - CORE-05: whitespace-only / digit-only segments are passed through unchanged;
               URLs, emails, {{template_vars}}, ${vars}, ISO dates, and version
               strings are masked with ⟦T{n}⟧ markers before the model call and
               restored afterwards so they never get translated or hallucinated
    - DEDUP:   identical (post-NFC) segments are translated exactly once and the
               result is broadcast to every matching input index.
    - BATCH:   unique non-passthrough segments are packed into groups joined by
               '|||' (Spike 001-validated sentinel), one API call per group.
               On count mismatch in the model's response, falls back to
               per-segment for that batch.

    Args:
        client: AsyncOpenAI instance pointed at DashScope intl endpoint
        segments: non-empty sequence of text segments to translate
        source_lang: source language code (e.g. "en", "vi", "ja")
        target_lang: target language code
        glossary: optional {source_term: target_term} dict for terminology control
        model: DashScope model ID. If None, reads `dashscope_model` from settings
               (env: DASHSCOPE_MODEL, default: qwen-mt-turbo).

    Returns:
        list[str] of translated segments, same length as input, NFC-normalized

    Raises:
        ValueError: if segments is empty
    """
    if not segments:
        raise ValueError("translate_batch: segments must be non-empty")

    if model is None:
        from app.core.config import get_settings
        model = get_settings().dashscope_model

    # CORE-04: NFC-normalize all input segments
    normalised = [_nfc(seg) for seg in segments]

    translation_options: dict = {"source_lang": source_lang, "target_lang": target_lang}
    if glossary:
        translation_options["terms"] = glossary_to_terms(glossary)

    sem = asyncio.Semaphore(_PER_CALL_CONCURRENCY)

    async def _api_call(content: str) -> str:
        """One API call with retry. Returns content or raises last exception."""
        last_exc: Exception | None = None
        for attempt in range(_PER_CALL_MAX_RETRIES):
            async with sem:
                try:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": content}],
                        extra_body={"translation_options": translation_options},
                        max_tokens=4096,
                    )
                    body = response.choices[0].message.content
                    if _PACE_SECONDS > 0:
                        await asyncio.sleep(_PACE_SECONDS)
                    return body or ""
                except RateLimitError as exc:
                    last_exc = exc
                except APIStatusError as exc:
                    # 4xx (non-429): bad input — no point retrying
                    if exc.status_code < 500:
                        raise
                    last_exc = exc
                except APIConnectionError as exc:
                    last_exc = exc
            wait = _PER_CALL_BACKOFF_BASE ** (attempt + 1)
            logger.warning(
                "per_call_retry attempt=%d wait=%.1fs err=%s",
                attempt + 1, wait, type(last_exc).__name__,
            )
            await asyncio.sleep(wait)

        assert last_exc is not None
        raise last_exc

    async def _translate_single(text: str) -> str:
        """Translate one segment. Used for size-1 batches and count-mismatch fallback."""
        if _is_passthrough(text):
            return text
        masked, tokens = extract_placeholders(text)
        body = await _api_call(masked)
        return restore_placeholders(_nfc(body), tokens)

    async def _translate_pack(cells: list[str]) -> list[str]:
        """
        Translate len(cells) non-passthrough cells in ONE API call by joining
        with the sentinel. On count mismatch in the response, falls back to
        per-segment translation for this batch.
        """
        if len(cells) == 1:
            return [await _translate_single(cells[0])]

        # Per-cell mask chain: CORE-05 placeholders THEN sentinel escape.
        # Both use ⟦…⟧ brackets but different letter prefixes (T vs C) so
        # restoration is unambiguous.
        prepared: list[tuple[str, dict[int, str], dict[int, str]]] = []
        for cell in cells:
            masked, core5_tokens = extract_placeholders(cell)
            escaped, sentinel_tokens = _escape_sentinel_in_cell(masked)
            prepared.append((escaped, core5_tokens, sentinel_tokens))

        joined = _BATCH_SEP.join(p[0] for p in prepared)
        body = await _api_call(joined)
        parts = body.split(_BATCH_SEP) if body else []

        if len(parts) != len(cells):
            # Model drift — defensive fallback. Logged at WARN so operators can
            # tune _BATCH_TARGET_SIZE if this fires frequently. Input/output
            # samples capped at 200 chars so logs don't explode on long cells.
            joined_preview = joined[:200] + ("…" if len(joined) > 200 else "")
            body_preview = (body or "")[:200] + ("…" if body and len(body) > 200 else "")
            logger.warning(
                "batch_count_mismatch expected=%d got=%d, falling back per-segment "
                "(joined=%r body=%r)",
                len(cells), len(parts), joined_preview, body_preview,
            )
            return await asyncio.gather(*(_translate_single(c) for c in cells))

        results: list[str] = []
        for part, (_, core5_tokens, sentinel_tokens) in zip(parts, prepared):
            restored = _restore_sentinel_in_cell(part, sentinel_tokens)
            restored = restore_placeholders(_nfc(restored), core5_tokens)
            results.append(restored)
        return results

    # DEDUP: collapse identical post-NFC segments to one translation each.
    unique_segments = list(dict.fromkeys(normalised))

    # Split: passthroughs short-circuit to identity, translatables go through batches.
    passthroughs = [u for u in unique_segments if _is_passthrough(u)]
    translatables = [u for u in unique_segments if not _is_passthrough(u)]

    # BATCH: pack translatables into fixed-size groups joined by the sentinel.
    batches = [
        translatables[i:i + _BATCH_TARGET_SIZE]
        for i in range(0, len(translatables), _BATCH_TARGET_SIZE)
    ]

    # Translate each batch. Each batch is one API call (with retry). Batches run
    # in parallel under the same _PER_CALL_CONCURRENCY semaphore.
    batch_outputs = await asyncio.gather(*(_translate_pack(b) for b in batches))

    # Assemble translation_map from passthroughs + batched results.
    translation_map: dict[str, str] = {p: p for p in passthroughs}
    for batch, outputs in zip(batches, batch_outputs):
        for original, translated in zip(batch, outputs):
            translation_map[original] = translated

    # Map back to original input order (every index resolves via dedup lookup).
    results = [translation_map[seg] for seg in normalised]

    assert len(results) == len(normalised), "translate_batch length invariant violated"
    return results
