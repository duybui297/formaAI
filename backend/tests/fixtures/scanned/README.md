# Scanned PDF Test Fixtures (D-04-21)

Four test PDFs for Phase 4 OCR pipeline unit and integration tests:

- `vn-typed.pdf`    — Vietnamese typed-document scan (good quality)
- `ja-typed.pdf`    — Japanese typed-document scan
- `en-typed.pdf`    — English typed-document scan
- `bad-quality.pdf` — Low-DPI/skewed scan (exercises confidence gating + needs_review)

These fixtures must be sourced or generated before running integration tests.
For unit tests, PaddleOCR is mocked (see conftest.py `mock_ppstructurev3` fixture).

Maps to: LANG-02 (multi-lingual coverage) + OCR-02 (confidence gating) + D-04-02/03.

## Generating bad-quality.pdf synthetically (for CI)

```bash
python scripts/generate_bad_quality_fixture.py
```

## Sourcing real scan fixtures

For meaningful integration tests, use real scanned PDFs:
- Vietnamese government form (A4, text-heavy)
- Japanese official document (A4, mixed CJK + tables)
- English typed report (Letter, multi-column)
- Any low-DPI scan (150 DPI or below, or with skew >5°)

Place files directly in this directory before running:
```bash
pytest -m integration tests/pipeline/test_scanned_pdf_extractor.py
```
