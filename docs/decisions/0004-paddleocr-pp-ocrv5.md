# ADR-0004: PaddleOCR PP-OCRv5 for scanned PDF OCR

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

Scanned PDFs require OCR before translation. Target languages: Vietnamese,
Japanese, Chinese (Simplified + Traditional), English — frequently mixed
in a single doc. Need layout-aware OCR (reading order, tables, figures)
because dumb line-by-line OCR destroys document structure.

Quality of Japanese and Vietnamese OCR varies wildly between engines.

## Decision

Use **PaddleOCR 3.x (PP-OCRv5)** as the default OCR engine, with the
**PP-StructureV3** pipeline for layout analysis. Azure Document
Intelligence is a documented cloud fallback if PaddleOCR proves
unreliable on a real customer doc.

## Alternatives considered

- **Tesseract 5 + pytesseract** — Japanese model is materially weaker
  than PaddleOCR's; no native layout analysis; would need to bolt on a
  separate layout model.
- **Azure Document Intelligence** — equal-or-better quality on real-world
  docs, but $1.50/1000 pages adds per-job cost and routes data through
  Azure. Acceptable for AICore PoC but not the default.
- **Google Document AI** — same cost class as Azure, same data-residency
  question, no clear quality advantage.
- **Alibaba OCR (DashScope)** — CN-biased; ecosystem bonus but unproven
  on VN/JA.

## Consequences

- ✅ Self-hostable — zero per-page cost.
- ✅ Single model covers 106 languages — VN, JA, ZH, EN all in `ch`
  multilingual pack.
- ✅ PP-OCRv5 (2025) is +13 percentage points over PP-OCRv4 on complex
  doc benchmarks; +30% on multilingual recognition.
- ⚠️ Adds ~700MB-1GB to the Docker image (models baked at build time —
  see backend `Dockerfile` line 44).
- ⚠️ `paddlepaddle` must be installed from Alibaba's index — standard
  PyPI version is a stub.
- ⚠️ CPU inference; GPU helps on long docs but not required for PoC.

## References

- `CLAUDE.md` → *5. OCR for Scanned PDFs*
- `backend/src/app/pipeline/scanned_pdf/{extractor,composer,detector}.py`
- `backend/Dockerfile` lines 27–44 (paddlepaddle + model bake)
- PP-OCRv5 paper: https://arxiv.org/abs/2507.05595
