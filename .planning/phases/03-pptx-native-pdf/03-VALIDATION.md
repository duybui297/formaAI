---
phase: 3
slug: pptx-native-pdf
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-25
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `03-RESEARCH.md ## Validation Architecture`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest 8+ + pytest-asyncio |
| **Framework (frontend)** | vitest (existing) |
| **Config file** | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| **Quick run command** | `cd backend && uv run pytest tests/pipeline/ -x -q` |
| **Full suite command** | `cd backend && uv run pytest --cov=src/app --cov-fail-under=80 -q && cd ../frontend && npm run test` |
| **Estimated runtime** | ~30 seconds (pipeline subset); ~90 seconds (full + frontend) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && uv run pytest tests/pipeline/ -x -q`
- **After every plan wave:** Run full suite (backend + frontend)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds for quick run

---

## Per-Task Verification Map

> Tasks numbered abstractly per requirement; planner will assign concrete `{N}-{plan}-{task}` IDs.
> Wave 0 = test scaffolding + dep installs (must precede implementation).

| Req ID | Wave | Behavior | Test Type | Automated Command | File Exists |
|--------|------|----------|-----------|-------------------|-------------|
| (deps) | 0 | `pymupdf>=1.26`, `python-pptx==1.0.2` in pyproject.toml | unit | `cd backend && uv run python -c "import pymupdf, pptx"` | ❌ W0 |
| PPTX-01 | 1 | text box + notes + table + master extracted + reassembled | unit | `pytest tests/pipeline/test_pptx_extractor.py -x` | ❌ W0 |
| PPTX-02 | 1 | SmartArt shapes produce `smartart` flag, write-back skipped | unit | `pytest tests/pipeline/test_pptx_extractor.py::test_smartart_flagged -x` | ❌ W0 |
| PPTX-03 | 1 | overflow flag set when shrink < 0.7; auto-fit applied when ≥ 0.7 | unit | `pytest tests/pipeline/test_pptx_reassembler.py::test_overflow -x` | ❌ W0 |
| PPTX-04 | 1 | nested group walker finds text at all nesting levels | unit | `pytest tests/pipeline/test_pptx_extractor.py::test_group_recursion -x` | ❌ W0 |
| PDF-01 | 1 | PDF parsed; segments have bbox, font, size, source_text | unit | `pytest tests/pipeline/test_pdf_extractor.py -x` | ❌ W0 |
| PDF-02 | 1 | redact-reinsert produces PDF with Noto text + non-text preserved | unit | `pytest tests/pipeline/test_pdf_reassembler.py::test_round_trip -x` | ❌ W0 |
| PDF-03 | 1 | overflow flagged when scale < 0.7 | unit | `pytest tests/pipeline/test_pdf_reassembler.py::test_overflow_flag -x` | ❌ W0 |
| PDF-04 | 1 | 2-col PDF produces 2 column groups in reading order; 3+ → degraded | unit | `pytest tests/pipeline/test_pdf_columns.py -x` | ❌ W0 |
| LAYOUT-02 | 2 | `overflow` SegmentFlag persisted with `(job_id, segment_id)` FK | integration | `pytest tests/pipeline/test_pdf_reassembler.py::test_overflow_db_flag_persisted -x` | ❌ W0 |
| LAYOUT-03 | 2 | `auto_adjusted` metadata in SegmentFlag.details JSON | unit | `pytest tests/pipeline/test_pptx_reassembler.py::test_auto_adjusted -x` | ❌ W0 |
| FE-01 | 2 | `FlagBadge` renders `smartart` (orange) + `multi_column_degraded` (slate) | unit (vitest) | `cd frontend && npm run test -- FlagBadge` | ✅ extend |
| FE-02 | 2 | `formatBreadcrumb()` parses docx/pptx/pdf position formats | unit (vitest) | `cd frontend && npm run test -- formatBreadcrumb` | ❌ W0 |
| FE-03 | 2 | `UploadForm` accepts `.pptx` and `.pdf` extensions | unit (vitest) | `cd frontend && npm run test -- UploadForm` | ✅ extend |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Property Tests (round-trip invariants)

```python
# I1: segment count preserved through translation map (existing CORE-03)
assert len(extracted_segments) == len(translated_map)

# I2: non-text content preserved on PDF round-trip
before_images = sum(1 for b in src_page.get_text("dict")["blocks"] if b["type"] == 1)
after_images  = sum(1 for b in out_page.get_text("dict")["blocks"] if b["type"] == 1)
assert before_images == after_images

