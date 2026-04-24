---
phase: 01-foundation-docx-pipeline
plan: "14"
type: execute
wave: 5
depends_on: []
files_modified:
  - frontend/src/components/UploadForm.tsx
  - frontend/src/app/api/upload/route.ts
  - backend/tests/api/test_upload.py
autonomous: true
gap_closure: true
requirements:
  - UPLD-02
  - LANG-01

must_haves:
  truths:
    - "UploadForm surfaces a visible error message when the user clicks 'Translate Document' with an unsupported file type (.pdf/.pptx/.txt/etc), and does NOT enqueue a job"
  artifacts:
    - path: "frontend/src/components/UploadForm.tsx"
      provides: "error state (useState<string | null>); rendered below Submit; 4xx branch parses detail"
    - path: "frontend/src/components/UploadForm.tsx"
      provides: "accept='.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document' on file input"
    - path: "frontend/src/app/api/upload/route.ts"
      provides: "backend status + body forwarded verbatim (no 500 swallow)"
    - path: "backend/tests/api/test_upload.py"
      provides: "integration test: POST /upload with .pdf → 415 with detail containing 'DOCX'"
  key_links:
    - from: "frontend/src/components/UploadForm.tsx:submitWithAction"
      to: "frontend/src/components/UploadForm.tsx:error state"
      via: "non-2xx fetch response → setError(data.detail || fallback)"
      pattern: "setError\\("
    - from: "frontend/src/app/api/upload/route.ts"
      to: "backend POST /upload"
      via: "Response.json(data, { status: response.status }) — status forwarded verbatim"
      pattern: "response\\.status"
---

<objective>
Close UAT gap G3: clicking "Translate Document" with a .pdf or .txt file produced no visible feedback. The button click silently swallowed the server's 415 rejection.

Three layered fixes required:

1. **Frontend accept attribute** — `<input type="file" accept=".docx,...">` restricts the OS file picker to DOCX only (defense-in-depth UX; does not prevent drag-and-drop of other types).

2. **UploadForm error state** — Add `const [error, setError] = useState<string | null>(null)` rendered below the Submit button. In `submitWithAction`, read `response.status`; if not ok, parse body for `detail` and call `setError()`.

3. **Next.js proxy status forwarding** — The current `/api/upload/route.ts` already forwards `response.status` via `Response.json(data, { status: response.status })` — this is correct. Verify it still applies and add the integration test to prove the 415 propagates end-to-end.

Note: The backend's magic-byte / extension check in `upload.py` is the authoritative validation. The `accept` attribute on the input is client-side convenience only — the server MUST remain the source of truth (T-14-02).

Purpose: User gets a clear, inline error message ("DOCX files only — PDF and PPTX support coming soon.") when an unsupported format is selected and submitted. No page refresh required. The Submit button re-enables after the error so the user can select a valid file.

Output: UploadForm.tsx (error display + non-ok branch), no changes to route.ts (already correct), new backend integration test, new frontend vitest test.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-foundation-docx-pipeline/01-UAT.md
@.planning/phases/01-foundation-docx-pipeline/01-06a-SUMMARY.md
@.planning/phases/01-foundation-docx-pipeline/01-08-SUMMARY.md

<interfaces>
<!-- Current UploadForm submitWithAction (frontend/src/components/UploadForm.tsx) -->
```typescript
const submitWithAction = useCallback(async (action: "strip" | "preserve" | null) => {
  if (!file || !targetLang) return
  setSubmitting(true)
  try {
    const formData = new FormData()
    // ... formData.append calls ...
    const res = await fetch("/api/upload", { method: "POST", body: formData })
    const data = await res.json()
    if (!res.ok) {
      toast({ variant: "destructive", description: data.detail || data.error || "Upload failed." })
      setSubmitting(false)
      return
    }
    router.push(`/jobs/${data.job_id}`)
  } catch {
    toast({ variant: "destructive", description: "Upload failed. Please check your connection." })
    setSubmitting(false)
  }
}, [file, targetLang, sourceLang, router, toast])
```

<!-- Current file input (frontend/src/components/UploadForm.tsx) -->
```tsx
<input
  id="file-input"
  type="file"
  accept=".docx,.pdf,.pptx"   // ← must change to DOCX-only
  className="hidden"
  onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
/>
```

