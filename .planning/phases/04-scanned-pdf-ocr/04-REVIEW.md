---
phase: 04-scanned-pdf-ocr
reviewed: 2026-04-28T10:00:00Z
depth: standard
files_reviewed: 42
files_reviewed_list:
  - backend/Dockerfile
  - backend/fonts/README.md
  - backend/pyproject.toml
  - backend/src/app/api/routes/jobs.py
  - backend/src/app/api/routes/segments.py
  - backend/src/app/api/routes/upload.py
  - backend/src/app/core/config.py
  - backend/src/app/db/migrations/versions/0006_phase4_ocr.py
  - backend/src/app/db/models.py
  - backend/src/app/pipeline/scanned_pdf/__init__.py
  - backend/src/app/pipeline/scanned_pdf/composer.py
  - backend/src/app/pipeline/scanned_pdf/detector.py
  - backend/src/app/pipeline/scanned_pdf/extractor.py
  - backend/src/app/pipeline/scanned_pdf/segment_to_md.py
  - backend/src/app/pipeline/segment.py
  - backend/src/app/workers/translate_worker.py
  - backend/tests/api/test_jobs_download.py
  - backend/tests/api/test_segments_edited_source.py
  - backend/tests/conftest.py
  - backend/tests/db/test_migration_0006.py
  - backend/tests/fixtures/scanned/README.md
  - backend/tests/pipeline/test_scanned_pdf_composer.py
  - backend/tests/pipeline/test_scanned_pdf_detector.py
  - backend/tests/pipeline/test_scanned_pdf_extractor.py
  - backend/tests/pipeline/test_scanned_pdf_roundtrip.py
  - backend/tests/pipeline/test_segment_to_md.py
  - backend/tests/workers/test_translate_worker_scanned.py
  - frontend/src/__tests__/phase4-flagbadge.test.tsx
  - frontend/src/__tests__/phase4-types.test.ts
  - frontend/src/app/jobs/[id]/review/page.tsx
  - frontend/src/components/FlagBadge.tsx
  - frontend/src/components/KeyboardHelpPanel.tsx
  - frontend/src/components/ReviewFilterBar.tsx
  - frontend/src/components/SegmentRow.tsx
  - frontend/src/components/UploadForm.tsx
  - frontend/src/components/ui/dropdown-menu.tsx
  - frontend/src/hooks/useReviewKeyboard.ts
  - frontend/src/hooks/useSegments.ts
  - frontend/src/lib/review-types.ts
  - frontend/src/lib/types.ts
findings:
  critical: 1
  warning: 6
  info: 2
  total: 9
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-04-28T10:00:00Z
**Depth:** standard
**Files Reviewed:** 42
**Status:** issues_found

## Summary

Phase 4 introduces the scanned-PDF OCR pipeline (PaddleOCR PP-StructureV3 → translate → fpdf2 bilingual compose), Phase 4 OCR columns on the `segments` table, a new `artifacts` download endpoint for three output artifacts, and frontend extensions (confidence chip, image crop preview, source cell edit, download dropdown). The pipeline architecture is sound: `asyncio.to_thread` wraps the sync PaddleOCR call correctly, per-page error isolation is solid, bbox normalization is clamped, and the migration handles PostgreSQL's `ALTER TYPE ... ADD VALUE IF NOT EXISTS` outside a transaction correctly.

One critical bug makes all Phase 4 artifact downloads silently broken in the browser: the frontend download URL does not match the backend endpoint path. Six warnings cover a missing compound-PK in a segment UPDATE (can corrupt cross-job data on hash collision), a stale closure in the upload form, a feature (`low_confidence_pages` banner) that silently breaks after page reload, an entire flag type (`ocr_page_error`) that is never emitted despite being fully wired up, a broken image crop CSS formula, and a test fixture that will fail with a NOT NULL violation on the FK column. Two info items cover the wrong text field used for DOCX export and a type-duplication debt.

---

## Critical Issues

### CR-01: Frontend artifact download URL does not match backend endpoint path

**File:** `frontend/src/app/jobs/[id]/review/page.tsx:98`

**Issue:** `handleDownload` constructs the URL as `/api/jobs/${jobId}/download?artifact=${artifact}`, but the backend artifact endpoint is registered at `GET /jobs/{job_id}/artifacts?artifact=...` (jobs.py line 91). The `/download` route (jobs.py line 176) is the legacy endpoint that only reads `job.output_path` from the DB and returns it with a hardcoded DOCX MIME type — it does not handle the `artifact` query parameter at all. Every click on "Bilingual PDF", "Translated PDF", and "Translated DOCX" in the review page will silently hit the wrong route.

**Fix:**
```tsx
// frontend/src/app/jobs/[id]/review/page.tsx
const handleDownload = (artifact: "bilingual_pdf" | "translated_pdf" | "translated_docx") => {
  setDownloading(true);
  const a = document.createElement("a");
  // Fix: /artifacts not /download
  a.href = `/api/jobs/${jobId}/artifacts?artifact=${artifact}`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => setDownloading(false), 1500);
};
```

