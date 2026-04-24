"""
Token-budget batch packer for qwen-mt-turbo.

Uses tiktoken cl100k_base (GPT-4 encoding) as an approximation of the Qwen tokenizer.
Accuracy is ~10-15% off; sufficient for batch budget estimation per D-07.

Key constraint (D-08): segments > 7000 tokens raise SegmentTooLargeError immediately.
Never sentence-split — the DOCX pipeline invariant (DOCX-02) forbids splitting mid-segment.
"""
from __future__ import annotations

from typing import Sequence, TypeVar

import tiktoken

T = TypeVar("T")

_ENC = tiktoken.get_encoding("cl100k_base")

# AI-SPEC §4: segments > 7K tokens → SegmentTooLargeError (D-08)
_HARD_LIMIT = 7000


class SegmentTooLargeError(Exception):
    """
    Raised when a single segment exceeds the 7K input token hard limit (D-08).

    Attributes:
        segment_id: identifier for the offending segment
        token_count: estimated token count that triggered the limit
        source_text_excerpt: first 200 chars of the segment for diagnostics
    """

    def __init__(self, segment_id: str, token_count: int, source_text_excerpt: str) -> None:
        self.segment_id = segment_id
        self.token_count = token_count
        self.source_text_excerpt = source_text_excerpt
        super().__init__(
            f"Segment {segment_id!r} has {token_count} tokens, exceeding the "
            f"{_HARD_LIMIT}-token limit. "
            f"Text excerpt: {source_text_excerpt[:200]!r}"
        )


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using tiktoken cl100k_base as a Qwen tokenizer approximation.

    Returns 0 for empty string. Accurate to ~10-15%; suitable for batch packing.
    """
    if not text:
        return 0
    return len(_ENC.encode(text))


def _coerce(item: T) -> tuple[str, str | None]:
    """
    Accept either a plain str or any object exposing ``.source_text`` + ``.id``
    (e.g. ``pipeline.segment.Segment``). Returns (text, optional_id).
    """
    if isinstance(item, str):
        return item, None
    text = getattr(item, "source_text", None)
    if text is None:
        raise TypeError(
            f"pack_into_batches expects str or Segment-like (with .source_text); got {type(item).__name__}"
        )
    return text, getattr(item, "id", None)


def pack_into_batches(
    segments: Sequence[T],
    budget_tokens: int = 3000,
    segment_ids: list[str] | None = None,
) -> list[list[T]]:
    """
    Pack segments into token-budgeted batches for qwen-mt-turbo.

    Accepts either ``list[str]`` (unit-test shape) or ``list[Segment]`` (pipeline shape —
    duck-typed via ``.source_text`` and ``.id``). Returns batches of the same element type.

    Rules:
    - A segment alone exceeding ``budget_tokens`` is placed in its own batch (no error).
    - A segment exceeding ``_HARD_LIMIT`` (7000 tokens) raises SegmentTooLargeError (D-08).
    - Segments are never split — DOCX-02 invariant forbids mid-segment splitting.

    Args:
        segments: list of str OR Segment-like objects (must expose ``.source_text``)
        budget_tokens: soft token budget per batch (default 3000 per D-07)
        segment_ids: optional list of IDs parallel to segments (for error reporting
            when input is ``list[str]``; ignored when input is ``list[Segment]``)

    Returns:
        list of batches, each batch a list of the same element type as input

    Raises:
        SegmentTooLargeError: if any single segment exceeds the 7000-token hard limit
    """
    if not segments:
        return []

    batches: list[list[T]] = []
    current_batch: list[T] = []
    current_tokens: int = 0

    for i, seg in enumerate(segments):
        text, inferred_id = _coerce(seg)
        seg_tokens = estimate_tokens(text)
        seg_id = inferred_id or (segment_ids[i] if segment_ids else None) or f"seg_{i}"

        # D-08: hard limit — raise immediately, never send oversized segment
        if seg_tokens > _HARD_LIMIT:
            raise SegmentTooLargeError(
                segment_id=seg_id,
                token_count=seg_tokens,
                source_text_excerpt=text,
            )

        if current_batch and (current_tokens + seg_tokens > budget_tokens):
            # Current batch would exceed budget — flush it and start a new one
            batches.append(current_batch)
            current_batch = [seg]
            current_tokens = seg_tokens
        else:
            current_batch.append(seg)
            current_tokens += seg_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