<!-- Current Next.js proxy (frontend/src/app/api/upload/route.ts) -->
```typescript
const response = await fetch(`${backendUrl}/upload`, { method: "POST", body: backendForm })
const data = await response.json()
return Response.json(data, { status: response.status })  // ← already correct
```

<!-- Backend 415 response shape (from upload.py) -->
```python
raise HTTPException(
    status_code=415,
    detail="Unsupported file type. Upload a DOCX, PDF, or PPTX.",
)
# FastAPI serializes this as: {"detail": "Unsupported file type. Upload a DOCX, PDF, or PPTX."}
```

<!-- Backend 422 response shape for Phase 1 format gate -->
```python
raise HTTPException(
    status_code=422,
    detail="PDF translation is not yet supported. DOCX is available now; PPTX and PDF are coming in the next release.",
)
```

<!-- Backend test fixture pattern (backend/tests/api/test_upload.py) -->
```python
# Existing pattern from 01-06a: ASGITransport + httpx AsyncClient + dependency_overrides
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
    response = await client.post("/upload", data={...}, files={"file": (filename, content, mime)})
assert response.status_code == 415
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add error state to UploadForm + restrict file input accept</name>
  <files>frontend/src/components/UploadForm.tsx</files>
  <read_first>
    - frontend/src/components/UploadForm.tsx (full file — submitWithAction, canSubmit, file input, form JSX)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, third gap — analysis section, `missing` list verbatim)
  </read_first>
  <behavior>
    - When submitWithAction receives a non-2xx response from /api/upload, error message renders below the Submit button
    - Error message contains the `detail` field from the response body (e.g., "Unsupported file type. Upload a DOCX, PDF, or PPTX.")
    - Submitting button re-enables after error (user can pick a new file and retry without refresh)
    - File input `accept` attribute is restricted to `.docx` only in the OS picker
    - Error message is cleared when a new file is selected (handleFile resets error)
    - Error message is cleared at the start of a new submission attempt
  </behavior>
  <action>
Make the following changes to UploadForm.tsx:

### 1. Add error state
```typescript
const [error, setError] = useState<string | null>(null)
```

### 2. Reset error on file selection and on submit start
In `handleFile`, add `setError(null)` near the top (after the file-type and size guards, before `setFile(f)`).
In `submitWithAction`, add `setError(null)` as the first statement (before `setSubmitting(true)`).

### 3. Update the non-ok branch in submitWithAction
Replace the current toast-only path:
```typescript
if (!res.ok) {
  const msg = data.detail || data.error || "Upload failed. Please try again."
  setError(msg)      // ← render inline, not just toast
  toast({ variant: "destructive", description: msg })   // keep toast for accessibility
  setSubmitting(false)
  return
}
```

### 4. Render error message below Submit button
In JSX, add after the Submit `<Button>`:
```tsx
{error && (
  <p role="alert" className="text-sm text-red-600 mt-1">
    {error}
  </p>
)}
```

### 5. Restrict file input accept attribute
Change:
```tsx
accept=".docx,.pdf,.pptx"
```
To:
```tsx
accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
```
Also update `ALLOWED_EXTS` comment and dropZoneText placeholder to say "Drop your DOCX here" (DOCX is the only Phase 1 supported format — PDF and PPTX show a 422 from backend if submitted via drag-and-drop bypass, which the error state now surfaces correctly).

Note: ALLOWED_EXTS set can remain as `{".docx", ".pdf", ".pptx"}` for now so drag-and-drop of PDF/PPTX still passes client validation and gets rejected by the server with an informative 422, which the error state then displays.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | tail -10</automated>
  </verify>
  <done>
    - `grep -n "useState.*null.*error\|const \[error" frontend/src/components/UploadForm.tsx` shows the state declaration
    - `grep -n "setError(" frontend/src/components/UploadForm.tsx` shows at least 3 occurrences (reset on file, reset on submit, set on error)
    - `grep -n "role=\"alert\"" frontend/src/components/UploadForm.tsx` shows the error paragraph
    - `grep -n 'accept=' frontend/src/components/UploadForm.tsx` shows `.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document`
    - `npx tsc --noEmit` exits 0
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Verify proxy forwards status verbatim + add frontend vitest for error display</name>
  <files>
    frontend/src/app/api/upload/route.ts,
    frontend/src/__tests__/UploadForm.test.tsx
  </files>
  <read_first>
    - frontend/src/app/api/upload/route.ts (verify `Response.json(data, { status: response.status })` already present)
    - frontend/src/__tests__/UploadForm.test.tsx (existing test patterns — mockDetect, vi.hoisted, fireEvent.change for file input)
    - frontend/src/components/UploadForm.tsx (updated from Task 1 — error state and setError calls)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, third gap — `missing` list item: "fetch() non-2xx branch parses detail + displays")
  </read_first>
  <action>
### 1. Verify route.ts (read-only check)
Open `frontend/src/app/api/upload/route.ts` and confirm the catch-free success path already returns:
```typescript
return Response.json(data, { status: response.status })
```
If the file already has this, NO changes are needed to route.ts. If it wraps the status in a different way, update to forward verbatim.

### 2. Add frontend vitest tests for error display
Add to `frontend/src/__tests__/UploadForm.test.tsx`:

**Test: "shows inline error message on 415 response"**
```typescript
it("shows inline error message on 415 response", async () => {
  // Mock fetch to return 415 with detail
  globalThis.fetch = vi.fn().mockResolvedValueOnce({
    ok: false,
    status: 415,
    json: async () => ({ detail: "Unsupported file type. Upload a DOCX, PDF, or PPTX." }),
  })
  // Set file + targetLang so canSubmit = true
  // ... (follow existing test pattern for setting file)
  // Submit
  // Assert: error paragraph with role="alert" is in the DOM
  // Assert: text matches "Unsupported file type"
})
```

**Test: "clears error when new file selected"**
```typescript
it("clears error on file reselection", async () => {
  // Trigger a 415 error first (same setup as above)
  // Simulate file selection of a new file
  // Assert: error paragraph is no longer in the DOM
})
```

Follow the exact test helper patterns from the existing test file (vi.hoisted for mockFetch, fireEvent.change for file inputs, waitFor for async state updates).
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx vitest run src/__tests__/UploadForm.test.tsx 2>&1 | tail -15</automated>
  </verify>
  <done>
    - route.ts contains `Response.json(data, { status: response.status })` (grep: `grep -n "response.status" frontend/src/app/api/upload/route.ts`)
    - Two new test names present in UploadForm.test.tsx: `grep -n "inline error message\|clears error" frontend/src/__tests__/UploadForm.test.tsx`
    - All vitest tests pass in UploadForm.test.tsx (0 failed)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Add backend integration test — POST /upload with .pdf returns 415</name>
  <files>backend/tests/api/test_upload.py</files>
  <read_first>
    - backend/tests/api/test_upload.py (full file — existing test patterns: ASGITransport, dependency_overrides, file upload fixtures)
    - backend/src/app/api/routes/upload.py (the 415 and 422 code paths — extension check and Phase 1 format gate)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, third gap — `missing` item: "integration test: POST /upload with a .pdf file → 415 with a descriptive detail field")
  </read_first>
  <behavior>
    Test: POST /upload with filename="report.pdf" → status 415, detail contains "Unsupported" or "DOCX"
    Test: POST /upload with filename="slides.pptx" → status 422, detail contains "PPTX" (Phase 1 gate)
    Test: POST /upload with filename="notes.txt" → status 415, detail contains "Unsupported"
  </behavior>
  <action>
Add 3 new test functions to `backend/tests/api/test_upload.py` following the existing test patterns exactly:

```python
@pytest.mark.asyncio
async def test_upload_pdf_returns_415(client):
    """POST /upload with .pdf should return 415 (extension not DOCX)."""
    response = await client.post(
        "/upload",
        data={"source_lang": "auto", "target_lang": "vi"},
        files={"file": ("report.pdf", b"%PDF-1.4 fake content", "application/pdf")},
    )
    assert response.status_code == 415
    body = response.json()
    assert "detail" in body
    # detail must be surfaceable to the frontend — must not be empty
    assert len(body["detail"]) > 10

