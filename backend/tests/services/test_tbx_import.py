"""
Additional TBX edge case tests.

TDD RED: written before implementation.
"""
from __future__ import annotations

import pytest

from app.services.glossary_service import parse_tbx_minimal


def test_parse_tbx_filters_short_terms():
    """Terms shorter than 2 chars should be excluded (D-02-07)."""
    content = b"""<?xml version="1.0"?>
<martif>
  <body>
    <termEntry>
      <langSet xml:lang="vi">
        <tig><term>a</term></tig>
      </langSet>
      <langSet xml:lang="en">
        <tig><term>b</term></tig>
      </langSet>
    </termEntry>
  </body>
</martif>"""
    rows = parse_tbx_minimal(content, source_lang="vi", target_lang="en")
    assert rows == []


def test_parse_tbx_empty_body():
    content = b"""<?xml version="1.0"?><martif><body></body></martif>"""
    rows = parse_tbx_minimal(content, source_lang="vi", target_lang="en")
    assert rows == []


def test_parse_tbx_case_insensitive_lang_match():
    """xml:lang="VI" should match source_lang="vi" (case-insensitive)."""
    content = """<?xml version="1.0"?>
<martif>
  <body>
    <termEntry>
      <langSet xml:lang="VI">
        <tig><term>nguon</term></tig>
      </langSet>
      <langSet xml:lang="EN">
        <tig><term>source</term></tig>
      </langSet>
    </termEntry>
  </body>
</martif>""".encode("utf-8")
    rows = parse_tbx_minimal(content, source_lang="vi", target_lang="en")
    assert len(rows) == 1
    assert rows[0]["source_term"] == "nguon"
