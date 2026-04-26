"""
PDF fonts CSS contract tests.

Locks in the CSS rules emitted by build_noto_archive_and_css() so the layout
fix from the post-Phase-3.1 hotfix does not silently regress.
"""
from __future__ import annotations


def test_css_does_not_force_global_font_size():
    """Forcing `* { font-size: 10pt }` flattens body sizes across heterogeneous
    PDFs and causes overlap. The reassembler now wraps each block in a
    per-block <div style="font-size:Npt"> instead — the global * rule must
    only set font-family, not font-size."""
    from app.pipeline.pdf.fonts import build_noto_archive_and_css

    _arch, css = build_noto_archive_and_css()
    assert "font-size: 10pt" not in css, (
        "CSS must not pin a global 10pt size — per-block size is set by reassembler"
    )


def test_css_declares_bold_and_italic_rules():
    """PyMuPDF's htmlbox renderer needs explicit b/i rules to map <b>/<i>
    tags to bold/italic style — without them, semantic tags render as plain
    text in the output PDF."""
    from app.pipeline.pdf.fonts import build_noto_archive_and_css

    _arch, css = build_noto_archive_and_css()
    assert "font-weight: bold" in css, "CSS must declare bold weight rule for <b>"
    assert "font-style: italic" in css, "CSS must declare italic style rule for <i>"


def test_css_keeps_heading_em_sizing():
    """Headings keep em-relative sizing so they scale with each block's
    body font size (set on the wrapper div)."""
    from app.pipeline.pdf.fonts import build_noto_archive_and_css

    _arch, css = build_noto_archive_and_css()
    assert "h1" in css and "1.6em" in css, "h1 must keep 1.6em scale"
    assert "h2" in css and "1.3em" in css, "h2 must keep 1.3em scale"
