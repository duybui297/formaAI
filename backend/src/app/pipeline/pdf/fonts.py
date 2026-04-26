"""
Noto font discovery and CSS builder for PDF text insertion via insert_htmlbox.

D-03-04: Bundled Noto fonts for all output — Noto Sans (latin/VN) + Noto Sans CJK (JA/ZH/KO).
Original PDF fonts are DRM-embedded/subsetted — cannot legally be reused.

[ASSUMED: A3 — Noto font files are installed via apt packages:
  fonts-noto:       /usr/share/fonts/truetype/noto/ (Latin, VN)
  fonts-noto-cjk:   /usr/share/fonts/opentype/noto/  (CJK)
Verify with: docker run --rm <image> fc-list | grep Noto]
[VERIFIED: wave-0-noto-paths.txt confirms CJK fonts are in opentype/noto/ on Docker image]
"""
from __future__ import annotations

import os

import pymupdf

# Font directories as confirmed by wave-0-noto-paths.txt
_NOTO_TRUETYPE_DIR = "/usr/share/fonts/truetype/noto"
_NOTO_OPENTYPE_DIR = "/usr/share/fonts/opentype/noto"

# Known Noto font filenames on Debian fonts-noto + fonts-noto-cjk packages.
# wave-0-noto-paths.txt confirms:
#   NotoSans-Regular.ttf, NotoSans-Bold.ttf, NotoSans-Italic.ttf  → truetype/noto
#   NotoSansCJK-Regular.ttc                                         → opentype/noto
_NOTO_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "regular": [
        (_NOTO_TRUETYPE_DIR, "NotoSans-Regular.ttf"),
        (_NOTO_TRUETYPE_DIR, "NotoSans[wdth,wght].ttf"),
    ],
    "bold": [
        (_NOTO_TRUETYPE_DIR, "NotoSans-Bold.ttf"),
        (_NOTO_TRUETYPE_DIR, "NotoSans[wdth,wght].ttf"),
    ],
    "italic": [
        (_NOTO_TRUETYPE_DIR, "NotoSans-Italic.ttf"),
        (_NOTO_TRUETYPE_DIR, "NotoSans[wdth,wght].ttf"),
    ],
    "cjk": [
        (_NOTO_OPENTYPE_DIR, "NotoSansCJK-Regular.ttc"),
        (_NOTO_TRUETYPE_DIR, "NotoSansCJK-Regular.ttc"),
        (_NOTO_OPENTYPE_DIR, "NotoSansCJKsc-Regular.otf"),
        (_NOTO_OPENTYPE_DIR, "NotoSansCJKjp-Regular.otf"),
    ],
}


def _find_font(candidates: list[tuple[str, str]]) -> tuple[str, str] | None:
    """Return the first (dir, filename) candidate that exists on disk."""
    for font_dir, fname in candidates:
        if os.path.exists(os.path.join(font_dir, fname)):
            return font_dir, fname
    return None


def build_noto_archive_and_css() -> tuple[pymupdf.Archive, str]:
    """
    Build PyMuPDF Archive pointing to Noto font directories and @font-face CSS string.

    Call once per reassembly job and pass arch+css into every insert_htmlbox call.
    HarfBuzz shaping (built into PyMuPDF) handles Vietnamese diacritics and CJK
    automatically when Noto fonts are registered.

    Returns
    -------
    arch : pymupdf.Archive — font file discovery context (may span multiple directories)
    css  : str — @font-face CSS to pass as css= parameter to insert_htmlbox
    """
    # Build archive covering both truetype and opentype directories
    arch = pymupdf.Archive()
    for font_dir in [_NOTO_TRUETYPE_DIR, _NOTO_OPENTYPE_DIR]:
        if os.path.isdir(font_dir):
            arch.add(font_dir)

    # Find best available font for each style
    regular_result = _find_font(_NOTO_CANDIDATES["regular"])
    bold_result = _find_font(_NOTO_CANDIDATES["bold"])
    italic_result = _find_font(_NOTO_CANDIDATES["italic"])
    cjk_result = _find_font(_NOTO_CANDIDATES["cjk"])

    # Use filename if found; fallback names will be present in the container
    regular = regular_result[1] if regular_result else "NotoSans-Regular.ttf"
    bold = bold_result[1] if bold_result else "NotoSans-Bold.ttf"
    italic = italic_result[1] if italic_result else "NotoSans-Italic.ttf"
    cjk = cjk_result[1] if cjk_result else "NotoSansCJK-Regular.ttc"

    css = f"""
    @font-face {{
        font-family: noto;
        src: url({regular});
    }}
    @font-face {{
        font-family: noto;
        src: url({bold});
        font-weight: bold;
    }}
    @font-face {{
        font-family: noto;
        src: url({italic});
        font-style: italic;
    }}
    @font-face {{
        font-family: noto-cjk;
        src: url({cjk});
    }}
    * {{
        font-family: noto, noto-cjk, sans-serif;
        font-size: 10pt;
    }}
    h1 {{ font-size: 1.6em; font-weight: bold; margin-bottom: 0.2em; }}
    h2 {{ font-size: 1.3em; font-weight: bold; margin-bottom: 0.1em; }}
    """
    return arch, css
