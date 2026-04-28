---
phase: 04
slug: scanned-pdf-ocr
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (Phase 1 stack) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` (existing) |
| **Quick run command** | `cd backend && uv run pytest -m unit -x` |
| **Full suite command** | `cd backend && uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80` |
| **Integration suite** | `cd backend && uv run pytest -m integration` (real PaddleOCR + DashScope; gated separately) |
| **Estimated runtime (unit)** | ~30 seconds |
| **Estimated runtime (integration)** | ~3–5 minutes (real PaddleOCR on 4 fixtures) |

Frontend: `cd frontend && npm test -- --run` (vitest, existing).

---

## Sampling Rate

- **After every task commit:** `cd backend && uv run pytest -m unit -x` (quick unit pass on touched modules)
- **After every plan wave:** `cd backend && uv run pytest --cov=src --cov-fail-under=80` (full unit + coverage)
- **Before `/gsd-verify-work`:** Full unit suite + integration suite (real PaddleOCR end-to-end on 4 demo fixtures) both green
- **Frontend after every UI task commit:** `cd frontend && npm test -- --run -t SegmentRow` or relevant component
- **Max feedback latency:** 30 seconds (unit pass) — keeps TDD inner loop under 1 minute total

---

## Per-Task Verification Map

> Filled by planner during PLAN.md task creation. Each task gets one row. Test_Type: unit (mocked PaddleOCR) | integration (real PaddleOCR) | manual (visual fidelity, demo-day smoke).

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | INFRA / Wave 0 | — | N/A | unit | `cd backend && uv run pytest tests/pipeline/test_scanned_pdf_extractor.py -x` | ❌ W0 | ⬜ pending |

*(Planner fills the remaining rows per plan. Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky)*

---

## Wave 0 Requirements

- [ ] `backend/tests/pipeline/test_scanned_pdf_extractor.py` — RED tests for OCR-01 (PP-StructureV3 wrapper, mocked Paddle output → Segment list with `kind=ocr_text`, confidence, region_bbox normalized [0,1], region_label)
- [ ] `backend/tests/pipeline/test_scanned_pdf_reassembler.py` — RED tests for OCR-03 compose stage (fpdf2 double-wide page, region-positioned multi_cell, three outputs)
- [ ] `backend/tests/pipeline/test_scanned_pdf_detection.py` — RED tests for D-04-17 text-density heuristic
- [ ] `backend/tests/pipeline/test_segment_to_md.py` — RED tests for D-04-33 Segment→Markdown helper
- [ ] `backend/tests/workers/test_translate_worker_scanned.py` — RED tests for `match job.input_format → case "scanned_pdf"` dispatch + 3-stage progression + per-stage retry budgets
- [ ] `backend/tests/api/test_segments_edited_source.py` — RED tests for PATCH `/segments/{id}` accepting `edited_source_text`
- [ ] `backend/tests/db/test_migration_0006_scanned_pdf.py` — RED test for Alembic migration 0006 (column adds + enum extensions)
- [ ] `backend/tests/conftest.py` — extend with `mocked_paddle_ocr` fixture (canned `parsing_res_list` output) + `scanned_pdf_fixture` helpers
- [ ] `backend/tests/fixtures/scanned/` — 4 fixture PDFs sourced (D-04-21): VN typed, JA typed, EN typed, bad-quality scan (synthetic via PyMuPDF rotate+downsample)
- [ ] `frontend/src/components/__tests__/SegmentRow.ocr.test.tsx` — RED tests for D-04-11/12/13 (click-to-expand image preview, double-click source edit, confidence chip)
- [ ] `frontend/src/components/__tests__/PageReviewBanner.test.tsx` — RED tests for D-04-14 (top-of-page banner with click-to-jump)
- [ ] `backend/pyproject.toml` updates — add `paddleocr>=3.5,<4`, `paddlepaddle==3.0.0` (CPU, from Alibaba index), `fpdf2>=2.8,<3`
- [ ] `backend/Dockerfile` — model-bake RUN layer (pre-warm PP-StructureV3); copy `backend/fonts/Noto*` into image
- [ ] `backend/fonts/` — bundle `NotoSans-Regular.ttf` + `NotoSansCJK-Regular.ttc`

*Wave 0 must complete before any GREEN implementation begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bilingual PDF visual fidelity (left=image, right=translated text) | OCR-03 | Pixel diff on rendered output not deterministic with fpdf2 + Noto fallback fonts | Run end-to-end on `vn-typed.pdf`; open `output.pdf`; verify left side = source page image, right side = translated VN→EN text in correct regions, font legible |
| CJK glyph rendering on translated DOCX | OCR-03 / LANG-02 | DOCX rendering depends on Word/LibreOffice version; visual confirmation only | Run on `ja-typed.pdf`; open `output.docx` in LibreOffice; verify Japanese characters render correctly via Noto CJK |
| Confidence chip color-coding visual hierarchy | D-04-13 | Color perception + paper-skill aesthetic = subjective | Open job review page in browser; verify green ≥70%, amber 50–70%, red <50% chips render and read clearly against paper-skill background |
| Click-to-expand image preview UX | D-04-11 | Expand animation + image clip rendering is visual | Click row, then press 'i'; verify image crop appears above source/target cells, segment row height adjusts cleanly without table jump |
| Page-level banner click-to-jump | D-04-14 | Scroll-to-segment animation is visual | Click page number in banner; verify viewport scrolls to first segment of that page; verify keyboard nav 'n' continues to next flagged segment |
| Demo-day smoke: 4 fixtures end-to-end | OCR-01..04 + DEMO-02 | Smoke script runs the full pipeline + measures latency on demo machine | `cd backend && uv run python scripts/healthcheck.py` extended with `--scanned-pdf` flag; assert OCR per-page latency < 15 sec, full-job end-to-end < 5 min on 10-page fixtures |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify command or Wave 0 dependency listed
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify (no UI-only chains without component tests)
- [ ] Wave 0 covers all MISSING references (RED tests + fixtures + deps + Dockerfile)
- [ ] No watch-mode flags (`pytest --watch`, `vitest --watch` — banned)
- [ ] Feedback latency < 30s (unit pass on touched module)
- [ ] Integration tests gated behind `@pytest.mark.integration` so unit feedback loop stays fast
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills per-task map

**Approval:** pending
