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
import re as _re
import unicodedata

import pymupdf

from app.pipeline.pdf.columns import cluster_columns
from app.pipeline.segment import Segment

# ---------------------------------------------------------------------------
# Math / symbol font detection
# ---------------------------------------------------------------------------

# Passthrough prefixes — subsets associated with math/symbol encoding.
# NOTE: AdvTT* (body-text subsets carrying Latin/CJK glyphs) are NOT in this
# list — they translate correctly with Noto fonts.
_MATH_FONT_PREFIXES = (
    "AdvP",      # math/symbol subset prefix (AdvP4C4E74, etc.)
    "CMSY",      # TeX Computer Modern Symbol
    "CMR",       # TeX Computer Modern Roman (used in math mode)
    "STIX",      # STIX math fonts
    "MathFont",  # generic MathFont* naming
    "MT",        # MathType fonts (MT-Extra, MT-Symbol, etc.)
)

# Exact match for legacy symbol fonts
_MATH_FONT_EXACT: frozenset[str] = frozenset({"Symbol", "ZapfDingbats", "Wingdings"})

# Keyword pattern: any font whose name contains "math", "symbol", or "glyph"
_MATH_FONT_PATTERN = _re.compile(r"math|symbol|glyph", _re.IGNORECASE)


def _is_math_font(font_name: str) -> bool:
    """
    Return True if font_name belongs to a math/symbol encoding that Noto cannot represent.

    Passthrough condition: font is a math/symbol subset whose glyphs are
    encoded outside Unicode ranges covered by Noto Sans / Noto Sans CJK.
    Translating these spans and reinserting via insert_htmlbox produces
    missing-glyph boxes — so we skip redact+reinsert entirely.

    Body-font subsets that look similar (AdvTT*) are NOT math fonts —
    they carry Latin/CJK glyphs in a custom encoding and translate correctly.

    CONTEXT.md D-03.2 font allowlist: body fonts to pass through as "text":
      Noto*, Helvetica*, Times*, Arial*, Calibri*, Cambria*, MyriadPro*,
      Roboto*, Liberation*, DejaVu*, Open Sans*, AdvTT* (body subsets).
    """
    if font_name in _MATH_FONT_EXACT:
        return True
    # Strip PSNAME subset prefix (e.g. "ABCDEF+AdvP4C4E74" → "AdvP4C4E74")
    base = font_name.split("+")[-1] if "+" in font_name else font_name
    if base.startswith(_MATH_FONT_PREFIXES):
        return True
    if _MATH_FONT_PATTERN.search(base):
        return True
    return False


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


def _is_bold_font(font_name: str) -> bool:
    """
    Detect bold via font-name suffix when PDF flags don't carry the bold bit.

    Subset fonts in academic PDFs often encode style via name suffix instead
    of the get_text() flags field — e.g. `AdvTTaf7f9f4f.B` is the bold variant
    of `AdvTTaf7f9f4f`. Spot-checked on the BMC paper (`flags=4` for "RESEARCH
    ARTICLE" but font name ends in `.B`).
    """
    if not font_name:
        return False
    base = font_name.split("+")[-1]  # strip subset prefix `ABCDEF+...`
    base_lower = base.lower()
    return (
        base.endswith(".B")
        or base.endswith("-Bold")
        or "bold" in base_lower
        or "black" in base_lower
        or "heavy" in base_lower
    )


def _is_italic_font(font_name: str) -> bool:
    """
    Detect italic via font-name suffix (mirrors `_is_bold_font`).
    """
    if not font_name:
        return False
    base = font_name.split("+")[-1]
    base_lower = base.lower()
    return (
        base.endswith(".I")
        or base.endswith("-Italic")
        or base.endswith("-Oblique")
        or "italic" in base_lower
        or "oblique" in base_lower
    )


