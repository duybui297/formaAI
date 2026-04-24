---
status: diagnosed
phase: 01-foundation-docx-pipeline
source:
  - 01-01-SUMMARY.md
  - 01-02-SUMMARY.md
  - 01-03-SUMMARY.md
  - 01-04-SUMMARY.md
  - 01-05-SUMMARY.md
  - 01-06a-SUMMARY.md
  - 01-06b-SUMMARY.md
  - 01-07-SUMMARY.md
  - 01-08-SUMMARY.md
  - 01-09-SUMMARY.md
  - 01-10-SUMMARY.md
  - 01-11-SUMMARY.md
started: 2026-04-24T14:10:00Z
updated: 2026-04-24T14:10:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: 8
name: Oversize file rejection
expected: |
  Upload a DOCX > 50 MB (MAX_UPLOAD_BYTES). Form rejects with a clear message (HTTP 413). No job created. Existing jobs list unchanged.
awaiting: closed — skipped (deferred to phase that handles PDF)

## Tests

### 1. Cold Start Smoke Test
expected: Run `docker compose down -v` then `docker compose up -d`. All 5 containers (api, worker, web, postgres, redis) reach healthy state. `curl http://localhost:8000/health` returns `{"status":"ok"}`. Frontend at http://localhost:3000 redirects `/` → `/upload` and renders the upload form.
result: pass

### 2. Upload DOCX end-to-end
expected: On http://localhost:3000/upload, drag-and-drop (or browse to) `examples/ICOM_Proposal_JP.docx`. Select source=Auto-detect, target=Vietnamese. Click Submit. Page redirects to `/jobs/{job_id}` with live progress bar and stage indicator (parse → translate → reassemble → done).
result: pass

### 3. Tracked-changes modal appears
expected: When uploading a DOCX with tracked changes (ICOM_Proposal_JP.docx qualifies), a modal appears BEFORE submission with "Strip tracked changes" / "Keep tracked changes" options. Picking one submits the job with that choice.
result: issue
reported: "earlier i saw that but then i didn't. also format of text (bold, italic, etc.) in .docx still not right. For example: If at the first paragraph, some characters is bold, then whole paragraph is bold, or text-embedding-ada-002 or equivalient need to underline and italic but translated document it became normal"
severity: major

### 4. Job status page SSE live progress
expected: On `/jobs/{id}` during a running job, the progress counter animates smoothly from 0 → N/total as each batch completes. Stage indicator advances through parse → translate → reassemble → done. No page refresh needed.
result: pass

### 5. Download translated DOCX
expected: When a job reaches `done` state, a Download button appears. Clicking it saves a DOCX. Opening it in Word/LibreOffice shows paragraphs + tables translated to the target language with original structure intact (same paragraph count, same table count, bold/italic runs preserved).
result: issue
reported: "no, as i told you — same run-merge format-collapse issue observed on the downloaded DOCX"
severity: major
refs_gap: "DOCX-02 run-merge collapse (already logged under Test 3)"

### 6. Jobs list page
expected: At http://localhost:3000/jobs, a table lists all jobs with columns: filename, format, lang pair, status, progress, created-at. Row click navigates to `/jobs/{id}` detail page. Empty state shows "No translations yet" with CTA back to upload.
result: pass

### 7. Invalid format rejection
expected: Upload a `.txt` or `.pdf` file. Form rejects with a clear message (HTTP 415). No job created. User can re-select a valid file without refreshing.
result: issue
reported: "nothing appeared, no message appeared when click Translate Document button"
severity: major

### 8. Oversize file rejection
expected: Upload a DOCX > 50 MB (MAX_UPLOAD_BYTES). Form rejects with a clear message (HTTP 413). No job created. Existing jobs list unchanged.
result: skipped
reason: "User deferred: 'skip for later (will test by use pdf later)' — plans to validate size cap with a PDF in Phase 3"
blocked_by: prior-phase

## Summary

total: 8
passed: 4
issues: 3
pending: 0
skipped: 1

## Gaps

