"""
DOCX tracked-changes detection and stripping.

DOCX-04, D-13: detect <w:ins>/<w:del> on upload.
If present, the upload form shows a modal with strip/preserve/cancel choices.

strip_tracked_changes():
  - <w:ins>: unwrap — move child <w:r> elements out to parent, remove <w:ins> wrapper.
    The inserted text becomes regular text, visible to the translator.
  - <w:del>: remove entirely — deleted text is gone from the document.

This module does NOT perform preserve_tracked_changes (D-14 full implementation
is deferred to a later plan — comment-as-segment support). The current implementation
covers the strip path required for D-13.
"""
from __future__ import annotations

from docx import Document
from docx.oxml.ns import qn


def has_tracked_changes(doc: Document) -> bool:
    """
    DOCX-04: Detect <w:ins> or <w:del> in the document body XML.

    Called on upload to determine whether to show the tracked-changes modal (D-13).
    Uses a simple string search on the serialized XML — fast and reliable.
    """
    body_xml: str = doc._element.xml
    return "<w:ins" in body_xml or "<w:del" in body_xml


def strip_tracked_changes(doc: Document) -> Document:
    """
    D-13 strip option: remove tracked changes, keeping the final accepted text.

    - <w:ins> elements: unwrap — move all child elements to the parent, removing
      the <w:ins> wrapper. Inserted runs become regular runs.
    - <w:del> elements: remove entirely. Deleted text is discarded.

    The source file at input_path is preserved by the caller (T-04-01).
    This function mutates the doc object and returns it.
    """
    body = doc._element.body

    # Process insertions: unwrap <w:ins>, promote children to parent
    # Collect all <w:ins> first to avoid modifying tree while iterating
    ins_elements = list(body.findall(f".//{qn('w:ins')}"))
    for ins in ins_elements:
        parent = ins.getparent()
        if parent is None:
            continue
        idx = list(parent).index(ins)
        for child in list(ins):
            parent.insert(idx, child)
            idx += 1
        parent.remove(ins)

    # Process deletions: remove <w:del> entirely
    del_elements = list(body.findall(f".//{qn('w:del')}"))
    for del_elem in del_elements:
        parent = del_elem.getparent()
        if parent is None:
            continue
        parent.remove(del_elem)

    return doc
