"""
SmartArt detection helper for PPTX pipeline.

PPTX-02: SmartArt shapes MUST be detected and flagged — not silently skipped.
Detection order: primary (MSO_SHAPE_TYPE.IGX_GRAPHIC enum) then fallback (XML URI).
"""
from __future__ import annotations

SMARTART_URI = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
_DML_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def is_smartart(shape) -> bool:  # type: ignore[type-arg]
    """
    Return True if shape is a SmartArt graphic.

    Primary check: MSO_SHAPE_TYPE.IGX_GRAPHIC — the definitive python-pptx enum value
    for SmartArt. [VERIFIED: Context7 /scanny/python-pptx MSO_SHAPE_TYPE docs]

    Fallback: XML graphicData URI contains diagram namespace — catches malformed/unlabeled
    SmartArt in edge-case PPTX files.

    Defensive: any lxml exception returns False (never crash the extraction pipeline).
    """
    from pptx.enum.shapes import MSO_SHAPE_TYPE  # noqa: PLC0415

    # Primary: enum check — most reliable
    try:
        if shape.shape_type == MSO_SHAPE_TYPE.IGX_GRAPHIC:
            return True
    except Exception:  # noqa: BLE001
        pass

    # Fallback: XML inspection for malformed/edge-case SmartArt
    try:
        graphic_data = shape.element.findall(
            f".//{{{_DML_NS}}}graphicData"
        )
        return any(gd.get("uri") == SMARTART_URI for gd in graphic_data)
    except Exception:  # noqa: BLE001
        return False


def extract_smartart_text(shape) -> str:  # type: ignore[type-arg]
    """
    Best-effort text extraction from SmartArt XML.

    SmartArt nodes contain text in //a:t elements (DML main namespace).
    Returns space-joined text or empty string if none found.
    """
    try:
        ns = {"a": _DML_NS}
        texts = shape.element.findall(".//a:t", ns)
        return " ".join(t.text for t in texts if t.text and t.text.strip())
    except Exception:  # noqa: BLE001
        return ""