- truth: "Tracked-changes detection in UploadForm reliably shows the strip/keep modal every time a DOCX with <w:ins>/<w:del> nodes is selected"
  status: flaky
  reason: "User reported: 'earlier i saw that but then i didn't' — modal appears inconsistently across repeated uploads of the same file"
  severity: major
  test: 3
  hypotheses:
    - "detectTrackedChanges() may short-circuit on a cached File.arrayBuffer() reference after the first read (browsers sometimes return an already-consumed stream)"
    - "useState race: submit handler may fire before the async detection promise resolves on second upload"
    - "showTrackedModal state not reset between file changes — once dismissed, subsequent detections see the stale `trackedAction !== null` guard and skip the modal"
  artifacts:
    - frontend/src/lib/detectTrackedChanges.ts
    - frontend/src/components/UploadForm.tsx
  missing:
    - reset of hasTrackedChanges + trackedAction state on every onFileChange
    - explicit await of detection before enabling the Submit button
    - integration test that exercises two back-to-back uploads of the same tracked-changes DOCX

- truth: "DOCX-02 run-merge preserves per-run character formatting (bold/italic/underline/color/font) across the full translated paragraph — not just the first run's formatting"
  status: broken
  reason: "User reported: 'If at the first paragraph, some characters is bold, then whole paragraph is bold' (run-merge collapses all runs into runs[0] formatting). Also: 'text-embedding-ada-002 or equivalent need to underline and italic but translated document it became normal' (multi-format runs after runs[0] lose their formatting entirely)"
  severity: major
  test: 3
  analysis: |
    Current impl `runs[0].text = translated; runs[1:].text = ""` works only when the source
    paragraph has uniform formatting. For paragraphs with mixed runs (e.g. "text-embedding-
    ada-002" italic+underline inside a plain paragraph), the translator cannot align
    translated character positions to source run boundaries because the model returns a
    single flat string with no formatting markers. This is a known limitation of the naive
    run-merge strategy documented in AI-SPEC §1b "Formatting preservation" — the issue
    isn't a bug in run-merge itself, but that run-merge is the wrong strategy for
    multi-format paragraphs.
  artifacts:
    - backend/src/app/pipeline/docx/reassembler.py
    - backend/src/app/pipeline/docx/extractor.py
    - backend/src/app/llm/translator.py
  missing:
    - per-run segment extraction (one segment per run, with character offsets preserved)
    - inline-format markers in the LLM payload (e.g. `[[B:]]text[[/B:]]` or sentinel tags)
      that the model is instructed to preserve and that the reassembler can parse back
    - alignment algorithm mapping translated output characters back to source run boundaries
    - test fixture: a paragraph with 3+ distinct formatting runs, round-tripped through the
      pipeline, asserting each run's formatting survives

- truth: "UploadForm surfaces a visible error message when the user clicks 'Translate Document' with an unsupported file type (.pdf/.pptx/.txt/etc), and does NOT enqueue a job"
  status: broken
  reason: "User reported: 'nothing appeared, no message appeared when click Translate Document button' — button click silently swallows the failure response from the server. UX gap: user cannot tell whether something is happening or whether it was rejected."
  severity: major
  test: 7
  analysis: |
    Likely causes (ranked by probability):
    1. Frontend fetch() throws on non-2xx HTTP response but the try/catch discards the
       error silently (no setState({error: ...}) to render).
    2. Form action handler `await response.json()` chokes when the backend returns a
       non-JSON error body or 415/422 payload that differs from the happy-path shape.
    3. Next.js API route `/api/upload/route.ts` proxy transforms the backend 415 into a
       generic 500, hiding the underlying "unsupported format" message.
    4. UploadForm's type accept="" attribute is broad, so the <input> never prevents the
       user from picking a .pdf in the first place — then backend rejects but UI has no
       error surface to render the response in.
  artifacts:
    - frontend/src/components/UploadForm.tsx
    - frontend/src/app/api/upload/route.ts
    - backend/src/app/api/routes/upload.py
  missing:
    - <input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document">
      restricts the OS file picker to DOCX only (defense in depth — user can still drag
      other files, handle those server-side)
    - UploadForm error state: `const [error, setError] = useState<string | null>(null)`
      that renders below the submit button when set
    - fetch() success branch: read `response.status`; if 4xx, parse error JSON and
      setError(body.detail || "Unsupported file type. Phase 1 accepts .docx only.")
    - Next.js /api/upload/route.ts proxy must forward the backend's status code + body
      verbatim, NOT swallow to a 500
    - integration test: POST /upload with a .pdf file → 415 with a descriptive detail
      field that the frontend can surface
