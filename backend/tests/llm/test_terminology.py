"""
Unit tests for glossary_to_terms() in app.llm.terminology.
"""
from __future__ import annotations

import pytest


def test_glossary_to_terms_converts_dict():
    """Simple two-entry dict → list of {source, target} dicts."""
    from app.llm.terminology import glossary_to_terms

    result = glossary_to_terms({"a": "b", "c": "d"})
    assert isinstance(result, list)
    assert len(result) == 2
    sources = {t["source"] for t in result}
    targets = {t["target"] for t in result}
    assert sources == {"a", "c"}
    assert targets == {"b", "d"}


def test_glossary_to_terms_empty_dict_returns_empty():
    """{} → []"""
    from app.llm.terminology import glossary_to_terms

    result = glossary_to_terms({})
    assert result == []


def test_glossary_to_terms_single_entry():
    """Single pair → list of one item."""
    from app.llm.terminology import glossary_to_terms

    result = glossary_to_terms({"term": "термин"})
    assert result == [{"source": "term", "target": "термин"}]


def test_glossary_to_terms_preserves_unicode():
    """Unicode keys and values are preserved without modification."""
    from app.llm.terminology import glossary_to_terms

    glossary = {"Hợp đồng": "Contract", "người dùng": "User"}
    result = glossary_to_terms(glossary)
    source_set = {t["source"] for t in result}
    assert "Hợp đồng" in source_set
    assert "người dùng" in source_set


def test_glossary_to_terms_each_item_has_source_and_target():
    """Every item in the result must have exactly 'source' and 'target' keys."""
    from app.llm.terminology import glossary_to_terms

    result = glossary_to_terms({"x": "y", "p": "q", "m": "n"})
    for item in result:
        assert set(item.keys()) == {"source", "target"}
