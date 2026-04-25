"""
PPTX presentation traversal and segment extraction.

PPTX-01: Full shape traversal — text boxes, speaker notes, tables, master slides.
PPTX-02: SmartArt shapes detected (is_smartart()) + flagged; not silently skipped.
PPTX-03: Overflow detection runs post-translate in reassembler.
PPTX-04: GroupShape walker recurses via walk_shape_tree().
D-06:    Segment ID is sha256(source_text + structural_position)[:16].
CORE-04: NFC normalization applied at extraction time.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Iterator
from typing import TYPE_CHECKING

from pptx.enum.shapes import MSO_SHAPE_TYPE

from app.pipeline.pptx.smartart import extract_smartart_text, is_smartart
from app.pipeline.segment import Segment

if TYPE_CHECKING:
    from pptx import Presentation
    from pptx.shapes.shapetree import SlideShapes


def _nfc(s: str) -> str:
    """CORE-04: NFC normalize at extraction time."""
    return unicodedata.normalize("NFC", s)


def walk_text_frame(text_frame, shape_pos: str, seq: list[int]) -> Iterator[Segment]:
    """
    Yield Segments for each non-empty paragraph in a text frame.

    structural_position: {shape_pos}.tf.0.para.{para_idx}
    """
    for para_idx, para in enumerate(text_frame.paragraphs):
        text = _nfc(para.text.strip())
        if not text:
            continue
        pos = f"{shape_pos}.tf.0.para.{para_idx}"
        yield Segment.from_text(
            source_text=text,
            structural_position=pos,
            seq_in_job=seq[0],
        )
        seq[0] += 1


def walk_table(table, shape_pos: str, seq: list[int]) -> Iterator[Segment]:
    """
    Walk table cells in row-major order; yield one Segment per non-empty paragraph.

    structural_position: {shape_pos}.table.row.{R}.col.{C}.para.{K}
    [VERIFIED: Context7 /scanny/python-pptx table cell traversal docs]
    """
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            for para_idx, para in enumerate(cell.text_frame.paragraphs):
                text = _nfc(para.text.strip())
                if not text:
                    continue
                pos = f"{shape_pos}.table.row.{row_idx}.col.{col_idx}.para.{para_idx}"
                yield Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                )
                seq[0] += 1


def walk_shape_tree(
    shapes: "SlideShapes",
    slide_idx: int,
    seq: list[int],
    pos_prefix: str,
) -> Iterator[Segment]:
    """
    Recursively walk all shapes on a slide (or in a group).

    Order of checks is CRITICAL:
    1. GROUP → recurse (must check before has_text_frame — groups never have text frames)
    2. is_smartart() → extract text + smartart structural_position (D-03-01)
       MUST check BEFORE has_text_frame — SmartArt has_text_frame=False, would be silently skipped
    3. TABLE → walk_table
    4. has_text_frame → walk_text_frame

    [PPTX-04: VERIFIED group recursion terminates — slide.shapes is SlideShapes, not GroupShape]
    """
    for shape_idx, shape in enumerate(shapes):
        shape_pos = f"{pos_prefix}.shape.{shape_idx}"

        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            # PPTX-04: recurse into group children
            yield from walk_shape_tree(
                shape.shapes,
                slide_idx,
                seq,
                f"{shape_pos}.group",
            )

        elif is_smartart(shape):
            # D-03-01: SmartArt — translate text best-effort, structural_position ends in .smartart
            # write-back is SKIPPED in reassembler (D-03-01)
            text = _nfc(extract_smartart_text(shape).strip())
            if text:
                pos = f"{shape_pos}.smartart"
                yield Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                )
                seq[0] += 1

        elif shape.shape_type == MSO_SHAPE_TYPE.TABLE:
            yield from walk_table(shape.table, shape_pos, seq)

        elif shape.has_text_frame:
            yield from walk_text_frame(shape.text_frame, shape_pos, seq)


def _extract_notes_segments(slide, slide_idx: int, seq: list[int]) -> list[Segment]:
    """
    Extract speaker notes as Segments.

    structural_position: slide.{N}.notes.para.{K}
    [VERIFIED: Context7 /scanny/python-pptx notes_slide, notes_text_frame docs]
    """
    if not slide.has_notes_slide:
        return []
    notes_tf = slide.notes_slide.notes_text_frame
    segments: list[Segment] = []
    for para_idx, para in enumerate(notes_tf.paragraphs):
        text = _nfc(para.text.strip())
        if not text:
            continue
        pos = f"slide.{slide_idx}.notes.para.{para_idx}"
        segments.append(Segment.from_text(
            source_text=text,
            structural_position=pos,
            seq_in_job=seq[0],
        ))
        seq[0] += 1
    return segments


def _extract_master_segments(prs: "Presentation", seq: list[int]) -> list[Segment]:
    """
    Extract master slide text, deduplicated by segment ID.

    Translates each master shape's text once. structural_position: master.{N}.shape.{M}.para.{K}
    Master text is extracted before slide loop so master translations can be applied during reassembly.
    [ASSUMED: A1 — master text edits propagate to layout slides; empirical verification recommended]
    """
    segments: list[Segment] = []
    seen_ids: set[str] = set()
    for master_idx, master in enumerate(prs.slide_masters):
        for shape_idx, shape in enumerate(master.shapes):
            if not shape.has_text_frame:
                continue
            for para_idx, para in enumerate(shape.text_frame.paragraphs):
                text = _nfc(para.text.strip())
                if not text:
                    continue
                pos = f"master.{master_idx}.shape.{shape_idx}.para.{para_idx}"
                seg = Segment.from_text(
                    source_text=text,
                    structural_position=pos,
                    seq_in_job=seq[0],
                )
                if seg.id in seen_ids:
                    continue  # deduplicate
                seen_ids.add(seg.id)
                segments.append(seg)
                seq[0] += 1
    return segments


def extract_pptx_segments(prs: "Presentation", job_id: str) -> list[Segment]:
    """
    Walk the entire presentation and return an ordered Segment list.

    Walk order: master slides (once, deduplicated) → slides[N] body shapes → slides[N] notes.
    Skips empty text. NFC-normalizes at extraction time (CORE-04).

    Returns: list[Segment] — ordered by walk order for reassembly lookup via structural_position.
    """
    segments: list[Segment] = []
    seq = [0]  # mutable int in list — shared counter across nested helpers

    # Master slides first (once per master, deduplicated by seg ID)
    segments.extend(_extract_master_segments(prs, seq))

    for slide_idx, slide in enumerate(prs.slides):
        # Body shapes — recursive walk
        for seg in walk_shape_tree(slide.shapes, slide_idx, seq, f"slide.{slide_idx}"):
            segments.append(seg)
        # Speaker notes
        segments.extend(_extract_notes_segments(slide, slide_idx, seq))

    return segments
