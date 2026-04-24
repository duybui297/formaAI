"""
Tests for CSV/TBX import parsers in glossary_service.py.

TDD RED: written before implementation.
"""
from __future__ import annotations

import pytest

from app.services.glossary_service import parse_csv_glossary, parse_tbx_minimal, import_csv_terms
from app.services.glossary_service import create_glossary


@pytest.mark.asyncio
async def test_import_csv_terms_success(db_session):
    g = await create_glossary(db_session, name="CSV", source_lang="vi", target_lang="en")
    csv_content = b"source_term,target_term,notes\nnguon,source,optional\ndich,target,\n"
    result = await import_csv_terms(db_session, g, csv_content, ".csv")
    assert result["imported"] == 2
    assert result["skipped_duplicates"] == 0


@pytest.mark.asyncio
async def test_import_csv_terms_skips_duplicates(db_session):
    g = await create_glossary(db_session, name="DupCSV", source_lang="vi", target_lang="en")
    csv_content = b"source_term,target_term\nnguon,source\nnguon,other\n"
    result = await import_csv_terms(db_session, g, csv_content, ".csv")
    assert result["imported"] == 1
    assert result["skipped_duplicates"] == 1


# --- parse_csv_glossary unit tests ---

def test_parse_csv_standard_headers():
    content = b"source_term,target_term,notes\nhello,xin chao,greeting\n"
    rows = parse_csv_glossary(content)
    assert len(rows) == 1
    assert rows[0]["source_term"] == "hello"
    assert rows[0]["target_term"] == "xin chao"
    assert rows[0]["notes"] == "greeting"


def test_parse_csv_alias_headers():
    content = b"source,target\nhello,xin chao\n"
    rows = parse_csv_glossary(content)
    assert len(rows) == 1
    assert rows[0]["source_term"] == "hello"
    assert rows[0]["target_term"] == "xin chao"


def test_parse_csv_bom_stripped():
    # utf-8-sig BOM prefix (\xef\xbb\xbf)
    content = b"\xef\xbb\xbfsource_term,target_term\nhello,xin chao\n"
    rows = parse_csv_glossary(content)
    assert len(rows) == 1
    assert rows[0]["source_term"] == "hello"


def test_parse_csv_missing_headers_raises():
    content = b"col1,col2\nhello,world\n"
    with pytest.raises(ValueError, match="source_term"):
        parse_csv_glossary(content)


def test_parse_csv_short_term_raises():
    content = b"source_term,target_term\na,world\n"
    with pytest.raises(ValueError, match="2 characters"):
        parse_csv_glossary(content)


def test_parse_csv_notes_optional():
    content = b"source_term,target_term\nhello,world\n"
    rows = parse_csv_glossary(content)
    assert rows[0]["notes"] is None


# --- parse_tbx_minimal unit tests ---

TBX_CORE_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX-Core" xml:lang="en">
  <body>
    <termEntry id="c1">
      <langSet xml:lang="vi">
        <tig><term>nguon</term></tig>
      </langSet>
      <langSet xml:lang="en">
        <tig><term>source</term></tig>
      </langSet>
    </termEntry>
    <termEntry id="c2">
      <langSet xml:lang="vi">
        <tig><term>dich</term></tig>
      </langSet>
      <langSet xml:lang="en">
        <tig><term>target</term></tig>
      </langSet>
    </termEntry>
  </body>
</martif>""".encode("utf-8")


def test_parse_tbx_core_extracts_pairs():
    rows = parse_tbx_minimal(TBX_CORE_SAMPLE, source_lang="vi", target_lang="en")
    assert len(rows) == 2
    assert rows[0]["source_term"] == "nguon"
    assert rows[0]["target_term"] == "source"
    assert rows[0]["notes"] is None


def test_parse_tbx_wrong_lang_pair_returns_empty():
    rows = parse_tbx_minimal(TBX_CORE_SAMPLE, source_lang="ja", target_lang="zh")
    assert rows == []


def test_parse_tbx_invalid_xml_raises():
    with pytest.raises(ValueError, match="Malformed TBX"):
        parse_tbx_minimal(b"<not valid xml><<", source_lang="vi", target_lang="en")


TBX_BASIC_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<martif type="TBX-Basic" xml:lang="en">
  <body>
    <termEntry id="b1">
      <langSet xml:lang="vi">
        <ntig>
          <termGrp><term>ma nguon</term></termGrp>
        </ntig>
      </langSet>
      <langSet xml:lang="en">
        <ntig>
          <termGrp><term>source code</term></termGrp>
        </ntig>
      </langSet>
    </termEntry>
  </body>
</martif>""".encode("utf-8")


def test_parse_tbx_basic_extracts_pairs():
    rows = parse_tbx_minimal(TBX_BASIC_SAMPLE, source_lang="vi", target_lang="en")
    assert len(rows) == 1
    assert rows[0]["source_term"] == "ma nguon"
    assert rows[0]["target_term"] == "source code"
