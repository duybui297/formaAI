from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.db.models import Segment, SegmentFlag


class SegmentPatchRequest(BaseModel, frozen=True):
    # edited_text=None clears the edit; Field(...) makes it required (not optional)
    edited_text: str | None = Field(default=..., max_length=10_000)
    # Phase 4 (D-04-12): reviewer-corrected OCR source text
    edited_source_text: str | None = Field(default=None, max_length=10_000)


def flag_to_dict(f: "SegmentFlag") -> dict:
    return {
        "id": f.id,
        "segment_id": f.segment_id,
        "flag_type": f.flag_type.value if hasattr(f.flag_type, "value") else f.flag_type,
        "severity": f.severity.value if hasattr(f.severity, "value") else f.severity,
        "details": f.details,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


def segment_to_dict(s: "Segment") -> dict:
    return {
        "id": s.id,
        "seq_in_job": s.seq_in_job,
        "source_text": s.source_text,
        "translated_text": s.translated_text,
        "edited_text": s.edited_text,
        "expansion_ratio": s.expansion_ratio,
        "structural_position": s.structural_position,
        "flags": [flag_to_dict(f) for f in (s.flags or [])],
        # Phase 4 OCR fields (D-04-12, D-04-26)
        "confidence": getattr(s, "confidence", None),
        "region_bbox": getattr(s, "region_bbox", None),
        "region_label": getattr(s, "region_label", None),
        "edited_source_text": getattr(s, "edited_source_text", None),
    }
