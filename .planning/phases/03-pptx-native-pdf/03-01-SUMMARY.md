---
phase: "03-pptx-native-pdf"
plan: "01"
subsystem: "backend/pipeline"
tags: ["deps", "db", "migration", "probe"]
dependency_graph:
  requires: []
  provides:
    - "pymupdf>=1.26,<2 importable in backend venv"
    - "python-pptx==1.0.2 importable in backend venv"
    - "FlagType.smartart enum value in models.py"
    - "FlagType.multi_column_degraded enum value in models.py"
    - "migration 0004_phase3 in Alembic chain"
    - "wave-0-noto-paths.txt — 298 Noto font entries for plan 03-04"
    - "wave-0-html-probe.txt — PIPELINE_PRESERVED verdict for plan 03-04"
  affects:
    - "backend/src/app/db/models.py (FlagType enum)"
    - "plans 03-02..03-06 consume pymupdf + python-pptx"
    - "plan 03-04 reads wave-0-noto-paths.txt + wave-0-html-probe.txt"
tech_stack:
  added:
    - "pymupdf 1.27.2.3 (PDF extraction, redact-reinsert, insert_htmlbox)"
    - "python-pptx 1.0.2 (PPTX shape/table/notes traversal)"
    - "pillow 12.2.0 (transitive dep of python-pptx)"
    - "xlsxwriter 3.2.9 (transitive dep of python-pptx)"
  patterns:
    - "Alembic no-DDL migration pattern (native_enum=False VARCHAR — extend enum with pass-through migration)"
key_files:
  created:
    - "backend/src/app/db/migrations/versions/0004_flagtype_phase3.py"
    - "backend/scripts/wave0_html_probe.py"
    - ".planning/phases/03-pptx-native-pdf/wave-0-noto-paths.txt"
    - ".planning/phases/03-pptx-native-pdf/wave-0-html-probe.txt"
  modified:
    - "backend/pyproject.toml (added pymupdf + python-pptx deps)"
    - "backend/uv.lock (resolved by uv sync)"
    - "backend/src/app/db/models.py (FlagType extended with smartart + multi_column_degraded)"
decisions:
  - "pymupdf pinned >=1.26,<2 (range) to receive security patches; python-pptx pinned ==1.0.2 exactly (1.0.x has breaking API vs 0.6.x)"
  - "Migration 0004 is a no-DDL documentation migration — flag_type VARCHAR column (native_enum=False) accepts new string values without ALTER TYPE"
  - "HTML probe result: PIPELINE_PRESERVED — qwen-mt-turbo preserves <b>/<i> tags through translate_batch (with masking). Plan 03-04 can feed raw HTML to translate_batch directly, no placeholder wrapping needed"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-26"
  tasks_completed: 4
  tasks_total: 4
  files_created: 4
  files_modified: 3
---

# Phase 03 Plan 01: Backend Deps + FlagType Extension + Wave-0 Probes Summary

**One-liner:** pymupdf 1.27 + python-pptx 1.0.2 added to backend; FlagType enum extended with smartart/multi_column_degraded; Noto font paths and HTML-tag survival verdict collected for downstream plans.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add pymupdf and python-pptx to pyproject.toml | 2880966 | backend/pyproject.toml, uv.lock |
| 2 | Extend FlagType enum + create Alembic migration 0004 | c374697 | models.py, 0004_flagtype_phase3.py |
| 3 | Font discovery probe — Noto paths in Docker | b164467 | wave-0-noto-paths.txt |
| 4 | HTML-tag survival probe — qwen-mt-turbo with HTML payload | 8bd2ff4 | wave0_html_probe.py, wave-0-html-probe.txt |

## Probe Results

### Noto Font Paths (wave-0-noto-paths.txt)

298 Noto font entries found in the Docker `api` container. Key paths confirmed:

- `/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc` — Japanese, Chinese (SC/TC/HK), Korean
- `/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc` — CJK serif variant
- `/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf` — Latin/Vietnamese sans-serif bold
- `/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf` — Latin/Vietnamese serif

Plan 03-04 reads this file to hardcode `NOTO_CANDIDATES` in `backend/src/app/pipeline/pdf/fonts.py`.

### HTML Tag Survival (wave-0-html-probe.txt)

Input: `'<b>hello</b> world'` (en → vi)

| Path | Output | Verdict |
|------|--------|---------|
| Pipeline (translate_batch + masking) | `'<b>xin chào</b> thế giới'` | PIPELINE_PRESERVED |
| Raw model (direct API, no masking) | `'<b>hello</b> world'` | RAW_PRESERVED |

**Decision for plan 03-04:** `spans_to_html()` can feed raw HTML directly to `translate_batch` — no placeholder wrapping of HTML tags needed.

Note: the raw path returned the untranslated Vietnamese (model applied translation instruction literally rather than via the `translation_options` parameter), but HTML tags were preserved as expected.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new network endpoints, auth paths, or file access patterns introduced. The probe script reads `.env` from the project root at `Path(__file__).parent.parent.parent / ".env"` — this is a dev-only script, not deployed code.

## Self-Check: PASSED

- `backend/pyproject.toml` contains `pymupdf>=1.26,<2` and `python-pptx==1.0.2` ✓
- `backend/src/app/db/models.py` contains `smartart = "smartart"` and `multi_column_degraded = "multi_column_degraded"` ✓
- `backend/src/app/db/migrations/versions/0004_flagtype_phase3.py` exists with `revision: str = "0004_phase3"` and `down_revision: Union[str, None] = "0003_segment_pk_run"` ✓
- `backend/scripts/wave0_html_probe.py` exists ✓
- `.planning/phases/03-pptx-native-pdf/wave-0-noto-paths.txt` exists with 298 lines ✓
- `.planning/phases/03-pptx-native-pdf/wave-0-html-probe.txt` contains `pipeline_verdict: PIPELINE_PRESERVED` ✓
- Commits: 2880966, c374697, b164467, 8bd2ff4 — all in git log ✓
