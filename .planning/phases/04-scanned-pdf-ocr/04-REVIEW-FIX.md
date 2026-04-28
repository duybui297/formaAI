---
phase: 04-scanned-pdf-ocr
fixed_at: 2026-04-28T15:48:08Z
review_path: .planning/phases/04-scanned-pdf-ocr/04-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 4: Code Review Fix Report

**Fixed at:** 2026-04-28T15:48:08Z
**Source review:** .planning/phases/04-scanned-pdf-ocr/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (1 Critical + 6 Warning; Info excluded per fix_scope)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: Frontend artifact download URL does not match backend endpoint path

**Files modified:** `frontend/src/app/jobs/[id]/review/page.tsx`
**Commit:** `3b65ab0`
**Applied fix:** Changed `handleDownload` URL from `/api/jobs/${jobId}/download?artifact=...` to `/api/jobs/${jobId}/artifacts?artifact=...` to match the backend `GET /jobs/{job_id}/artifacts` endpoint registered in jobs.py line 91.

### WR-01: Segment translated_text UPDATE in worker missing job_id in WHERE clause

**Files modified:** `backend/src/app/workers/translate_worker.py`
**Commit:** `ff78af5`
**Applied fix:** Added `SegmentORM.job_id == job_id` to the WHERE clause of the `sa_update(SegmentORM)` call that persists `translated_text`, forming the full compound-PK guard `(job_id, id)` and preventing cross-job translated_text corruption on hash collision.

### WR-02: low_confidence_pages not persisted — review banner breaks on page reload

**Files modified:** `backend/src/app/db/models.py`, `backend/src/app/api/routes/jobs.py`, `backend/src/app/workers/translate_worker.py`, `backend/src/app/db/migrations/versions/0007_job_low_confidence_pages.py`
**Commit:** `42bf649`
**Applied fix:** Three-part fix: (1) added `low_confidence_pages: Mapped[list | None]` JSON column to the `Job` ORM model; (2) assigned `job.low_confidence_pages = _low_conf_pages` in the worker before the `needs_review` status transition; (3) included `"low_confidence_pages": job.low_confidence_pages` in `_job_to_dict` so it is returned by `GET /jobs/{id}`. Added migration `0007_job_low_confidence_pages.py` with `down_revision = "0006_phase4_ocr"`.

### WR-03: submitWithAction stale closure — isScannedOverride/isScannedDetected missing from deps

**Files modified:** `frontend/src/components/UploadForm.tsx`
**Commit:** `fc0d3b2`
**Applied fix:** Added `isScannedOverride` and `isScannedDetected` to the `useCallback` dependency array for `submitWithAction`, ensuring the callback always closes over the current state values and will not submit a stale `is_scanned_override` value.

### WR-04: FlagType.ocr_page_error defined and wired in UI but never emitted by the worker

**Files modified:** `backend/src/app/workers/translate_worker.py`
**Commit:** `6d9ff1a`
**Applied fix:** Added a loop after the overflow flags block in the `scanned_pdf` match branch that iterates `segments` and appends a `SegmentFlag(flag_type=FlagType.ocr_page_error, severity=FlagSeverity.warn)` for every segment with `kind=="ocr_text"`, `confidence==0.0`, and `source_text=="[OCR failed for this page]"`. These flags are included in the existing `_ocr_db_flags` list and flushed together.

### WR-05: make_segment_flag test fixture missing required segment_job_id field

**Files modified:** `backend/tests/conftest.py`
**Commit:** `9b8fa06`
**Applied fix:** Added `segment_job_id: str` as a required positional parameter to the `_make` inner function, and passed it to `SegmentFlag(segment_job_id=segment_job_id, ...)`. No existing test calls the fixture yet (grep confirmed zero callsites), so no downstream test changes were needed.

### WR-06: objectPosition CSS formula incorrect for image crop preview

**Files modified:** `frontend/src/components/SegmentRow.tsx`
**Commit:** `b1ab348`
**Applied fix:** Replaced the broken `object-none` + `objectPosition` percentage approach with a `relative` wrapper div containing the full-page `<img>` (width 100%, no object-fit manipulation) and an absolutely-positioned overlay `<div>` whose `left`, `top`, `width`, `height` are computed from the normalized `region_bbox` values as percentages. The overlay uses an amber border + semi-transparent fill to highlight the region. This is pixel-accurate for any bbox position without requiring knowledge of the image's intrinsic dimensions.

---

_Fixed: 2026-04-28T15:48:08Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
