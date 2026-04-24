---
phase: 01-foundation-docx-pipeline
reviewed: 2026-04-24T08:31:59Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - backend/src/app/pipeline/segment.py
  - backend/src/app/pipeline/docx/extractor.py
  - backend/src/app/pipeline/docx/reassembler.py
  - backend/src/app/workers/translate_worker.py
  - frontend/src/components/UploadForm.tsx
findings:
  critical: 0
  warning: 3
  info: 3
  total: 6
status: issues_found
---

# Phase 01: Code Review Report — Wave 5 Gap Closure

**Reviewed:** 2026-04-24T08:31:59Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found (0 critical, 3 warnings, 3 info)

## Summary

Reviewed five Wave 5 gap-closure files across the run-format preservation (G2) and error
state (G1/G3) work. No critical issues found. The overall structure is sound: the
`extract_run_segments` → `reassemble_docx_runs` pipeline is correctly paired, the
walk-order para_seq counter is symmetric between extractor and reassembler, and the
`detecting` guard in `UploadForm` correctly blocks premature submission.

Three warnings require attention before the next PoC demo milestone:

1. A dead-code `if/else` in `extractor.py` (both branches identical) — currently harmless
   but masks an incomplete empty-run-groups case.
2. The `file` input `accept` attribute is `.docx`-only while the drop zone promises
   PDF/PPTX support — the native file picker silently hides those formats.
3. FastAPI's auto-generated 422 response (`detail` is an array) will render as
   `[object Object]` if the frontend receives it directly — only triggered by malformed
   API calls, but worth hardening.

---

## Warnings

### WR-01: Dead-code `if/else` in `extract_run_segments` masks logic gap

**File:** `backend/src/app/pipeline/docx/extractor.py:181-184`