def _block_body_font(block: dict, block_body_pt: float) -> str:
    """
    Return the most common font name among spans whose size matches the
    block's body size, weighted by character count. Used by spans_to_html
    to flag variant-font spans (different font at the same size = likely
    bold/italic variant).

    Weighting by character count (not span count) keeps the body font
    winning in academic-paper blocks where label spans like "Background:"
    appear roughly as often as the surrounding body span chunks but
    contribute far fewer characters overall.
    """
    from collections import Counter  # noqa: PLC0415

    font_chars: Counter[str] = Counter()
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            size = span.get("size", 0.0)
            if size > 0 and abs(round(size * 2) / 2 - block_body_pt) < 0.6:
                name = span.get("font", "")
                text = span.get("text", "") or ""
                if name and text:
                    font_chars[name] += len(text)
    if not font_chars:
        return ""
    return font_chars.most_common(1)[0][0]


def _page_body_font_size(text_blocks: list[dict]) -> float:
    """
    Estimate the page-level body font size by finding the modal size across
    every span in every text block on the page.

    Page-level mode is required to detect heading-only blocks (uniform large
    font) — per-block mode would compare a heading-only block against itself
    and miss the heading classification.
    """
    from collections import Counter  # noqa: PLC0415

    sizes: list[float] = []
    for block in text_blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0.0)
                if size > 0:
                    sizes.append(round(size * 2) / 2)
    if not sizes:
        return 12.0
    counter = Counter(sizes)
    max_count = counter.most_common(1)[0][1]
    candidates = [sz for sz, cnt in counter.items() if cnt == max_count]
    return min(candidates)


