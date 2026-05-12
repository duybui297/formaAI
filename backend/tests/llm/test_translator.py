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
    # Call-count semantics covered by dedicated batching tests below — this test
    # only asserts length invariant.


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


# ---------------------------------------------------------------------------
# CORE-05: placeholder masking (URLs / emails / template vars / dates / versions)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_core05_masks_url_before_model_call():
    """URLs must be masked with ⟦T{n}⟧ markers before reaching the model."""
    from app.llm.translator import translate_batch

    captured: list[str] = []

    async def capture(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        # Model echoes markers unchanged
        response.choices[0].message.content = captured[-1].replace(
            "Visit", "Truy cập"
        )
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(
        client,
        ["Visit https://example.com/path?q=1 today"],
        "en",
        "vi",
    )

    # Model never saw the raw URL
    assert "https://example.com" not in captured[0]
    assert "⟦T0⟧" in captured[0]
    # Output has the URL restored verbatim
    assert "https://example.com/path?q=1" in result[0]


@pytest.mark.asyncio
async def test_translate_batch_core05_masks_email_and_template_var():
    """Emails and {{template_vars}} are masked and restored."""
    from app.llm.translator import translate_batch

    captured: list[str] = []

    async def capture(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = captured[-1]  # echo
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(
        client,
        ["Contact support@example.com or {{user_name}}"],
        "en",
        "vi",
    )

    # Neither email nor template var reached the model
    assert "support@example.com" not in captured[0]
    assert "{{user_name}}" not in captured[0]
    # Both are restored in the output
    assert "support@example.com" in result[0]
    assert "{{user_name}}" in result[0]


@pytest.mark.asyncio
async def test_translate_batch_core05_masks_iso_date_and_version():
    """ISO dates and version strings (v2.3.1) are masked and restored."""
    from app.llm.translator import translate_batch

    captured: list[str] = []

    async def capture(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = captured[-1]
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(
        client,
        ["Released v2.3.1 on 2026-04-24"],
        "en",
        "vi",
    )

    assert "v2.3.1" not in captured[0]
    assert "2026-04-24" not in captured[0]
    assert "v2.3.1" in result[0]
    assert "2026-04-24" in result[0]


@pytest.mark.asyncio
async def test_translate_batch_core05_segment_without_placeholders_unchanged():
    """Segments with no protected tokens pass through masking as no-ops."""
    from app.llm.translator import translate_batch

    captured: list[str] = []

    async def capture(**kwargs):
        captured.append(kwargs["messages"][0]["content"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Xin chào"
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    result = await translate_batch(client, ["Hello world"], "en", "vi")

    # No markers introduced; content sent verbatim (after NFC)
    assert "⟦T" not in captured[0]
    assert captured[0] == "Hello world"
    assert result == ["Xin chào"]


# ---------------------------------------------------------------------------
# Dedup — collapse identical non-passthrough segments to a single API call
# Cuts cost + latency on table-heavy PDFs where headers/labels repeat (e.g.
# job 7f958166 had 672-cell tables with many repeated short cells).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_dedupes_identical_segments():
    """Identical inputs trigger one API call per unique value, result broadcast back."""
    from app.llm.translator import translate_batch

    call_contents: list[str] = []

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        call_contents.append(content)
        response = MagicMock()
        response.choices = [MagicMock()]
        # Mirror back upper-cased to prove broadcast wiring
        response.choices[0].message.content = content.upper()
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    # 4 segments, 2 unique non-passthrough values → sentinel-batched into 1 call
    result = await translate_batch(client, ["foo", "bar", "foo", "foo"], "en", "fr")

    assert result == ["FOO", "BAR", "FOO", "FOO"]
    # Batching may pack both uniques into one call (joined by '|||') OR fall
    # back to per-segment on small batches; either is correct as long as the
    # unique set was sent exactly once each.
    joined = "|||".join(call_contents)
    assert "foo" in joined and "bar" in joined
    assert client.chat.completions.create.await_count <= 2


@pytest.mark.asyncio
async def test_translate_batch_dedup_with_passthrough_mix():
    """Dedup + CORE-05 passthrough cooperate: passthroughs untouched, uniques deduped."""
    from app.llm.translator import translate_batch

    call_contents: list[str] = []

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        call_contents.append(content)
        response = MagicMock()
        response.choices = [MagicMock()]
        # Wrap each cell (preserves sentinel-joined batches)
        parts = content.split("|||")
        response.choices[0].message.content = "|||".join(f"<{p}>" for p in parts)
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    # Mix: 2 passthroughs (whitespace, digit), 3 unique real values, with repeats
    segments = ["  ", "N/A", "42", "N/A", "Total", "N/A", "Total"]
    result = await translate_batch(client, segments, "en", "vi")

    assert result == ["  ", "<N/A>", "42", "<N/A>", "<Total>", "<N/A>", "<Total>"]
    # Only "N/A" + "Total" reach the model — passthroughs skipped, repeats deduped.
    # Batching may pack both into 1 sentinel-joined call OR send them separately;
    # either is correct as long as both uniques reached the model exactly once.
    joined = "|||".join(call_contents)
    assert "N/A" in joined and "Total" in joined
    assert client.chat.completions.create.await_count <= 2


# ---------------------------------------------------------------------------
# Sentinel-batched packing — many short uniques compressed into few API calls.
# Validated by spike 001 ('|||' survives qwen-mt-* round-trip on en/vi/ja/zh)
# and spike 002 (escape with ⟦C{n}⟧, 20-cell stress, glossary cooperation).
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_translate_batch_packs_many_uniques_into_few_calls():
    """30 short uniques should pack into ~2 batch calls instead of 30 per-segment calls."""
    from app.llm.translator import translate_batch

    call_inputs: list[str] = []

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        call_inputs.append(content)
        # Simulate model: upper-case every cell, preserving the '|||' delimiters
        parts = content.split("|||")
        translated = "|||".join(p.upper() for p in parts)
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = translated
        response.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    cells = [f"Item{i}" for i in range(30)]
    result = await translate_batch(client, cells, "en", "vi")

    assert result == [c.upper() for c in cells]
    # 30 cells / batch size 20 → 2 batch calls. Old impl: 30 calls.
    # Allow a small margin in case the impl picks slightly different batch size.
    assert client.chat.completions.create.await_count <= 5, (
        f"Expected few batched calls, got {client.chat.completions.create.await_count}"
    )


@pytest.mark.asyncio
async def test_translate_batch_count_mismatch_falls_back_to_per_segment():
    """If model response sentinel count != input, fall back to per-segment for that batch."""
    from app.llm.translator import translate_batch

    call_inputs: list[str] = []

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        call_inputs.append(content)
        response = MagicMock()
        response.choices = [MagicMock()]
        # First call is the sentinel-joined batch — return garbage with NO sentinels
        if "|||" in content:
            response.choices[0].message.content = "broken response"
        else:
            # Per-segment fallback — return uppercase per cell
            response.choices[0].message.content = content.upper()
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    cells = ["foo", "bar", "baz"]
    result = await translate_batch(client, cells, "en", "vi")

    # Per-segment fallback recovers the right answer
    assert result == ["FOO", "BAR", "BAZ"]
    # 1 failed batch + 3 fallback = 4 calls
    assert client.chat.completions.create.await_count == 4
    # First call must have been the sentinel-joined batch
    assert "|||" in call_inputs[0]


@pytest.mark.asyncio
async def test_translate_batch_escapes_literal_sentinel_in_cell_content():
    """Cell containing literal '|||' is escaped before join; split + restore yields original."""
    from app.llm.translator import translate_batch

    received: list[str] = []

    async def capture(**kwargs):
        content = kwargs["messages"][0]["content"]
        received.append(content)
        response = MagicMock()
        response.choices = [MagicMock()]
        # Pass-through (no actual translation) so restore yields source verbatim
        response.choices[0].message.content = content
        response.usage = MagicMock(prompt_tokens=10, completion_tokens=10, total_tokens=20)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    # Middle cell contains a literal '|||' that must NOT split the batch
    cells = ["Year", "Range |||x|||", "Total"]
    result = await translate_batch(client, cells, "en", "vi")

    # Output round-trip restores the original '|||' inside cell 1
    assert result == ["Year", "Range |||x|||", "Total"]
    # The single API call's input contains exactly 2 sentinels (between cells),
    # the in-cell '|||' must be escaped to a different marker.
    sent = received[0]
    assert sent.count("|||") == 2, (
        f"Expected 2 sentinels in batched input, got {sent.count('|||')}. "
        f"Sent: {sent!r}"
    )


@pytest.mark.asyncio
async def test_translate_batch_glossary_propagates_to_batched_call():
    """Glossary `terminology` API param applies even when uniques are sentinel-batched."""
    from app.llm.translator import translate_batch

    seen_opts: list[dict] = []

    async def capture(**kwargs):
        seen_opts.append(kwargs["extra_body"]["translation_options"])
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = kwargs["messages"][0]["content"]
        response.usage = MagicMock(prompt_tokens=5, completion_tokens=5, total_tokens=10)
        return response

    client = AsyncMock()
    client.chat.completions.create = AsyncMock(side_effect=capture)

    await translate_batch(
        client, ["Apple", "Orange", "Mango"], "en", "vi",
        glossary={"Apple": "Táo Đỏ"},
    )

    assert seen_opts, "no API call was made"
    opts = seen_opts[0]
    assert "terms" in opts
    assert any(t.get("source") == "Apple" and t.get("target") == "Táo Đỏ" for t in opts["terms"])
