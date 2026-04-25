"""
Native PDF text extraction using PyMuPDF.

PDF-01: Parse text-layer PDF; extract each text block's bbox, font info, and text.
D-03-03: Cluster blocks by x-coordinate into columns (cluster_columns()).
D-03-06: HTML round-trip approach — spans_to_html() generates minimal HTML preserving bold/italic.
CORE-04: NFC normalization applied at extraction time.

FORMAT CHOICE: Use page.get_text("dict") which provides span-level "text" strings.
  - "html" format: clip parameter is IGNORED (RESEARCH.md Q7, Pitfall #4) — do NOT use
  - "rawdict" format: spans have per-character "chars" lists, not "text" strings
  - "dict" format: spans have "text" strings + "flags" for bold/italic — optimal for us
  Full-page "dict" extraction is used for block discovery and clustering; the block
  data from that same extraction is reused directly for spans_to_html(), avoiding
  redundant per-block clips.
PITFALL: image blocks (type==1) have no "lines" key — ALWAYS filter type==0 only.
"""
from __future__ import annotations

import unicodedata

import pymupdf

from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.segment import Segment


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time."""
    return unicodedata.normalize("NFC", s)


def spans_to_html(block: dict) -> str:
    """
    Convert a page.get_text("dict") text block to minimal HTML.

    Preserves bold (<b>) and italic (<i>) based on span flags:
      bit 4 (0x10 = 16): bold
      bit 1 (0x02 = 2):  italic
    [VERIFIED: Context7 /websites/pymupdf_readthedocs_io_en — span flags documentation]

    Accepts blocks from get_text("dict") format where each span has a "text" key.
    Returns plain-text (no HTML tags) if no formatting detected — valid HTML input.
    """
    parts: list[str] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text:
                continue
            flags = span.get("flags", 0)
            is_bold = bool(flags & (2**4))
            is_italic = bool(flags & (2**1))
            if is_bold and is_italic:
                parts.append(f"<b><i>{text}</i></b>")
            elif is_bold:
                parts.append(f"<b>{text}</b>")
            elif is_italic:
                parts.append(f"<i>{text}</i>")
            else:
                parts.append(text)
        parts.append(" ")  # line separator
    return "".join(parts).strip()


def extract_pdf_segments(doc: pymupdf.Document, job_id: str) -> list[Segment]:
    """
    Walk all pages; extract text blocks; cluster columns; build Segment list.

    Walk order: pages in order → columns left-to-right → blocks top-to-bottom.
    structural_position:
      2-col (normal): page.{N}.col.{C}.block.{B}
      degraded (3+):  page.{N}.block.{B}

    Segments use source_text = spans_to_html(block) to preserve bold/italic for
    the HTML round-trip reassembly (D-03-06).

    Args
    ----
    doc     : pymupdf.Document (already opened by worker)
    job_id  : str — not used for ID generation (Segment.from_text uses sha256 of content+pos)

    Returns
    -------
    list[Segment] ordered by extraction walk order.
    """
    segments: list[Segment] = []
    seq = 0

    for page_num, page in enumerate(doc):
        # Filter: text blocks only — image blocks (type==1) have no "lines" key
        # Use "dict" format: spans have "text" + "flags" (bold/italic).
        # DO NOT use "html" (clip ignored) or "rawdict" (chars not text).
        raw_blocks = page.get_text("dict")["blocks"]
        text_blocks = [b for b in raw_blocks if b["type"] == 0]

        if not text_blocks:
            continue

        column_groups, is_degraded = cluster_columns(text_blocks, page.rect.width)

        for col_idx, col_blocks in enumerate(column_groups):
            for block_idx, block in enumerate(col_blocks):
                # Block data from "dict" extraction already has "text" in spans.
                # No need for per-block clip extraction — use block directly.
                html = spans_to_html(block)
                text = _nfc(html.strip())
                if not text:
                    continue

                # Build structural_position
                if is_degraded:
                    pos = f"page.{page_num}.block.{block_idx}"
                else:
                    pos = f"page.{page_num}.col.{col_idx}.block.{block_idx}"

                segments.append(Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq,
                ))
                seq += 1

    return segments
