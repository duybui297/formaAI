"""
Unit tests for translate_batch — covers CORE-03/04/05 invariants.
All tests use a mock AsyncOpenAI client; no network calls are made.
"""
from __future__ import annotations

import unicodedata
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — build a minimal mock LLM client with a custom response
# ---------------------------------------------------------------------------

def _make_client(content: str | None) -> AsyncMock:
    """Return a mock AsyncOpenAI whose completions.create returns ``content``."""
    client = AsyncMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock(prompt_tokens=10, completion_tokens=8, total_tokens=18)
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_returns_same_count():
    """Happy path: 2 segments in → 2 translations out (one API call per segment)."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour monde")
    result = await translate_batch(client, ["Hello world", "This is a test"], "en", "fr")
    assert len(result) == 2
    # Per-segment architecture: one call per input segment
    assert client.chat.completions.create.await_count == 2


@pytest.mark.asyncio
async def test_translate_batch_returns_list_of_strings():
    """Result must be a list of str values."""
    from app.llm.translator import translate_batch

    client = _make_client("Hallo")
    result = await translate_batch(client, ["Hello", "World"], "en", "de")
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


# ---------------------------------------------------------------------------
# CORE-03: segment count invariant
#
# New per-segment architecture guarantees len(output) == len(input) by
# construction (one coroutine per input segment, collected via asyncio.gather).
# The prior newline-based impl could drift when the model added/merged lines
# in a single batched response; those tests are obsolete.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_length_invariant_real_world():
    """CORE-03: real-world mixed batch returns exactly one output per input."""
    from app.llm.translator import translate_batch

    inputs = ["Hello", "World", "Third", "Fourth", "Fifth"]
    # Model returns multi-line content; new impl ignores embedded newlines
    client = _make_client("Translated\nline\nbreak")
    result = await translate_batch(client, inputs, "en", "fr")
    assert len(result) == len(inputs)


@pytest.mark.asyncio
async def test_translate_batch_none_content_returns_empty_string():
    """None content from the model surfaces as an empty string in the output, not a crash."""
    from app.llm.translator import translate_batch

    client = _make_client(None)
    result = await translate_batch(client, ["Hello"], "en", "fr")
    assert result == [""]


# ---------------------------------------------------------------------------
# CORE-04: NFC normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_core04_nfc_normalizes_output():
    """CORE-04: output strings must be NFC-normalized."""
    from app.llm.translator import translate_batch

    # "đ" in NFD: d + combining-hook-above (U+0111 can be represented differently)
    # Simulate model returning NFD-form Vietnamese text
    nfd_viet = unicodedata.normalize("NFD", "Xin chào")
    client = _make_client(nfd_viet)

    result = await translate_batch(client, ["Hello"], "en", "vi")
    assert result[0] == unicodedata.normalize("NFC", nfd_viet)


@pytest.mark.asyncio
async def test_translate_batch_core04_nfc_normalizes_input():
    """CORE-04: input segments are NFC-normalized before sending to model."""
    from app.llm.translator import translate_batch

    # Build NFD input — must be sent as NFC to the model
    nfd_input = unicodedata.normalize("NFD", "café")
    captured_content: list[str] = []

    async def capture_create(**kwargs):
        msg = kwargs["messages"][0]["content"]
        captured_content.append(msg)
        # Return one translated line matching the one payload segment
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Translated"
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=3, total_tokens=8)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture_create)

    await translate_batch(client, [nfd_input], "fr", "en")
    sent = captured_content[0]
    assert sent == unicodedata.normalize("NFC", nfd_input)


# ---------------------------------------------------------------------------
# CORE-05: passthrough stubs for whitespace-only / digit-only segments
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_core05_whitespace_passthrough():
    """CORE-05: whitespace-only segment is returned as-is; model never called for it."""
    from app.llm.translator import translate_batch

    client = AsyncMock()
    client.chat.completions.create = AsyncMock()

    result = await translate_batch(client, ["   "], "en", "fr")
    assert result == ["   "]
    # Passthrough segments must NOT trigger a model call (cost + correctness)
    client.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_translate_batch_core05_digit_passthrough():
    """CORE-05: digit-only segment is returned as-is; model never called."""
    from app.llm.translator import translate_batch

    client = AsyncMock()
    client.chat.completions.create = AsyncMock()

    result = await translate_batch(client, ["42"], "en", "fr")
    assert result == ["42"]
    client.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_translate_batch_core05_mixed_passthrough_and_real():
    """CORE-05: mix of passthrough and real — one API call for the real segment only."""
    from app.llm.translator import translate_batch

    call_contents: list[str] = []

    async def capture(**kwargs):
        call_contents.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Bonjour"
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(client, ["  ", "Hello"], "en", "fr")
    assert result[0] == "  "       # passthrough unchanged
    assert result[1] == "Bonjour"
    # Only the "Hello" segment should have reached the model
    assert call_contents == ["Hello"]


# ---------------------------------------------------------------------------
# API call discipline — no system message, no temperature
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_no_system_message():
    """AI-SPEC: no system message must be sent to qwen-mt-turbo."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour")
    await translate_batch(client, ["Hello"], "en", "fr")

    call_kwargs = client.chat.completions.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    # messages may be positional; retrieve safely
    if call_kwargs.kwargs.get("messages") is not None:
        messages = call_kwargs.kwargs["messages"]
    else:
        # try positional
        messages = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["messages"]

    roles = [m["role"] for m in messages]
    assert "system" not in roles


@pytest.mark.asyncio
async def test_translate_batch_no_temperature():
    """AI-SPEC: temperature= must never be passed to qwen-mt-turbo."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour")
    await translate_batch(client, ["Hello"], "en", "fr")

    call_kwargs = client.chat.completions.create.call_args
    assert "temperature" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# Glossary (extra_body)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_with_glossary():
    """Glossary must be passed as translation_options.terms in extra_body."""
    from app.llm.translator import translate_batch

    client = _make_client("термин")
    await translate_batch(
        client,
        ["term"],
        "en",
        "ru",
        glossary={"term": "термин"},
    )

    call_kwargs = client.chat.completions.create.call_args
    extra_body = call_kwargs.kwargs.get("extra_body", {})
    assert "translation_options" in extra_body
    opts = extra_body["translation_options"]
    assert "terms" in opts
    terms = opts["terms"]
    assert isinstance(terms, list)
    assert any(t["source"] == "term" and t["target"] == "термин" for t in terms)


@pytest.mark.asyncio
async def test_translate_batch_without_glossary_has_no_terms():
    """Without glossary, translation_options must not include 'terms' key."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour")
    await translate_batch(client, ["Hello"], "en", "fr")

    call_kwargs = client.chat.completions.create.call_args
    extra_body = call_kwargs.kwargs.get("extra_body", {})
    opts = extra_body.get("translation_options", {})
    assert "terms" not in opts


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_empty_segments_raises():
    """Empty segments list must raise ValueError immediately (no LLM call)."""
    from app.llm.translator import translate_batch

    client = AsyncMock()
    with pytest.raises(ValueError):
        await translate_batch(client, [], "en", "fr")

    client.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_translate_batch_max_tokens_set():
    """max_tokens=4096 must be passed on every call (AI-SPEC §4b.3)."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour")
    await translate_batch(client, ["Hello"], "en", "fr")

    call_kwargs = client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("max_tokens") == 4096