# I3: SmartArt segments produce no reassembly write-back
# (write-back skipped for positions whose source is smartart-flagged)

# I4: structural_position uniqueness per job
positions = [s.structural_position for s in segments]
assert len(positions) == len(set(positions))
```

---

## Adversarial Tests

| Scenario | Test | Expected Behavior |
|----------|------|-------------------|
| Malformed PPTX (corrupt XML) | `test_malformed_pptx` | Worker logs error, job → `failed`, no crash |
| Encrypted PDF (password) | `test_encrypted_pdf` | `pymupdf.open()` raises, caught, job → `failed` |
| Empty PPTX (zero slides) | `test_empty_pptx` | Returns `[]` segments, job → `done` empty output |
| PPTX zero-run text frame | `test_zero_run_tf` | Falls back to paragraph-level extraction |
| 3-column PDF | `test_three_col_pdf` | `multi_column_degraded` flag set, flat reading order |
| All-image PDF (no text layer) | `test_image_only_pdf` | Returns `[]` segments, job → `done` (Phase 4 territory) |
| Extreme expansion (>5x) | `test_extreme_expansion` | `overflow` flag, `spare_height < 0` after `insert_htmlbox` |

---

## Observability (post-hoc debugging)

Per-job structured log fields (structlog):

```python
log.info("pptx_extracted", job_id=job_id, slide_count=len(prs.slides),
         segment_count=len(segments), smartart_count=smartart_shapes_found)
log.info("pdf_extracted", job_id=job_id, page_count=len(doc),
         segment_count=len(segments), degraded_pages=degraded_count)
log.info("pdf_block_overflow", job_id=job_id, page=page_num,
         block=block_idx, scale_applied=scale)
```

Metrics worth recording (logs are sufficient for PoC; Prometheus optional):
- segments per format (pptx/pdf/docx) per job
- overflow rate per format
- smartart count per job
- degraded_pages per job

---

## Wave 0 Requirements

- [ ] `backend/pyproject.toml` — add `pymupdf>=1.26,<2`, `python-pptx==1.0.2`
- [ ] `backend/tests/pipeline/test_pptx_extractor.py` — covers PPTX-01..04
- [ ] `backend/tests/pipeline/test_pptx_reassembler.py` — covers PPTX-03, LAYOUT-03
- [ ] `backend/tests/pipeline/test_pdf_extractor.py` — covers PDF-01
- [ ] `backend/tests/pipeline/test_pdf_reassembler.py` — covers PDF-02, PDF-03, LAYOUT-02
- [ ] `backend/tests/pipeline/test_pdf_columns.py` — covers PDF-04
- [ ] `frontend/src/__tests__/formatBreadcrumb.test.ts` — covers D-03-07
- [ ] `frontend/src/__tests__/FlagBadge.test.tsx` — extend with smartart + multi_column_degraded
- [x] Programmatic fixtures via tmp_path_factory in test_pptx_extractor.py, test_pptx_reassembler.py, test_pdf_extractor.py, test_pdf_reassembler.py, test_pdf_columns.py — no binary files committed (per PATTERNS.md DOCX analog)
- [ ] Wave-0 empirical probe: `qwen-mt-turbo` HTML-tag preservation → planned in plan 03-01 Task 4 (wave0_html_probe.py)
- [ ] Wave-0 empirical probe: `fc-list | grep Noto` inside Docker → planned in plan 03-01 Task 3 (wave-0-noto-paths.txt)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual fidelity of round-tripped PPTX in PowerPoint/Keynote | PPTX-01 | Headless renderer can't replicate user perception | Open exported `.pptx` in PowerPoint; visually compare layout, fonts, table formatting |
| Visual fidelity of redact-reinserted PDF | PDF-02 | Pixel-perfect comparison fragile on font substitution | Open exported `.pdf` in Acrobat; verify CJK glyphs render, columns flow, non-text artifacts intact |
| Breadcrumb badge appearance in review UI | D-03-07 | UX/typography judgement | Run frontend, upload PPTX or PDF, open review page, confirm breadcrumb above source text in `font-mono text-xs text-slate-400` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30 seconds (quick run)
- [x] `nyquist_compliant: true` set in frontmatter (probe tasks added to plan 03-01)

**Approval:** pending
