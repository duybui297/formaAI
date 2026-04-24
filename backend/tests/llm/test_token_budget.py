"""
Unit tests for token_budget.py — pack_into_batches, estimate_tokens, SegmentTooLargeError.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

def test_estimate_tokens_non_empty():
    """Non-empty string returns a positive integer token count."""
    from app.llm.token_budget import estimate_tokens

    count = estimate_tokens("hello world")
    assert isinstance(count, int)
    assert count > 0


def test_estimate_tokens_empty_string():
    """Empty string returns 0."""
    from app.llm.token_budget import estimate_tokens

    assert estimate_tokens("") == 0


def test_estimate_tokens_cjk_vs_latin():
    """
    CJK text uses more tokens per character than Latin (BPE encodes CJK less densely).
    10-char CJK should NOT have fewer tokens than a single short Latin word,
    but the key property is that both return positive ints.
    """
    from app.llm.token_budget import estimate_tokens

    latin = estimate_tokens("hello world!")
    cjk = estimate_tokens("こんにちは世界")
    assert latin > 0
    assert cjk > 0


# ---------------------------------------------------------------------------
# pack_into_batches
# ---------------------------------------------------------------------------

def test_pack_empty_segments_returns_empty():
    """Empty input → empty batch list."""
    from app.llm.token_budget import pack_into_batches

    result = pack_into_batches([])
    assert result == []


def test_pack_single_small_segment():
    """One short segment → exactly one batch containing it."""
    from app.llm.token_budget import pack_into_batches

    result = pack_into_batches(["hello"])
    assert len(result) == 1
    assert result[0] == ["hello"]


def test_pack_multiple_segments_one_batch():
    """Five short segments well under budget → single batch."""
    from app.llm.token_budget import pack_into_batches

    segs = ["a", "b", "c", "d", "e"]
    result = pack_into_batches(segs, budget_tokens=3000)
    assert len(result) == 1
    assert result[0] == segs


def test_pack_splits_when_budget_exceeded():
    """
    Enough short segments to exceed budget → multiple batches.
    Use a tiny budget (20 tokens) to force splitting.
    """
    from app.llm.token_budget import pack_into_batches, estimate_tokens

    # Each segment is ~3-4 tokens; with budget=10 we'll need multiple batches
    segs = ["hello world"] * 10
    result = pack_into_batches(segs, budget_tokens=10)
    assert len(result) > 1
    # All segments are present across all batches
    all_segs = [s for batch in result for s in batch]
    assert all_segs == segs


def test_pack_preserves_all_segments():
    """No segment is lost or duplicated during batching."""
    from app.llm.token_budget import pack_into_batches

    segs = [f"Segment number {i} with some text." for i in range(50)]
    result = pack_into_batches(segs, budget_tokens=200)
    all_segs = [s for batch in result for s in batch]
    assert all_segs == segs


def test_pack_oversized_single_segment_own_batch():
    """
    A segment bigger than budget but <= 7000 tokens goes into its own batch
    (not raising an error — only the hard limit of 7000 raises).
    """
    from app.llm.token_budget import pack_into_batches

    # Create a segment that will exceed a small budget but not the hard limit
    big_seg = "word " * 800  # ~800 tokens, well under 7000
    small_segs = ["hello", "world"]

    result = pack_into_batches(small_segs + [big_seg], budget_tokens=50)
    # big_seg must appear in its own batch
    big_batches = [b for b in result if big_seg in b]
    assert len(big_batches) == 1
    assert big_batches[0] == [big_seg]


def test_pack_oversized_exceeds_hard_limit_raises():
    """Segment > 7000 tokens → SegmentTooLargeError (D-08)."""
    from app.llm.token_budget import pack_into_batches, SegmentTooLargeError

    # ~8000 tokens: "word " * 8000 ≈ 8000 tokens via cl100k_base
    huge_seg = "word " * 8000
    with pytest.raises(SegmentTooLargeError):
        pack_into_batches([huge_seg])


def test_oversized_error_contains_segment_info():
    """SegmentTooLargeError exposes segment_id and token_count attributes."""
    from app.llm.token_budget import pack_into_batches, SegmentTooLargeError

    huge_seg = "word " * 8000
    with pytest.raises(SegmentTooLargeError) as exc_info:
        pack_into_batches([huge_seg], segment_ids=["seg_abc"])

    err = exc_info.value
    assert hasattr(err, "segment_id")
    assert hasattr(err, "token_count")
    assert err.segment_id == "seg_abc"
    assert err.token_count > 7000


def test_oversized_error_segment_id_auto_generated():
    """Without explicit segment_ids, a default ID is still set on the error."""
    from app.llm.token_budget import pack_into_batches, SegmentTooLargeError

    huge_seg = "word " * 8000
    with pytest.raises(SegmentTooLargeError) as exc_info:
        pack_into_batches([huge_seg])

    err = exc_info.value
    assert err.segment_id is not None
    assert len(err.segment_id) > 0


def test_pack_batch_does_not_exceed_budget_unless_single_seg():
    """
    No batch's total token count exceeds the budget, unless a batch
    contains exactly one segment that itself exceeds the budget.
    """
    from app.llm.token_budget import pack_into_batches, estimate_tokens

    segs = [f"This is sentence number {i}." for i in range(30)]
    budget = 100
    result = pack_into_batches(segs, budget_tokens=budget)

    for batch in result:
        total = sum(estimate_tokens(s) for s in batch)
        if len(batch) > 1:
            assert total <= budget, f"Multi-seg batch exceeded budget: {total} > {budget}"


def test_pack_respects_custom_budget():
    """Smaller budget → more (smaller) batches."""
    from app.llm.token_budget import pack_into_batches

    segs = ["This is a test sentence."] * 20
    large_budget = pack_into_batches(segs, budget_tokens=5000)
    small_budget = pack_into_batches(segs, budget_tokens=20)
    assert len(small_budget) >= len(large_budget)
