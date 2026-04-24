"""
DOCX reassembler — write translated text back into a Document.

DOCX-02: run-merge write-back invariant.
  NEVER call paragraph.text = value — it calls paragraph.clear() which
  destroys ALL <w:rPr> formatting (bold, italic, underline, font, color).
  Instead: writes into runs[0].text only, blanks runs[1:] without removing
  the <w:r> elements (preserving all formatting attributes).

CORE-04: NFC-normalize before write-back (both extraction and reassembly sides).
"""
from __future__ import annotations

import unicodedata

from docx import Document
from docx.text.paragraph import Paragraph

from app.pipeline.docx.extractor import walk_document
from app.pipeline.segment import Segment


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize before write-back."""
    return unicodedata.normalize("NFC", s)


def write_translated_paragraph(paragraph: Paragraph, translated_text: str) -> None:
    """
    DOCX-02 run-merge write-back.

    Writes translated_text into the paragraph without destroying run formatting.

    Strategy:
      - If paragraph has runs: write into runs[0].text, blank runs[1:].
        The <w:r> elements and their <w:rPr> children are NOT removed.
        Only the <w:t> content is changed.
      - If paragraph has no runs: add_run(translated_text) as a new run.

    FORBIDDEN anti-pattern: paragraph.text = value
      This calls paragraph.clear() then paragraph.add_run(text), which removes
      ALL <w:r> elements and therefore all bold/italic/underline/font/color.
      Never use it in any docx-writing code (CLAUDE.md anti-pattern table).
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(_nfc(translated_text))
        return

    # Write translated text into first run only
    runs[0].text = _nfc(translated_text)  # touches <w:t>; <w:rPr> preserved intact

    # Blank remaining runs — keep <w:r> elements (with their <w:rPr>) in place
    for run in runs[1:]:
        run.text = ""  # blank <w:t>, do NOT remove <w:r>


def reassemble_docx(
    doc: Document,
    segments: list[Segment],
    translated_texts: dict[str, str],
) -> Document:
    """
    Write translated text back into the document using run-merge strategy.

    translated_texts is keyed by segment.id (D-06 sha256 ID).
    Only segments present in translated_texts are written; others are left as-is.

    The traversal order must exactly match extract_segments() to ensure
    segments align with the correct paragraphs.

    Returns the modified document (same object, mutated in-place).
    """
    seq = 0
    for _, paragraph in walk_document(doc):
        text = paragraph.text
        if not text.strip():
            continue

        if seq < len(segments):
            seg = segments[seq]
            translated = translated_texts.get(seg.id)
            if translated is not None:
                write_translated_paragraph(paragraph, translated)
        seq += 1

    return doc
