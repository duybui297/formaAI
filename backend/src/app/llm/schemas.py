"""
Pydantic schemas for the LLM translation batch API.

All models are frozen (immutable) per CLAUDE.md coding style.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class TokenUsage(BaseModel, frozen=True):
    """Token consumption from a single LLM API call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TranslateBatchRequest(BaseModel, frozen=True):
    """Input contract for a single translate_batch call."""

    segments: list[str] = Field(..., min_length=1)
    source_lang: str
    target_lang: str
    glossary: dict[str, str] | None = None
    model: str = "qwen-mt-turbo"


class TranslateBatchResponse(BaseModel, frozen=True):
    """Output contract from a single translate_batch call."""

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
    """
    CORE-03: raise ValueError with full context when count mismatches.

    Called after every translate_batch invocation. The explicit error message
    includes model, source/target languages, and expected vs. got counts so
    the worker can log actionable diagnostics.
    """
    if len(response.segments) != len(request.segments):
        raise ValueError(
            f"CORE-03 segment count mismatch: "
            f"expected={len(request.segments)}, got={len(response.segments)}, "
            f"model={request.model}, src={request.source_lang}, tgt={request.target_lang}"
        )
