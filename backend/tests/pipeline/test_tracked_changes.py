"""
Tests for pipeline/docx/tracked.py.

TDD RED: Written before implementation. Tests define expected behavior of
has_tracked_changes() and strip_tracked_changes() (DOCX-04, D-13).

Golden fixtures are created programmatically using lxml to inject
<w:ins>/<w:del> nodes directly into the document XML.
"""
from __future__ import annotations

import pytest
from docx import Document
from docx.oxml.ns import qn
from lxml import etree

from app.pipeline.docx.tracked import has_tracked_changes, strip_tracked_changes


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


@pytest.fixture
def clean_doc():
    """Plain DOCX with no tracked changes."""
    doc = Document()
    doc.add_paragraph("This is clean text with no tracked changes.")
    return doc


@pytest.fixture
def doc_with_insertion():
    """
    DOCX with a <w:ins> element wrapping an inserted run.
    Simulates an accepted insertion that hasn't been finalized.
    """
    doc = Document()
    para = doc.add_paragraph("Before ")
    # Inject <w:ins> directly into the paragraph XML
    # <w:ins w:id="1" w:author="Test" w:date="2026-04-01T00:00:00Z">
    #   <w:r><w:t>inserted</w:t></w:r>
    # </w:ins>
    # <w:r><w:t> after</w:t></w:r>
    ins_xml = (
        '<w:ins xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="1" w:author="Test" w:date="2026-04-01T00:00:00Z">'
        "<w:r><w:t>inserted</w:t></w:r>"
        "</w:ins>"
    )
    ins_elem = etree.fromstring(ins_xml)
    para._element.append(ins_elem)
    # Also append a normal run after
    run = para.add_run(" after")
    return doc


@pytest.fixture
def doc_with_deletion():
    """
    DOCX with a <w:del> element wrapping deleted text.
    """
    doc = Document()
    para = doc.add_paragraph("Keep this. ")
    del_xml = (
        '<w:del xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="2" w:author="Test" w:date="2026-04-01T00:00:00Z">'
        '<w:r><w:delText>deleted text</w:delText></w:r>'
        "</w:del>"
    )
    del_elem = etree.fromstring(del_xml)
    para._element.append(del_elem)
    return doc


@pytest.fixture
def doc_with_both():
    """DOCX with both <w:ins> and <w:del> elements."""
    doc = Document()
    para = doc.add_paragraph("Base text. ")
    ins_xml = (
        '<w:ins xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="3" w:author="Test" w:date="2026-04-01T00:00:00Z">'
        "<w:r><w:t>addition</w:t></w:r>"
        "</w:ins>"
    )
    del_xml = (
        '<w:del xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'w:id="4" w:author="Test" w:date="2026-04-01T00:00:00Z">'
        '<w:r><w:delText>removal</w:delText></w:r>'
        "</w:del>"
    )
    para._element.append(etree.fromstring(ins_xml))
    para._element.append(etree.fromstring(del_xml))
    return doc


# ---------------------------------------------------------------------------
# has_tracked_changes tests (DOCX-04)
# ---------------------------------------------------------------------------


def test_has_tracked_changes_returns_false_for_clean_doc(clean_doc):
    """A document with no tracked changes must return False."""
    assert has_tracked_changes(clean_doc) is False


def test_has_tracked_changes_detects_insertion(doc_with_insertion):
    """A document with <w:ins> must return True."""
    assert has_tracked_changes(doc_with_insertion) is True


def test_has_tracked_changes_detects_deletion(doc_with_deletion):
    """A document with <w:del> must return True."""
    assert has_tracked_changes(doc_with_deletion) is True


def test_has_tracked_changes_detects_both(doc_with_both):
    """A document with both <w:ins> and <w:del> must return True."""
    assert has_tracked_changes(doc_with_both) is True


# ---------------------------------------------------------------------------
# strip_tracked_changes tests (D-13)
# ---------------------------------------------------------------------------


def test_strip_tracked_changes_removes_deletion(doc_with_deletion):
    """
    strip_tracked_changes must remove <w:del> elements entirely.
    The deleted text should not appear in the document body after stripping.
    """
    result = strip_tracked_changes(doc_with_deletion)
    body_xml = result._element.xml
    assert "<w:del" not in body_xml
    # Deleted text must be gone
    assert "deleted text" not in body_xml


def test_strip_tracked_changes_unwraps_insertion(doc_with_insertion):
    """
    strip_tracked_changes must unwrap <w:ins> elements: keep child <w:r> runs,
    remove the <w:ins> wrapper. The inserted text becomes regular text.
    """
    result = strip_tracked_changes(doc_with_insertion)
    body_xml = result._element.xml
    assert "<w:ins" not in body_xml
    # Inserted text must still be present as a regular run
    assert "inserted" in body_xml


def test_strip_tracked_changes_cleans_both(doc_with_both):
    """After stripping, neither <w:ins> nor <w:del> must remain."""
    result = strip_tracked_changes(doc_with_both)
    body_xml = result._element.xml
    assert "<w:ins" not in body_xml
    assert "<w:del" not in body_xml


def test_strip_tracked_changes_no_longer_detected(doc_with_both):
    """After strip, has_tracked_changes must return False."""
    stripped = strip_tracked_changes(doc_with_both)
    assert has_tracked_changes(stripped) is False


def test_strip_tracked_changes_preserves_clean_text(doc_with_deletion):
    """
    strip_tracked_changes must not affect non-tracked text.
    'Keep this.' must survive.
    """
    result = strip_tracked_changes(doc_with_deletion)
    body_xml = result._element.xml
    assert "Keep this." in body_xml