---

## Warnings

### WR-01: Segment translated_text UPDATE in worker missing `job_id` in WHERE clause

**File:** `backend/src/app/workers/translate_worker.py:559-563`

**Issue:** The UPDATE that persists translated text after batching uses only `SegmentORM.id == seg.id` in the WHERE clause:

```python
sa_update(SegmentORM)
    .where(SegmentORM.id == seg.id)
    .values(translated_text=translated)
```

`Segment.id` is a 16-char hex SHA-256 of `source_text + structural_position` (segment.py:21-22). Two different jobs that share a segment with identical source text and identical structural position will produce the same `id`. When job B's worker runs, this UPDATE will overwrite job A's `translated_text` on that shared segment — silent data corruption.

The compound primary key `(id, job_id)` exists precisely to prevent this, and all other locations in the codebase use it correctly (segments.py:154, regenerate endpoint). This one UPDATE is missing the guard.

**Fix:**
```python
await session.execute(
    sa_update(SegmentORM)
    .where(SegmentORM.job_id == job_id, SegmentORM.id == seg.id)
    .values(translated_text=translated)
)
```

### WR-02: `low_confidence_pages` not persisted — review banner breaks on page reload

**File:** `backend/src/app/api/routes/jobs.py:31-53` and `frontend/src/app/jobs/[id]/review/page.tsx:43-51`

**Issue:** The frontend review page reads `job.low_confidence_pages` from the TanStack Query cache for `["job", jobId]`, which fetches `GET /jobs/{job_id}`. The `_job_to_dict` serializer never includes `low_confidence_pages` — the field does not exist on the `Job` ORM model. `low_confidence_pages` is only emitted in the Redis SSE payload during the active worker run. After any page reload (or if the user navigates to the review page after the job completes), the banner will never appear, regardless of how many low-confidence pages exist.

**Fix — two-part:**

1. Add a `low_confidence_pages` column (JSON, nullable) to the `Job` model and migration:
```python
# db/models.py — Job class
low_confidence_pages: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

2. Persist it in the worker when transitioning to `needs_review`, and include it in `_job_to_dict`:
```python
# translate_worker.py — scanned_pdf compose branch
if _low_conf_pages:
    job.low_confidence_pages = _low_conf_pages
    job.status = JobStatus.needs_review
    await session.flush()
```
```python
# jobs.py — _job_to_dict
"low_confidence_pages": job.low_confidence_pages,
```

### WR-03: `submitWithAction` stale closure — `isScannedOverride`/`isScannedDetected` missing from deps

**File:** `frontend/src/components/UploadForm.tsx:106-156`

**Issue:** `submitWithAction` is wrapped in `useCallback` with deps `[file, targetLang, sourceLang, glossaryId, router, toast]` (line 155). The callback body captures `isScannedOverride` (line 123) and `isScannedDetected` (line 123) from the outer scope. Both are state variables. If the user selects a file (which sets `isScannedDetected`), then changes the scanned override toggle (which sets `isScannedOverride`), then submits — the `submitWithAction` reference they hold may be a stale closure from the previous render where `isScannedOverride` was still `null`. The form will silently submit with the wrong `is_scanned_override` value.

**Fix:**
```tsx
[file, targetLang, sourceLang, glossaryId, isScannedOverride, isScannedDetected, router, toast]
```

### WR-04: `FlagType.ocr_page_error` defined and wired in UI but never emitted by the worker

**File:** `backend/src/app/workers/translate_worker.py` (scanned_pdf compose branch, lines 780-795)

**Issue:** `FlagType.ocr_page_error` is defined in `db/models.py:167`, rendered correctly by `SegmentRow.tsx`, and shows up as a filter chip in `ReviewFilterBar.tsx`. However, the worker never creates a `SegmentFlag` row with `flag_type=FlagType.ocr_page_error`. Per-page OCR failures produce a placeholder `Segment` with `confidence=0.0` but no associated flag. Reviewers cannot use the "OCR ERR" filter chip to locate failed pages.

**Fix:** In the scanned_pdf compose branch (after `_ocr_db_flags` is assembled), add flags for all segments that have `confidence == 0.0` and `source_text == "[OCR failed for this page]"`:
```python
for _seg in segments:
    if (
        getattr(_seg, "kind", None) == "ocr_text"
        and getattr(_seg, "confidence", None) == 0.0
        and _seg.source_text == "[OCR failed for this page]"
    ):
        _ocr_db_flags.append(SegmentFlag(
            segment_id=_seg.id,
            segment_job_id=job_id,
            flag_type=FlagType.ocr_page_error,
            severity=FlagSeverity.warn,
            details={"page": _seg.structural_position},
        ))
