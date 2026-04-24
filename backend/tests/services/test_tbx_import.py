"""TBX minimal import tests — GLOS-02."""
from __future__ import annotations

import pytest

_SAMPLE_TBX = b"""<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX-Basic">
  <body>
    <termEntry>
      <langSet xml:lang="vi"><tig><term>xin ch\xc3\xa0o</term></tig></langSet>
      <langSet xml:lang="en"><tig><term>hello</term></tig></langSet>
    </termEntry>
  </body>
</martif>
"""


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service TBX parser", strict=False)
def test_parse_tbx_minimal_valid():
    """Valid TBX-Core file extracts term pairs correctly."""
    from app.services.glossary_service import parse_tbx_minimal
    terms = parse_tbx_minimal(_SAMPLE_TBX, source_lang="vi", target_lang="en")
    assert len(terms) == 1
    assert terms[0]["source_term"] == "xin chào"
    assert terms[0]["target_term"] == "hello"


@pytest.mark.xfail(reason="Requires Plan 03 glossary_service TBX parser", strict=False)
def test_parse_tbx_no_matching_lang_returns_empty():
    """TBX with no entries for the specified pair returns empty list (not error)."""
    from app.services.glossary_service import parse_tbx_minimal
    terms = parse_tbx_minimal(_SAMPLE_TBX, source_lang="zh", target_lang="en")
    assert terms == []
