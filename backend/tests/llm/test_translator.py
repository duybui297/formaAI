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
    """Happy path: 2 segments in → 2 translations out."""
    from app.llm.translator import translate_batch

    client = _make_client("Bonjour monde\nCeci est un test")
    result = await translate_batch(client, ["Hello world", "This is a test"], "en", "fr")
    assert len(result) == 2


@pytest.mark.asyncio
async def test_translate_batch_returns_list_of_strings():
    """Result must be a list of str values."""
    from app.llm.translator import translate_batch

    client = _make_client("Hallo\nWelt")
    result = await translate_batch(client, ["Hello", "World"], "en", "de")
    assert isinstance(result, list)
    assert all(isinstance(s, str) for s in result)


# ---------------------------------------------------------------------------
# CORE-03: segment count assertion
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_core03_raises_on_mismatch():
    """CORE-03: model returns 1 line for 2 segments → ValueError."""
    from app.llm.translator import translate_batch

    client = _make_client("Only one line")
    with pytest.raises(ValueError, match="CORE-03 violation"):
        await translate_batch(client, ["Hello", "World"], "en", "fr")


@pytest.mark.asyncio
async def test_translate_batch_none_content_triggers_core03():
    """CORE-03: content=None means 0 lines for N segments → ValueError."""
    from app.llm.translator import translate_batch

    client = _make_client(None)
    with pytest.raises(ValueError, match="CORE-03 violation"):
        await translate_batch(client, ["Hello"], "en", "fr")


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
    """CORE-05: whitespace-only segment is returned as-is; model sees placeholder."""
    from app.llm.translator import translate_batch

    call_args: list = []

    async def capture(**kwargs):
        call_args.append(kwargs["messages"][0]["content"])
        # model receives the placeholder ⟦T0⟧ and returns it unchanged
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "⟦T0⟧"
        response.usage = MagicMock(prompt_tokens=2, completion_tokens=2, total_tokens=4)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(client, ["   "], "en", "fr")
    assert result == ["   "]
    # Model should receive a placeholder, not the raw whitespace
    assert "⟦T" in call_args[0]


@pytest.mark.asyncio
async def test_translate_batch_core05_digit_passthrough():
    """CORE-05: digit-only segment is returned as-is."""
    from app.llm.translator import translate_batch

    call_args: list = []

    async def capture(**kwargs):
        call_args.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "⟦T0⟧"
        response.usage = MagicMock(prompt_tokens=2, completion_tokens=2, total_tokens=4)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(client, ["42"], "en", "fr")
    assert result == ["42"]
    assert "⟦T" in call_args[0]


@pytest.mark.asyncio
async def test_translate_batch_core05_mixed_passthrough_and_real():
    """CORE-05: mix of passthrough and real segments are handled correctly."""
    from app.llm.translator import translate_batch

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        # Content is "⟦T0⟧\nHello" — model returns placeholder + translation
        lines = content.split("\n")
        assert len(lines) == 2
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "⟦T0⟧\nBonjour"
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(client, ["  ", "Hello"], "en", "fr")
    assert result[0] == "  "   # passthrough unchanged
    assert result[1] == "Bonjour"


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