@pytest.mark.asyncio
async def test_upload_pptx_returns_422_phase1_gate(client):
    """POST /upload with .pptx should return 422 (Phase 1 gate — PPTX not yet supported)."""
    response = await client.post(
        "/upload",
        data={"source_lang": "auto", "target_lang": "vi"},
        files={"file": ("slides.pptx", b"PK fake pptx content", "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "PPTX" in body["detail"] or "pptx" in body["detail"].lower()

@pytest.mark.asyncio
async def test_upload_txt_returns_415(client):
    """POST /upload with .txt should return 415 (unsupported extension)."""
    response = await client.post(
        "/upload",
        data={"source_lang": "auto", "target_lang": "vi"},
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 415
    body = response.json()
    assert "detail" in body
    assert len(body["detail"]) > 10
```

Use the same `client` fixture already defined in the test file (AsyncClient with app dependency_overrides). Do NOT add new fixtures.

Note: test_upload.py already has a test for `.txt` returning 415 (`test_upload_unsupported_extension_returns_415`) — if that test exists, add a comment referencing the new test as "GAP G3 coverage" and verify the existing test covers the case. Only add the test if not already present with that exact assertion.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/api/test_upload.py -q 2>&1 | tail -15</automated>
  </verify>
  <done>
    - `grep -n "def test_upload_pdf_returns_415\|def test_upload_pptx_returns_422\|def test_upload_txt_returns_415" backend/tests/api/test_upload.py` shows the new test functions
    - `uv run pytest tests/api/test_upload.py -q` exits 0 (all tests pass)
    - Test coverage for upload.py: `uv run pytest tests/api/test_upload.py --cov=app.api.routes.upload --cov-report=term-missing -q 2>&1 | grep "upload.py"` shows ≥ 80%
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser file picker → UploadForm | User-selected file (type, name) |
| UploadForm → /api/upload (Next.js proxy) | FormData with file + language fields |
| Next.js proxy → FastAPI POST /upload | Forwarded FormData |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-14-01 | Spoofing | File `accept` attribute bypass | accept | The `accept` attribute restricts the OS picker but does NOT prevent a user from dragging a .pdf onto the drop zone. This is by design: the server is the authoritative validator. The backend's extension check + Phase 1 format gate (upload.py lines 65-81) remains the hard enforcement point. Client-side is defense-in-depth UX only. |
| T-14-02 | Tampering | Magic-byte spoof — rename .exe to .docx | accept | Phase 1 server validates by file extension (UPLD-02). Full magic-byte validation (reading file header bytes) is a Phase 2+ hardening item per project scope. The PoC threat model accepts this: it's an internal demo with no external users. |
| T-14-03 | Information Disclosure | Error detail forwarded to browser | accept | Backend HTTPException `detail` strings are intentionally informative for the internal PoC (T-06a-05 disposition from Plan 06a). They do not expose stack traces, file paths, or secrets — only human-readable rejection reasons. Accepted per internal PoC scope. |
| T-14-04 | Denial of Service | Error state loop | accept | UploadForm clears error on each new submission attempt (`setError(null)` at start of submitWithAction). No loop possible — the user must physically interact to retry. |
</threat_model>

<verification>
Backend tests:
```bash
cd /home/thu/dev/projects/ai-translation/backend && uv run pytest tests/api/test_upload.py -v 2>&1 | tail -25
```

Frontend tests:
```bash
cd /home/thu/dev/projects/ai-translation/frontend && npx vitest run src/__tests__/UploadForm.test.tsx 2>&1 | tail -15
```

TypeScript check:
```bash
cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1
```

Grep assertions:
```bash
# Error state present
grep -n "const \[error, setError\]" frontend/src/components/UploadForm.tsx

# Error rendered in JSX
grep -n 'role="alert"' frontend/src/components/UploadForm.tsx

# Accept restricted to DOCX
grep -n "accept=" frontend/src/components/UploadForm.tsx

# Proxy forwards status verbatim
grep -n "response.status" frontend/src/app/api/upload/route.ts

# Backend test functions present
grep -n "def test_upload_pdf_returns_415\|def test_upload_pptx_returns_422" backend/tests/api/test_upload.py
```
</verification>

<success_criteria>
- `UploadForm.tsx` renders `<p role="alert">` containing the backend's `detail` message when fetch returns non-2xx
- `UploadForm.tsx` file input `accept` attribute contains `.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `setError(null)` is called on new file selection and at the start of each submission
- `route.ts` returns `Response.json(data, { status: response.status })` (already present, verified)
- Backend test `test_upload_pdf_returns_415` passes: POST with .pdf → HTTP 415 + `detail` field present
- Backend test `test_upload_pptx_returns_422_phase1_gate` passes: POST with .pptx → HTTP 422 + `detail` contains "PPTX"
- Two new frontend tests pass: inline error display + error cleared on reselection
- All existing backend test_upload.py and frontend UploadForm.test.tsx tests still pass
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-14-SUMMARY.md`
</output>
