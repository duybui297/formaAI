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

import html as _html
import unicodedata

import pymupdf

from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.segment import Segment


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time."""
    return unicodedata.normalize("NFC", s)


def _detect_heading_level(span_font_size: float, body_font_size: float) -> int:
    """
    Classify a span's font size relative to the block's body font size.

    Returns:
      1 → h1 (span_font_size >= body_font_size * 1.8)
      2 → h2 (span_font_size >= body_font_size * 1.4 and < 1.8x)
      0 → body text (below 1.4x threshold)

    Gap 3 (UAT Test 7): Font-size-threshold approach avoids cluster analysis overhead.
      - Academic papers: section titles typically 14-18pt on 10-12pt body → ratio 1.4-1.5
      - Document headings: 18-24pt on 12pt body → ratio 1.5-2.0
      - T-03.1-05 guard: body_font_size <= 0 returns 0 (body) to handle malicious PDFs
    """
    if body_font_size <= 0:
        return 0
    ratio = span_font_size / body_font_size
    if ratio >= 1.8:
        return 1
    if ratio >= 1.4:
        return 2
    return 0


def _body_font_size(block: dict) -> float:
    """
    Estimate the body font size for a block by finding the mode (most common)
    font size across all spans.

    Rounds to 0.5pt precision to group near-identical sizes (e.g. 11.9 and 12.0).
    Falls back to 12.0 if block is empty or all spans have size <= 0.

    Tie-breaking: when multiple sizes share the highest count, the smallest size
    is returned — body text is always the smallest and most frequent size in a block.
    This is correct for real PDFs where heading spans (large, few) coexist with
    body spans (small, many), and also handles synthetic test blocks where each
    size appears exactly once.
    """
    from collections import Counter  # noqa: PLC0415

    sizes: list[float] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            size = span.get("size", 0.0)
            if size > 0:
                sizes.append(round(size * 2) / 2)  # round to 0.5pt
    if not sizes:
        return 12.0
    counter = Counter(sizes)
    max_count = counter.most_common(1)[0][1]
    # Among all sizes with the highest count, pick the smallest (body baseline)
    candidates = [sz for sz, cnt in counter.items() if cnt == max_count]
    return min(candidates)


def spans_to_html(block: dict) -> str:
    """
    Convert a page.get_text("dict") text block to minimal HTML.

    Preserves bold (<b>) and italic (<i>) based on span flags:
      bit 4 (0x10 = 16): bold
      bit 1 (0x02 = 2):  italic
    [VERIFIED: Context7 /websites/pymupdf_readthedocs_io_en — span flags documentation]

    Gap 3 (UAT Test 7): Emits <h1>/<h2> for spans whose font size is significantly
    larger than the block's body font size (via _detect_heading_level).
    Heading spans do NOT get an additional <b> wrapper — <h1>/<h2> carry bold weight.

    Accepts blocks from get_text("dict") format where each span has a "text" key.
    Returns plain-text (no HTML tags) if no formatting detected — valid HTML input.
    """
    body_pt = _body_font_size(block)
    parts: list[str] = []
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text:
                continue
            escaped = _html.escape(text)  # prevent injection of <, >, & from PDF text
            flags = span.get("flags", 0)
            is_bold = bool(flags & (2**4))
            is_italic = bool(flags & (2**1))
            span_size = span.get("size", 0.0)
            heading_level = _detect_heading_level(span_size, body_pt)

            if heading_level == 1:
                # h1: italic still applies if set; skip <b> — <h1> carries bold weight
                inner = f"<i>{escaped}</i>" if is_italic else escaped
                parts.append(f"<h1>{inner}</h1>")
            elif heading_level == 2:
                inner = f"<i>{escaped}</i>" if is_italic else escaped
                parts.append(f"<h2>{inner}</h2>")
            elif is_bold and is_italic:
                parts.append(f"<b><i>{escaped}</i></b>")
            elif is_bold:
                parts.append(f"<b>{escaped}</b>")
            elif is_italic:
                parts.append(f"<i>{escaped}</i>")
            else:
                parts.append(escaped)
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
