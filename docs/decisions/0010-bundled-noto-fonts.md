# ADR-0010: Bundle Noto fonts for CJK + Vietnamese PDF insertion

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

After redact-and-reinsert ([ADR-0003](0003-pymupdf-direct-reinsertion.md)),
translated text needs a font to render in. Two problems:

1. The original embedded fonts in the source PDF are typically
   DRM-protected and legally not redistributable for substitution.
2. The default PDF builtin fonts (Helvetica, Times, Courier) have **no
   CJK or Vietnamese glyph coverage** — render as missing-glyph boxes.

Vietnamese tone marks (combining diacritics) and CJK ideographs both
require explicit font coverage; partial coverage produces silently
broken docs.

## Decision

**Bundle Noto fonts in the backend Docker image** and register them
with PyMuPDF at text-insertion time:

| Font | Coverage | Size |
|---|---|---|
| `NotoSansCJK-Regular.ttc` | JA, ZH-SC, ZH-TC, KO | ~48MB |
| `NotoSans-Regular.ttf` | VN + Latin | ~500KB |
| `NotoSerif-Regular.ttf` | Serif body text | ~500KB |

Install via `apt-get install fonts-noto-cjk fonts-noto` in the
Dockerfile; additionally bundle TTFs at `backend/fonts/` for explicit
path-based registration (used by fpdf2 in Phase 4 OCR composer).

## Alternatives considered

- **Embedding original PDF fonts** — legally not allowed; DRM tooling
  varies by font foundry; would couple us to per-document font
  licenses.
- **Per-language font picking** — adds complexity; Noto covers every
  target language in one font family.
- **System default fonts only** — Helvetica/Times have no CJK/VN
  coverage; produces unreadable output.
- **ReportLab for CJK PDF generation** — poor CJK support; requires
  manual glyph registration.

## Consequences

- ✅ Universal coverage for all target languages in one font family.
- ✅ Apache 2.0 license — free to bundle and redistribute.
- ✅ Visually consistent across JA/ZH/VN/EN/KO outputs.
- ⚠️ Docker image is ~48MB larger because of CJK font bundle.
  Acceptable — image is already large from PaddleOCR.
- ⚠️ Font metrics differ from the original PDF font — line heights and
  character widths will not match exactly. Unavoidable without the
  original font.
- ⚠️ For scanned PDF output, the original font is unknowable anyway —
  Noto Sans is a clean default.

## References

- `CLAUDE.md` → *10. Font Handling for CJK + Vietnamese PDFs*
- `backend/Dockerfile` lines 5–11 (apt fonts) and line 38 (TTF bundle)
- `backend/src/app/pipeline/pdf/fonts.py`
