"""
Core translation batch function.

Enforces CORE-03/04/05 invariants. CORE-06 retry lives in translate_worker.

Pitfalls (AI-SPEC §3):
- No system message (qwen-mt-turbo treats it as text to translate)
- No temperature (not supported by MT models; may cause rejection)
- Non-streaming (CORE-03 requires the full response to count lines)
- Guard message.content with "or ''" in case model returns None
"""
from __future__ import annotations

import unicodedata
from typing import Sequence

from openai import AsyncOpenAI

from app.llm.terminology import glossary_to_terms

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
    Translate a batch of text segments in a single qwen-mt-turbo call.

    Invariants enforced:
    - CORE-03: len(translated_lines) must equal len(payload_segments); raises ValueError on mismatch
    - CORE-04: NFC normalization applied to every input AND output string
    - CORE-05: whitespace-only / digit-only segments are replaced with ⟦T{n}⟧ placeholders
               and passed through unchanged (not sent to the model for translation)

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
        ValueError: if translated line count does not match segment count (CORE-03)
    """
    if not segments:
        raise ValueError("translate_batch: segments must be non-empty")

    # CORE-04: NFC-normalize all input segments
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
        translation_options["terms"] = glossary_to_terms(glossary)

    # NEVER pass temperature (AI-SPEC Pitfall #3 — not supported by MT models)
    # NEVER add a system message (AI-SPEC Pitfall #2 — treated as text to translate)
    # max_tokens=4096 required (AI-SPEC §4b.3)
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        extra_body={"translation_options": translation_options},
        max_tokens=4096,
    )

    raw_content = response.choices[0].message.content
    # Guard: None content → treat as 0 lines so CORE-03 fires (not as 1 empty line)
    if raw_content is None:
        translated_lines: list[str] = []
    else:
        translated_lines = raw_content.split("\n")

    # CORE-03: segment count assertion — raise immediately on mismatch
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
            result.append(_nfc(translated))  # CORE-04: NFC-normalize output

    return result
