"""
Tests for pipeline/segment.py and pipeline/placeholder.py.

TDD RED: Written before implementation. These tests define the expected behavior
of make_segment_id, extract_placeholders, and restore_placeholders.
"""
from __future__ import annotations

import pytest

from app.pipeline.segment import make_segment_id
from app.pipeline.placeholder import (
    PlaceholderRestoreError,
    extract_placeholders,
    restore_placeholders,
)


# ---------------------------------------------------------------------------
# make_segment_id tests (D-06)
# ---------------------------------------------------------------------------


def test_segment_id_deterministic():
    """D-06: same inputs always produce same 16-char hex ID."""
    result1 = make_segment_id("Hello world", "body.para.0")
    result2 = make_segment_id("Hello world", "body.para.0")
    assert result1 == result2


def test_segment_id_length():
    """D-06: result is exactly 16 hex characters."""
    result = make_segment_id("Some text", "body.para.5")
    assert len(result) == 16
    # must be valid hex
    int(result, 16)


def test_segment_id_differs_on_different_text():
    """D-06: different source text → different id (collision extremely unlikely)."""
    id1 = make_segment_id("Hello world", "body.para.0")
    id2 = make_segment_id("Goodbye world", "body.para.0")
    assert id1 != id2


def test_segment_id_differs_on_different_position():
    """D-06: same text at different structural positions → different id."""
    id1 = make_segment_id("Hello world", "body.para.0")
    id2 = make_segment_id("Hello world", "body.para.1")
    assert id1 != id2


# ---------------------------------------------------------------------------
# extract_placeholders tests (CORE-05)
# ---------------------------------------------------------------------------


def test_extract_url_produces_placeholder():
    """URLs must be replaced with ⟦T0⟧ markers."""
    text = "Visit https://aicore.vn for info"
    masked, tokens = extract_placeholders(text)
    assert "⟦T0⟧" in masked
    assert "https://aicore.vn" not in masked
    assert tokens[0] == "https://aicore.vn"


def test_extract_email_produces_placeholder():
    """Email addresses must be replaced with ⟦T{n}⟧ markers."""
    text = "contact@aicore.vn works"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "contact@aicore.vn" not in masked
    assert "contact@aicore.vn" in tokens.values()


def test_extract_template_var_double_braces():
    """{{user_name}} mustache vars must be replaced."""
    text = "Hello {{user_name}}"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "{{user_name}}" not in masked
    assert "{{user_name}}" in tokens.values()


def test_extract_template_var_dollar_brace():
    """${foo} JS template literals must be replaced."""
    text = "Value is ${foo} here"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "${foo}" not in masked
    assert "${foo}" in tokens.values()


def test_extract_template_var_ejs():
    """<%= bar %> EJS template tags must be replaced."""
    text = "Output: <%= bar %>"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "<%= bar %>" not in masked
    assert "<%= bar %>" in tokens.values()


def test_extract_version_string():
    """Version strings like v2.3.1 must be replaced."""
    text = "using v2.3.1 release"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "v2.3.1" not in masked
    assert "v2.3.1" in tokens.values()


def test_extract_iso_date():
    """ISO date strings like 2026-04-23 must be replaced."""
    text = "on 2026-04-23 we shipped"
    masked, tokens = extract_placeholders(text)
    assert "⟦T" in masked
    assert "2026-04-23" not in masked
    assert "2026-04-23" in tokens.values()


def test_extract_multiple_tokens_in_same_text():
    """URL + email in same text → two distinct markers ⟦T0⟧ and ⟦T1⟧ (or higher)."""
    text = "See https://aicore.vn and email me@aicore.vn"
    masked, tokens = extract_placeholders(text)
    assert len(tokens) >= 2
    # no original values remain in masked text
    assert "https://aicore.vn" not in masked
    assert "me@aicore.vn" not in masked
    # all ⟦T{n}⟧ markers present for each extracted token
    for idx in tokens:
        assert f"⟦T{idx}⟧" in masked


def test_extract_plain_text_unchanged():
    """Plain text with no protected patterns should be returned unchanged."""
    text = "This is just plain text with no special tokens."
    masked, tokens = extract_placeholders(text)
    assert masked == text
    assert tokens == {}


# ---------------------------------------------------------------------------
# restore_placeholders tests (CORE-05)
# ---------------------------------------------------------------------------


def test_restore_replaces_single_marker():
    """Basic round-trip: extract then restore returns original text."""
    original = "Visit https://aicore.vn for info"
    masked, tokens = extract_placeholders(original)
    restored = restore_placeholders(masked, tokens)
    assert restored == original


def test_restore_replaces_all_markers():
    """All ⟦T{n}⟧ markers in multi-token text must be restored."""
    original = "See https://aicore.vn and email me@aicore.vn"
    masked, tokens = extract_placeholders(original)
    restored = restore_placeholders(masked, tokens)
    assert "https://aicore.vn" in restored
    assert "me@aicore.vn" in restored


def test_no_leftover_markers_after_restore():
    """After restore_placeholders, no ⟦T{n}⟧ markers may remain in the output."""
    original = "Visit https://aicore.vn and contact admin@aicore.vn, version v1.0.0"
    masked, tokens = extract_placeholders(original)
    restored = restore_placeholders(masked, tokens)
    assert "⟦T" not in restored


def test_restore_missing_key_keeps_marker():
    """If a token index is missing from the map, the marker stays (visible error)."""
    text = "Check ⟦T0⟧ and ⟦T5⟧"
    tokens = {0: "https://aicore.vn"}  # 5 is missing
    restored = restore_placeholders(text, tokens)
    assert "https://aicore.vn" in restored
    assert "⟦T5⟧" in restored  # missing key keeps the marker


def test_restore_empty_tokens_dict():
    """If tokens is empty, text is returned unchanged."""
    text = "No markers here"
    restored = restore_placeholders(text, {})
    assert restored == text
