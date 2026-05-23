# ADR-0007: Run-level text replacement in python-docx

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

DOCX is the hero format — fidelity bar is "near pixel-perfect". A DOCX
paragraph is composed of *runs*: each run carries its own formatting
(bold, italic, font, color, hyperlinks, tracked changes). Translation
must replace the *text* without destroying the *formatting*.

The naive approach in python-docx is `paragraph.text = "translated"`,
which works textually but destroys all run-level formatting because it
collapses the paragraph to a single run.

## Decision

Translate at the **run level**: overwrite `run.text` with translated
content on the first run of a paragraph, then blank the text of the
remaining runs in that paragraph. Preserve all run XML siblings
(formatting properties) untouched.

## Alternatives considered

- **`paragraph.text = value`** — destroys all run-level formatting.
  Strictly forbidden in this codebase.
- **Per-run translation** — translate each run's text independently.
  Bad: the translation model loses sentence context; mid-word
  formatting splits become broken in the translation.
- **Reconstruct paragraph from translated string + format spans** —
  much more complex; only worth it for paragraphs with mid-word
  formatting boundaries (rare).

## Consequences

- ✅ Bold, italic, font, color, hyperlink, comment anchors all preserved
  bit-for-bit.
- ✅ Tracked changes survive intact for paragraphs with no edits.
- ⚠️ Mid-word formatting boundaries (rare) collapse to the first run's
  formatting — acceptable trade-off for PoC.
- ⚠️ Empty runs leave invisible XML siblings; tested to render fine in
  Word and LibreOffice.

## References

- `CLAUDE.md` → *What NOT to Use* table (entry on `paragraph.text`)
- `backend/src/app/pipeline/docx/reassembler.py`
- python-docx run model: https://python-docx.readthedocs.io/
