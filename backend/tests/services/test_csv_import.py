"""CSV glossary import tests — GLOS-02.

Stubs: will pass after Plan 03 implements parse_csv_glossary in glossary_service.py.
"""
from __future__ import annotations

import pytest


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_standard_headers():
    """CSV with source_term,target_term headers parses correctly."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source_term,target_term,notes\nAICore,AICore,brand name\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1
    assert terms[0]["source_term"] == "AICore"
    assert terms[0]["target_term"] == "AICore"
    assert terms[0]["notes"] == "brand name"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_with_bom():
    """CSV with UTF-8 BOM (Excel export) strips BOM and parses correctly — Pitfall 6."""
    from app.services.glossary_service import parse_csv_glossary
    bom = b"\xef\xbb\xbf"
    content = bom + b"source_term,target_term\nxin ch\xc3\xa0o,hello\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1
    assert terms[0]["source_term"] == "xin chào"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_header_variants():
    """CSV with 'source','target' header aliases are accepted."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source,target\nterm,translation\n"
    terms = parse_csv_glossary(content)
    assert len(terms) == 1


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_short_term_rejected():
    """Terms shorter than 2 chars are rejected per D-02-07."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"source_term,target_term\nA,B\n"
    with pytest.raises(ValueError, match="at least 2 characters"):
        parse_csv_glossary(content)


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service CSV parser", strict=False)
def test_parse_csv_missing_headers_raises():
    """CSV without required headers raises ValueError."""
    from app.services.glossary_service import parse_csv_glossary
    content = b"col1,col2\nfoo,bar\n"
    with pytest.raises(ValueError):
        parse_csv_glossary(content)