```

### WR-05: `make_segment_flag` test fixture missing required `segment_job_id` field

**File:** `backend/tests/conftest.py:188-195`

**Issue:** `SegmentFlag` has a compound foreign key constraint requiring both `segment_id` and `segment_job_id` (`fk_segment_flags_segment` on models.py:234-239). The `make_segment_flag` fixture constructs `SegmentFlag(segment_id=segment_id, ...)` but never sets `segment_job_id`. Any test that calls `make_segment_flag` and then attempts to flush/commit will raise a NOT NULL violation on `segment_job_id` or a FK constraint violation. The fixture is silently incomplete.

**Fix:**
```python
async def _make(
    segment_id: str,
    segment_job_id: str,        # add required parameter
    flag_type: str = "overflow",
    severity: str = "warn",
    details: dict | None = None,
):
    from app.db.models import SegmentFlag, FlagType, FlagSeverity
    f = SegmentFlag(
        id=str(uuid.uuid4()),
        segment_id=segment_id,
        segment_job_id=segment_job_id,   # add this
        flag_type=FlagType(flag_type),
        severity=FlagSeverity(severity),
        details=details or {},
    )
```

### WR-06: `objectPosition` CSS formula incorrect for image crop preview

**File:** `frontend/src/components/SegmentRow.tsx:279`

**Issue:**
```tsx
objectPosition: `-${segment.region_bbox[0] * 100}% -${segment.region_bbox[1] * 100}%`,
```
`region_bbox` values are normalized to `[0, 1]`. For `object-fit: none` (which is not even set — `object-fit` defaults to `fill`), `object-position` percentages are relative to the element's content area minus the image's intrinsic size. Multiplying normalized bbox coordinates by 100 and using them as CSS percentages does not produce a pixel-accurate crop at `region_bbox` coordinates; it produces an offset based on the element's dimensions, not the image's. The current class is also `object-none` (set via `className="w-full object-none"`) — combined with a percentage `objectPosition`, the crop position will be wrong for any bbox that is not at the top-left corner.

For correct region cropping without a canvas, use CSS `clip-path` or a wrapper `overflow:hidden` div with an absolutely-positioned `<img>` shifted by the negative pixel offset derived from the full-page PNG dimensions.

A simpler approach for PoC: render the full page image and use a CSS outline or box-shadow overlay to highlight the region, which avoids the coordinate transform entirely.

**Immediate partial fix** (reduces visible error by anchoring to page percentage):
```tsx
// The page PNG is full-page. Treat objectPosition as "show region at bbox coords".
// object-fit:none + object-position in % aligns the image's top-left with the element.
// Use negative pixel offsets computed from the img's natural dimensions via onLoad.
// For now, flag as needs-rework; provide region highlight overlay instead.
```

---

## Info

### IN-01: `segment_to_md.py` uses `edited_source_text` instead of `translated_text` for DOCX export

**File:** `backend/src/app/pipeline/scanned_pdf/segment_to_md.py:53-54`

**Issue:** The comment block at lines 29-35 explicitly acknowledges a design ambiguity. The current implementation uses:
```python
text = seg.edited_source_text or seg.translated_text or seg.source_text
```
`edited_source_text` is the reviewer's correction of the OCR-extracted source text (not the translation). For DOCX export the correct priority should be the translated output: `translated_text ?? source_text`, with `edited_source_text` only used as the source for re-translation, not as the output text. As-is, DOCX export will silently output the OCR source correction instead of the translation whenever a reviewer corrects the source cell.

The `Segment` dataclass does not have an `edited_text` field (that exists only in the ORM `Segment` model), which is the root cause of the confusion. The worker uses `translated_map` as the authoritative translation source. The fix is to pass `translated_map` into `segments_to_markdown` and use it:

```python
def segments_to_markdown(segments: list[Segment], translated_map: dict[str, str] | None = None) -> str:
    ...
    text = (
        (translated_map.get(seg.id) if translated_map else None)
        or seg.translated_text
        or seg.source_text
    )
```

Then in the worker:
```python
_md_text = segments_to_markdown(segments, translated_map=translated_map)
```

### IN-02: Duplicate type definitions across `types.ts` and `review-types.ts` with divergent `SegmentsResponse`

**File:** `frontend/src/lib/review-types.ts:41-44`

**Issue:** `FlagType`, `Segment`, `SegmentFlag`, and `SegmentsResponse` are defined in both `lib/types.ts` and `lib/review-types.ts`. The file-level comment acknowledges the debt ("These types will be consolidated into lib/types.ts by Plan 05"). A concrete divergence is already present: `SegmentsResponse` in `review-types.ts` (line 41-44) is missing the `flag_counts` field that `types.ts` includes (line 104-108). The `useSegments.ts` hook imports from `review-types.ts` (line 4) and uses its `SegmentsResponse` — meaning `flag_counts` is silently discarded from the parsed response. `ReviewFilterBar` recomputes flag counts client-side from the full segment list instead, masking this gap, but it doubles work and diverges from the server-computed counts.

---

_Reviewed: 2026-04-28T10:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
