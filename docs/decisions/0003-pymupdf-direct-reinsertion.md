# ADR-0003: PyMuPDF redact-and-reinsert for native PDF translation

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

Native (text-based) PDFs need translated copies that preserve layout.
Two broad strategies:

1. **Direct manipulation** — modify the PDF in place: remove the source
   text and insert translated text at the same coordinates.
2. **Round-trip** — convert PDF → DOCX, translate, convert back.

The hero quality bar is "near-original layout fidelity" for the demo,
on Vietnamese / English / Japanese / Chinese documents.

## Decision

Use **PyMuPDF 1.26.x** with the **redact-and-reinsert** pattern as the
primary native-PDF pipeline. `pdf2docx` remains available as a fallback
for column-heavy layouts where direct reinsertion struggles.

## Alternatives considered

- **`pdf2docx` round-trip** — abandoned by Artifex, community-maintained;
  two conversion steps each lose fidelity; LibreOffice-inherited fonts
  break for CJK + Vietnamese.
- **`pdfplumber`** — extraction only, no write API. Disqualified.
- **`pypdfium2`** — fast extraction, no write API. Same problem.
- **Headless LibreOffice convert** — adds binary dependency, single-
  threaded, slow on large jobs.

## Consequences

- ✅ Direct manipulation = highest achievable layout fidelity.
- ✅ PyMuPDF is well-maintained, fast (C++ core), and has rich
  geometry/text APIs.
- ⚠️ Original embedded fonts are not legally re-usable for substitution
  — bundle Noto fonts ([ADR-0010](0010-bundled-noto-fonts.md)).
- ⚠️ `page.insert_textbox()` returns negative if text overflows the rect
  — must detect and either shrink font or flag for review.
- ⚠️ Multi-column reading-order requires `sort=True` in `get_text()`.
- ⚠️ Right-to-left scripts need `insert_htmlbox()`; LTR (VN, EN, JA, ZH)
  uses `insert_textbox()`.

## References

- `CLAUDE.md` → *4. Native PDF Translation*
- `backend/src/app/pipeline/pdf/{extractor,reassembler,columns,fonts}.py`
- PyMuPDF docs: https://pymupdf.readthedocs.io/
