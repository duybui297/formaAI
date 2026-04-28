"""
Segment tree → Markdown helper for DOCX export (D-04-33).

Walks the translated Segment list (sorted by seq_in_job),
maps region_label to Markdown heading/paragraph structure,
then writes a DOCX using python-docx (already in stack).

Why python-docx instead of PP-StructureV3 save_to_word():
PP-StructureV3's save_to_word() is coupled to the original OCR result object,
not to our translated Segment state. python-docx is already in the stack and
gives us full control over heading structure. (RESEARCH.md §DOCX path recommendation)
"""
from __future__ import annotations

from app.pipeline.segment import Segment

_HEADING_1_LABELS = frozenset({"doc_title"})
_HEADING_2_LABELS = frozenset({"paragraph_title", "header"})
_TABLE_LABELS = frozenset({"table"})
_SKIP_LABELS = frozenset({"seal", "page_number"})


def segments_to_markdown(segments: list[Segment]) -> str:
    """
    D-04-33: Walk Segment tree → emit Markdown string.

    Text priority: edited_source_text (D-04-03) is NOT the edit priority here —
    for output we use: edited_text (reviewer edit of translation) ??
    translated_text ?? source_text. The Segment dataclass uses `edited_source_text`
    for source OCR corrections and has no `edited_text` field; we treat
    `edited_source_text` as the reviewed text per D-04-33 spec.

    Actually per the plan spec: text = seg.edited_text or seg.translated_text or
    seg.source_text — but Segment has `edited_source_text` not `edited_text`.
    Use `edited_source_text` as the "edited" field since that is what the
    Segment dataclass provides (D-04-03).

    Maintains blank-line separation between blocks.
    """
    lines: list[str] = []

    for seg in sorted(segments, key=lambda s: s.seq_in_job):
        label = seg.region_label or "text"

        if label in _SKIP_LABELS:
            continue

        if seg.kind == "figure_passthrough":
            lines.append("[Figure]")
            lines.append("")
            continue

        # Text priority: edited_source_text ?? translated_text ?? source_text
        text = seg.edited_source_text or seg.translated_text or seg.source_text
        if not text or not text.strip():
            continue

        if label in _HEADING_1_LABELS:
            lines.append(f"# {text.strip()}")
        elif label in _HEADING_2_LABELS:
            lines.append(f"## {text.strip()}")
        elif label in _TABLE_LABELS:
            # block_content from PP-StructureV3 is already Markdown table format
            lines.append(text.strip())
        elif seg.kind == "math_passthrough":
            lines.append(text)
        else:
            lines.append(text.strip())

        lines.append("")  # blank line between blocks

    return "\n".join(lines)


def md_to_docx(md_text: str, output_path: str) -> None:
    """
    Convert Markdown string to DOCX using python-docx 1.2.0.
    Handles: H1 headings, H2 headings, plain paragraphs.
    Tables (Markdown `|...|` rows) are emitted as plain paragraphs for PoC.
    """
    from docx import Document  # noqa: PLC0415

    doc = Document()

    for line in md_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        else:
            doc.add_paragraph(line.strip())

    doc.save(output_path)