def spans_to_html(block: dict, page_body_pt: float | None = None) -> str:
    """
    Convert a page.get_text("dict") text block to minimal HTML.

    Preserves bold (<b>) and italic (<i>) based on span flags AND font-name suffix:
      flags bit 4 (0x10 = 16): bold | flags bit 1 (0x02 = 2): italic
      font-name `.B` / `-Bold` / contains "bold|black|heavy" → bold
      font-name `.I` / `-Italic` / `-Oblique` / contains "italic|oblique" → italic

    Heading detection (Gap 3 + page-level extension):
      - Per-span: span size compared to block body size — catches inline headings
      - Per-block: when caller passes `page_body_pt` and the entire block is
        uniformly larger than the page body size, the whole block is wrapped
        in <h1>/<h2>. This catches title-only blocks where per-block detection
        fails (block has only one size = its own body baseline).
    """
    block_body_pt = _body_font_size(block)
    # If a page-level body size is supplied, use it for the per-block heading
    # check below — this catches title blocks (uniform large size) that the
    # per-span check would miss.
    page_pt = page_body_pt if page_body_pt and page_body_pt > 0 else block_body_pt
    block_heading_level = _detect_heading_level(block_body_pt, page_pt)

    # Detect the block's primary body font — the most common font name across
    # spans whose size matches the block body size. Spans inside the same
    # block that use a DIFFERENT font name at the same size are likely a
    # bold/italic variant in disguise (subset fonts that don't carry .B/.I
    # suffixes — common in academic-paper PDFs where 'Background:' /
    # 'Methods:' labels are inline-bold).
    block_body_font = _block_body_font(block, block_body_pt)

    # Pass 1 — collect spans as (text, style) tuples where style is one of
    # 'h1', 'h2', 'b', 'i', 'bi', or '' (plain). Adjacent spans with the same
    # style are merged into a single run so e.g. "Open Access" doesn't end up
    # as <b>Open</b><b> </b><b>Access</b>.
    runs: list[tuple[str, str]] = []  # (text, style)

    def _push(text: str, style: str) -> None:
        if runs and runs[-1][1] == style:
            runs[-1] = (runs[-1][0] + text, style)
        else:
            runs.append((text, style))

    for line_idx, line in enumerate(block.get("lines", [])):
        if line_idx > 0 and runs:
            # PDF line breaks inside a block are visually a space — keep as
            # a plain-style space so adjacent same-style runs across lines
            # still merge into one tag where appropriate.
            _push(" ", "")
        for span in line.get("spans", []):
            text = span.get("text", "")
            if not text:
                continue
            flags = span.get("flags", 0)
            font_name = span.get("font", "")
            span_size = span.get("size", 0.0)
            # Bold/italic detection layers (in priority order):
            #  1. PDF span flag bit
            #  2. Font-name suffix / keyword
            #  3. Variant font in body-size span (different font from block
            #     primary at the same size → treat as bold)
            is_bold = bool(flags & (2**4)) or _is_bold_font(font_name)
            is_italic = bool(flags & (2**1)) or _is_italic_font(font_name)
            if (
                not is_bold
                and not is_italic
                and block_body_font
                and font_name
                and font_name != block_body_font
                and abs(span_size - block_body_pt) < 0.6  # same size as body
                and not _is_math_font(font_name)
            ):
                is_bold = True

            # Per-span heading level (mixed-size block); fall back to block-level
            heading_level = (
                _detect_heading_level(span_size, block_body_pt)
                or block_heading_level
            )
            if heading_level == 1:
                style = "h1"
            elif heading_level == 2:
                style = "h2"
            elif is_bold and is_italic:
                style = "bi"
            elif is_bold:
                style = "b"
            elif is_italic:
                style = "i"
            else:
                style = ""
            _push(text, style)

    # Pass 2 — render runs with line-break heuristic. Insert a <br> before a
    # bold run that looks like an inline section label or a new list item:
    #   - Run is NOT at the start of the block
    #   - Run is bold (style 'b' or 'bi')
    #   - Either ends with `:` (label like 'Background:') OR ends with `.` (list
    #     item like 'Supplementary Table 1.')
    #   - The preceding non-empty run ends with a sentence terminator
    #     `. ? ! :` so we don't break inside running prose
    # This catches multi-label abstract paragraphs and supplementary lists
    # while leaving inline bold words inside a sentence untouched.
    parts: list[str] = []
    seen_visible_content = False
    prev_run_stripped = ""
    last_emitted_was_block_leading_heading = False
    for text, style in runs:
        stripped = text.strip()
        prev_terminates = prev_run_stripped.endswith((".", "?", "!", ":"))
        looks_like_inline_label = (
            style in ("b", "bi")
            and seen_visible_content
            and prev_terminates
            and 2 <= len(stripped) <= 80
            and stripped.endswith((":", "."))
        )
        if looks_like_inline_label:
            parts.append("<br>")

        # Block-leading heading detection: a bold run that opens the block
        # AND does NOT end with `:` is a section header (e.g.
        # 'Acknowledgements', 'Supplementary Information', 'Funding').
        # Inline labels ending with `:` (e.g. 'Background:') stay inline.
        is_block_leading_heading = (
            style in ("b", "bi", "h1", "h2")
            and not seen_visible_content
            and stripped
            and not stripped.endswith(":")
            and len(stripped) >= 3
        )

        # Body run that follows a block-leading heading → insert <br>
        # before this run so the heading and body sit on separate lines.
        if last_emitted_was_block_leading_heading and stripped and style not in ("h1", "h2"):
            # Suppress the break if this run is itself another heading-style
            # run that should stay adjacent (rare).
            parts.append("<br>")
            last_emitted_was_block_leading_heading = False

        escaped = _html.escape(text)
        if style == "h1":
            parts.append(f"<h1>{escaped}</h1>")
        elif style == "h2":
            parts.append(f"<h2>{escaped}</h2>")
        elif style == "bi":
            parts.append(f"<b><i>{escaped}</i></b>")
        elif style == "b":
            parts.append(f"<b>{escaped}</b>")
        elif style == "i":
            parts.append(f"<i>{escaped}</i>")
        else:
            parts.append(escaped)
        if stripped:
            seen_visible_content = True
            prev_run_stripped = stripped
            if is_block_leading_heading:
                last_emitted_was_block_leading_heading = True
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

        # Page-level body font size — used by spans_to_html to detect title-only
        # blocks (uniform large font) that per-block detection would miss.
        page_body_pt = _page_body_font_size(text_blocks)

        # --- Table cell extraction (CONTEXT.md: find_tables() cell walk) ---
        # Runs before the non-table block walk. Collects table bbox regions so
        # that overlapping blocks can be filtered from the non-table walk, preventing
        # double-emission of table content.
        table_block_bboxes: list[pymupdf.Rect] = []

        try:
            finder = page.find_tables()
            for table_idx, table in enumerate(finder.tables):
                table_rect = pymupdf.Rect(table.bbox)
                table_block_bboxes.append(table_rect)

                for r in range(table.row_count):
                    for c in range(table.col_count):
                        cell_idx = r * table.col_count + c
                        if cell_idx >= len(table.cells):
                            continue
                        cell = table.cells[cell_idx]
                        if cell is None:
                            continue  # merged cell — skip
                        cell_rect = pymupdf.Rect(cell)
                        # Get cell text — page.get_textbox clips to the rect
                        raw = _nfc(page.get_textbox(cell_rect).strip())
                        if not raw:
                            continue
                        pos = f"page.{page_num}.table.{table_idx}.row.{r}.col.{c}"
                        segments.append(Segment.from_text(
                            source_text=raw,
                            structural_position=pos,
                            seq_in_job=seq,
                            kind="table_cell",
                        ))
                        seq += 1
        except Exception as _table_exc:  # noqa: BLE001
            # T-03.2-02-1: malformed PDF — fall through to non-table block walk
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "find_tables() failed on page %d: %s", page_num, _table_exc
            )
            table_block_bboxes = []  # reset so no blocks are filtered

        # Filter out blocks whose bbox intersects any detected table region.
        # These blocks are already handled by the cell walk above (T-03.2-02-3).
        non_table_blocks = [
            b for b in text_blocks
            if not any(
                pymupdf.Rect(b["bbox"]).intersects(tr)
                for tr in table_block_bboxes
            )
        ]

        if not non_table_blocks:
            continue

        column_groups, is_degraded = cluster_columns(non_table_blocks, page.rect.width)

        for col_idx, col_blocks in enumerate(column_groups):
            for block_idx, block in enumerate(col_blocks):
                # Build structural_position first — used by both paths.
                if is_degraded:
                    pos = f"page.{page_num}.block.{block_idx}"
                else:
                    pos = f"page.{page_num}.col.{col_idx}.block.{block_idx}"

                # Check if ANY non-empty span in this block uses a math/symbol font.
                # If so, emit the whole block as math_passthrough (skip translation).
                # Math-font blocks in real PDFs are standalone symbol blocks, not
                # mixed with translatable text, so whole-block passthrough is correct.
                all_spans: list[dict] = [
                    span
                    for line in block.get("lines", [])
                    for span in line.get("spans", [])
                ]
                has_math_font = any(
                    _is_math_font(span.get("font", ""))
                    for span in all_spans
                    if span.get("text", "").strip()
                )

                if has_math_font:
                    # CONTEXT.md: math_passthrough — source glyphs stay visible,
                    # translation skipped; reassembler leaves region untouched.
                    raw_text = _nfc(" ".join(
                        span.get("text", "")
                        for line in block.get("lines", [])
                        for span in line.get("spans", [])
                    ).strip())
                    if not raw_text:
                        continue
                    segments.append(Segment.from_text(
                        source_text=raw_text,
                        structural_position=pos,
                        seq_in_job=seq,
                        kind="math_passthrough",
                    ))
                    seq += 1
                    continue  # skip normal spans_to_html path for this block

                # Normal translatable block (existing path, unchanged).
                # Block data from "dict" extraction already has "text" in spans.
                # No need for per-block clip extraction — use block directly.
                html = spans_to_html(block, page_body_pt=page_body_pt)
                text = _nfc(html.strip())
                if not text:
                    continue

                segments.append(Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq,
                ))
                seq += 1

    return segments
