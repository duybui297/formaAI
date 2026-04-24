"""
Segment dataclass for the DOCX/PPTX/PDF translation pipeline.

D-05: Rich structural segment with parent-reference tree for reassembly.
D-06: Deterministic ID from sha256(source_text + structural_position)[:16].
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


def make_segment_id(source_text: str, structural_position: str) -> str:
    """
    D-06: sha256(source_text + structural_position)[:16].

    Deterministic and job-independent — enables translation-memory reuse in v2
    without a schema migration. The null byte separator prevents hash collisions
    between ('a', 'bc') and ('ab', 'c').
    """
    payload = f"{source_text}\x00{structural_position}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class Segment:
    """
    D-05: Rich structural segment. Carries structural_position for tree-walk reassembly.
    D-06: Deterministic id from sha256(source_text + structural_position).

    The id column matches Segment.id = String(16) in the ORM (db/models.py).
    """

    id: str  # 16-char hex (D-06)
    seq_in_job: int  # human-readable "segment 5/210"
    source_text: str
    structural_position: str  # e.g. "body.para.0", "body.table.0.row.1.cell.0.para.0"
    is_comment: bool = False  # D-14: comment segments
    is_inserted: bool = False  # D-13: tracked change — inserted text
    is_deleted: bool = False  # D-13: tracked change — deleted text
    translated_text: str | None = None
    run_index: int | None = None  # run slot in paragraph (None = paragraph-level segment)
    run_group_size: int = 1  # consecutive same-format runs merged into this segment

    @classmethod
    def from_text(
        cls,
        source_text: str,
        structural_position: str,
        seq_in_job: int,
        **kwargs: object,
    ) -> "Segment":
        """Factory: compute SHA ID from text + position, then construct Segment."""
        return cls(
            id=make_segment_id(source_text, structural_position),
            seq_in_job=seq_in_job,
            source_text=source_text,
            structural_position=structural_position,
            **kwargs,
        )