**Issue:** Both branches of the condition are identical — `para_seq` is incremented
unconditionally regardless of whether the paragraph had content or not. The boolean
expression `if para_had_content or any(r.text.strip() for r in runs)` is evaluated
and then discarded because both paths do the same thing. This tells the reader that
a distinction was intended (perhaps not incrementing for all-whitespace paragraphs)
but was never implemented. The resulting behaviour is correct (every visited paragraph
increments once, matching the reassembler's symmetric counter), but the dead code
signals an incomplete thought and will confuse future maintainers.

```python
# Current (lines 181-184) — both branches identical:
if para_had_content or any(r.text.strip() for r in runs):
    para_seq += 1
else:
    para_seq += 1
```

**Fix:** Collapse to an unconditional increment with a comment explaining the
design decision:

```python
# Increment for every paragraph regardless of content — reassembler mirrors
# this counter exactly so empty paragraphs still consume a slot.
para_seq += 1
```

---

### WR-02: `<input type="file">` `accept` attribute only allows `.docx` — inconsistent with UI

**File:** `frontend/src/components/UploadForm.tsx:194`

**Issue:** The hidden file input declares
`accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"`.
The drop zone label says "Drop your DOCX, PDF, or PPTX here" and `ALLOWED_EXTS`
includes `.pdf` and `.pptx`. When a user clicks the drop zone to open the native file
picker, the OS filters to DOCX only — PDF and PPTX files are not shown. Drag-and-drop
still works for all three types because the `accept` attribute is not enforced on drop
events. This is a UX inconsistency: some upload paths silently restrict while others
do not.

**Fix:** Align `accept` with `ALLOWED_EXTS`:

```tsx
accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document,.pdf,application/pdf,.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation"
```

Note: In Phase 1 the backend rejects PDF/PPTX with a 422. That is the correct
server-side gate. The file picker should still allow selection of all three so the
user sees the informative 422 error message rather than being silently unable to
find their file.

---

### WR-03: `data.detail` array coercion to string when FastAPI auto-generates 422

**File:** `frontend/src/components/UploadForm.tsx:114`

**Issue:** The error extraction `data.detail || data.error || "Upload failed..."` assumes
`data.detail` is always a string. The custom `HTTPException` calls in `upload.py` always
pass a string `detail`, so the happy/sad paths through the application are fine. However,
if FastAPI generates its own 422 (e.g., missing required form field `source_lang` or
`target_lang` due to a client bug), the response body is
`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. In that case
`data.detail` is an array, `setError(msg)` stores the string `"[object Object]"`,
and the error paragraph renders `[object Object]` instead of a useful message.

```tsx
// Current — line 114:
const msg = data.detail || data.error || "Upload failed. Please try again."
```

**Fix:** Normalise `detail` before use:

```tsx
const rawDetail = data.detail
const msg =
  typeof rawDetail === "string"
    ? rawDetail
    : Array.isArray(rawDetail)
    ? rawDetail.map((e: { msg?: string }) => e.msg ?? JSON.stringify(e)).join("; ")
    : data.error ?? "Upload failed. Please try again."
```

---

## Info

### IN-01: `getExt` returns last character for filenames with no dot

**File:** `frontend/src/components/UploadForm.tsx:16`

**Issue:** `filename.lastIndexOf(".")` returns `-1` for filenames with no extension.
`filename.slice(-1)` therefore returns the last character of the filename (e.g., `"e"`
for `"nodotfile"`). In practice this character is not in `ALLOWED_EXTS`, so the toast
fires correctly. But the function's contract is misleading and could cause confusion
if `getExt` is reused elsewhere.

```ts
// "nodotfile".slice(-1) === "e" — not "" as expected
```

**Fix:**
```ts
function getExt(filename: string): string {
  const idx = filename.lastIndexOf(".")
  return idx === -1 ? "" : filename.slice(idx).toLowerCase()
}
```

---

### IN-02: `import logging` and `from collections import defaultdict` are deferred inside functions

**File:** `backend/src/app/pipeline/docx/reassembler.py:76` and
`backend/src/app/pipeline/docx/reassembler.py:141`

**Issue:** Both `import logging` (inside `write_translated_run`) and
`from collections import defaultdict` (inside `reassemble_docx_runs`) are module-level
standard-library imports deferred inside function bodies with `# noqa: PLC0415`. These
are unconditionally reachable code paths, so there is no circular-import justification.
Deferred imports add per-call overhead (mitigated by Python's import cache but still
non-zero) and obscure the function's dependencies.

**Fix:** Move both to the top of the module:

```python
# At top of reassembler.py:
import logging
from collections import defaultdict
```

Then remove the inline imports and the `# noqa: PLC0415` suppressions.

---

### IN-03: `detecting` state is not cleared on drag-and-drop validation failure

**File:** `frontend/src/components/UploadForm.tsx:44-72`

**Issue:** `detecting` is set to `true` only after the early-return validation guards
(lines 46-59), so a rejected file never sets `detecting = true` — which means there is
nothing to clear. This is actually correct behaviour. However, if a future change moves
the `setDetecting(true)` call before the validation guards, the function would return
early and leave `detecting` stuck as `true`, permanently disabling the Submit button.
The pattern is fragile.

**Suggestion:** Document the ordering dependency with a comment, or restructure to use
`finally`:

```ts
const handleFile = useCallback(async (f: File) => {
  const ext = getExt(f.name)
  if (!ALLOWED_EXTS.has(ext)) { /* toast */ return }
  if (f.size > MAX_SIZE_BYTES) { /* toast */ return }

  // Validation passed — safe to start async detection.
  // setDetecting(true) must remain AFTER the guards above so early-return
  // paths never leave detecting=true with no corresponding setDetecting(false).
  setError(null)
  setFile(f)
  setTrackedAction(null)
  setHasTrackedChanges(false)
  setShowTrackedModal(false)
  setDetecting(true)
  try {
    const hasTC = await detectTrackedChanges(f)
    setHasTrackedChanges(hasTC)
  } finally {
    setDetecting(false)
  }
}, [toast])
```

Using `finally` makes the cleanup robust against future changes and exceptions thrown
by `detectTrackedChanges`.

---

_Reviewed: 2026-04-24T08:31:59Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
