"""
Unit tests for app.llm.schemas — TranslateBatchRequest, TranslateBatchResponse,
TokenUsage, and assert_segment_count (CORE-03).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schemas import (
    TokenUsage,
    TranslateBatchRequest,
    TranslateBatchResponse,
    assert_segment_count,
)


# ---------------------------------------------------------------------------
# TokenUsage
# ---------------------------------------------------------------------------

def test_token_usage_fields():
    usage = TokenUsage(prompt_tokens=10, completion_tokens=8, total_tokens=18)
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 8
    assert usage.total_tokens == 18


def test_token_usage_frozen():
    usage = TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3)
    with pytest.raises((ValidationError, TypeError)):
        usage.prompt_tokens = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TranslateBatchRequest
# ---------------------------------------------------------------------------

def test_translate_batch_request_defaults():
    req = TranslateBatchRequest(
        segments=["Hello"],
        source_lang="en",
        target_lang="vi",
    )
    assert req.model == "qwen-mt-turbo"
    assert req.glossary is None


def test_translate_batch_request_requires_segments():
    with pytest.raises(ValidationError):
        TranslateBatchRequest(segments=[], source_lang="en", target_lang="vi")


def test_translate_batch_request_with_glossary():
    req = TranslateBatchRequest(
        segments=["AICore"],
        source_lang="en",
        target_lang="vi",
        glossary={"AICore": "AICore"},
    )
    assert req.glossary == {"AICore": "AICore"}


# ---------------------------------------------------------------------------
# TranslateBatchResponse
# ---------------------------------------------------------------------------

def test_translate_batch_response_valid():
    usage = TokenUsage(prompt_tokens=5, completion_tokens=6, total_tokens=11)
    resp = TranslateBatchResponse(segments=["Xin chào"], usage=usage)
    assert resp.segments == ["Xin chào"]


def test_translate_batch_response_empty_segments_raises():
    usage = TokenUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2)
    with pytest.raises(ValidationError, match="non-empty"):
        TranslateBatchResponse(segments=[], usage=usage)


# ---------------------------------------------------------------------------
# assert_segment_count (CORE-03)
# ---------------------------------------------------------------------------

def test_assert_segment_count_match_passes():
    usage = TokenUsage(prompt_tokens=2, completion_tokens=2, total_tokens=4)
    req = TranslateBatchRequest(segments=["a", "b"], source_lang="en", target_lang="vi")
    resp = TranslateBatchResponse(segments=["x", "y"], usage=usage)
    assert_segment_count(req, resp)  # should not raise


def test_assert_segment_count_mismatch_raises():
    usage = TokenUsage(prompt_tokens=2, completion_tokens=1, total_tokens=3)
    req = TranslateBatchRequest(segments=["a", "b"], source_lang="en", target_lang="vi")
    resp = TranslateBatchResponse(segments=["x"], usage=usage)
    with pytest.raises(ValueError, match="CORE-03"):
        assert_segment_count(req, resp)


def test_assert_segment_count_mismatch_message_contains_counts():
    usage = TokenUsage(prompt_tokens=3, completion_tokens=2, total_tokens=5)
    req = TranslateBatchRequest(segments=["a", "b", "c"], source_lang="en", target_lang="vi")
    resp = TranslateBatchResponse(segments=["x", "y"], usage=usage)
    with pytest.raises(ValueError) as exc_info:
        assert_segment_count(req, resp)
    msg = str(exc_info.value)
    assert "expected=3" in msg
    assert "got=2" in msg
