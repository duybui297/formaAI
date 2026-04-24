---
phase: 01-foundation-docx-pipeline
plan: "12"
type: execute
wave: 5
depends_on: []
files_modified:
  - frontend/src/lib/detectTrackedChanges.ts
  - frontend/src/components/UploadForm.tsx
  - frontend/src/__tests__/UploadForm.test.tsx
autonomous: true
gap_closure: true
requirements:
  - UPLD-01
  - UPLD-05
  - DOCX-04

must_haves:
  truths:
    - "Tracked-changes detection in UploadForm reliably shows the strip/keep modal every time a DOCX with <w:ins>/<w:del> nodes is selected"
  artifacts:
    - path: "frontend/src/components/UploadForm.tsx"
      provides: "resetTrackedState() called in handleFile before detection, Submit disabled while detecting"
    - path: "frontend/src/lib/detectTrackedChanges.ts"
      provides: "fresh arrayBuffer read on every call — no cached reference reuse"
    - path: "frontend/src/__tests__/UploadForm.test.tsx"
      provides: "back-to-back upload test for same tracked-changes DOCX"
  key_links:
    - from: "frontend/src/components/UploadForm.tsx:handleFile"
      to: "frontend/src/lib/detectTrackedChanges.ts"
      via: "await detectTrackedChanges(f) with detecting guard"
      pattern: "setDetecting\\(true\\)"
---

<objective>
Close UAT gap G1: the tracked-changes strip/keep modal appeared on first upload but became unreliable on subsequent uploads of the same DOCX.

Three root causes from UAT diagnosis:
1. State not reset atomically before detection — `hasTrackedChanges` could carry a stale true from the previous file, causing the modal to skip (guard `trackedAction !== null` trips early) or fire incorrectly.
2. Submit button enabled while `detectTrackedChanges()` is still resolving — race condition where the user can submit before `hasTrackedChanges` reflects the new file's result.
3. No integration test covering back-to-back upload of the same file — allowed the regression to survive 20 passing tests.

Purpose: Guarantee the D-13 modal fires reliably on every upload where `<w:ins>` or `<w:del>` exists, including re-selection of the same file, without user-visible flicker.

Output: Two modified source files + one expanded test file. No schema changes, no backend changes.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-foundation-docx-pipeline/01-UAT.md
@.planning/phases/01-foundation-docx-pipeline/01-08-SUMMARY.md

<interfaces>
<!-- Current UploadForm state machine (from frontend/src/components/UploadForm.tsx) -->
```typescript
const [hasTrackedChanges, setHasTrackedChanges] = useState(false)
const [showTrackedModal, setShowTrackedModal] = useState(false)
const [trackedAction, setTrackedAction] = useState<"strip" | "preserve" | null>(null)

// Current handleFile — BUG: resets state then immediately reads stale hasTrackedChanges
const handleFile = useCallback(async (f: File) => {
  setFile(f)
  setTrackedAction(null)        // ← reset
  setHasTrackedChanges(false)   // ← reset (async, not yet flushed when detect runs)
  const hasTC = await detectTrackedChanges(f)
  setHasTrackedChanges(hasTC)   // ← may land after modal guard already evaluated
}, [toast])

// Submit guard (correct, but depends on hasTrackedChanges being stable)
const canSubmit = !!file && !!targetLang && !submitting
```

<!-- detectTrackedChanges signature (from frontend/src/lib/detectTrackedChanges.ts) -->
```typescript
export async function detectTrackedChanges(file: File): Promise<boolean>
// Calls file.arrayBuffer() once per invocation — safe to call multiple times
// (no caching inside the function itself)
```

<!-- TrackedChangesModal props (from frontend/src/components/TrackedChangesModal.tsx) -->
```typescript
interface TrackedChangesModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onApply: (action: "strip" | "preserve") => void
  onCancel: () => void
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix UploadForm state-reset race + add detecting guard</name>
  <files>frontend/src/components/UploadForm.tsx</files>
  <read_first>
    - frontend/src/components/UploadForm.tsx (full file — current handleFile implementation and canSubmit guard)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, first gap, hypotheses list)
  </read_first>
  <behavior>
    - While detection is in progress, Submit button is disabled (canSubmit = false)
    - After selecting a tracked-changes DOCX a second time (same file object), modal still appears
    - After selecting a plain DOCX (no tracked changes), Submit is NOT blocked by modal guard
    - Dismissing the modal via Cancel resets file, hasTrackedChanges, and trackedAction to initial state
  </behavior>
  <action>
Add a `detecting` state boolean initialized to `false`.

In `handleFile`:
1. Before calling `detectTrackedChanges`, synchronously reset ALL four state values in a single logical block:
   ```typescript
   setFile(f)
   setTrackedAction(null)
   setHasTrackedChanges(false)
   setShowTrackedModal(false)
   setDetecting(true)
   ```
2. `await detectTrackedChanges(f)` — unchanged call
3. After the await:
   ```typescript
   setHasTrackedChanges(hasTC)
   setDetecting(false)
   ```

Change `canSubmit`:
```typescript
const canSubmit = !!file && !!targetLang && !submitting && !detecting
```

The `detecting` guard prevents the submit race: Submit is physically disabled for the ~50ms JSZip runs. This is correct UX because the file just changed — there is nothing valid to submit until detection resolves.

Do NOT change TrackedChangesModal, submitWithAction, or handleSubmit — only handleFile and canSubmit.

The existing guard `if (hasTrackedChanges && trackedAction === null)` in handleSubmit is correct and must remain unchanged.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx vitest run src/__tests__/UploadForm.test.tsx 2>&1 | tail -20</automated>
  </verify>
  <done>
    - `canSubmit` expression contains `!detecting` (grep-verifiable: `grep -n "detecting" frontend/src/components/UploadForm.tsx`)
    - `setDetecting(true)` appears before `await detectTrackedChanges` in handleFile (grep: `grep -n "setDetecting" frontend/src/components/UploadForm.tsx`)
    - `setDetecting(false)` appears after `setHasTrackedChanges(hasTC)` in handleFile
    - `setShowTrackedModal(false)` is reset in handleFile before detection runs
    - All existing vitest tests still pass (22+)
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add back-to-back upload integration test</name>
  <files>frontend/src/__tests__/UploadForm.test.tsx</files>
  <read_first>
    - frontend/src/__tests__/UploadForm.test.tsx (full file — existing test patterns, vi.hoisted usage, fireEvent.change pattern for hidden file inputs)
    - frontend/src/components/UploadForm.tsx (updated from Task 1 — detecting state is now in scope)
    - .planning/phases/01-foundation-docx-pipeline/01-UAT.md (Gaps block, first gap, `missing` list: "integration test that exercises two back-to-back uploads of the same tracked-changes DOCX")
  </read_first>
  <behavior>
    - Test: "shows modal on second upload of same tracked-changes DOCX"
      Input: mock detectTrackedChanges to return true; simulate file change twice with identical File objects
      Expected: TrackedChangesModal renders open=true both times (after each file change)
    - Test: "resets modal after cancel then re-selection"
      Input: detectTrackedChanges returns true; show modal; cancel; re-select same file
      Expected: modal opens again after re-selection (trackedAction is null, hasTrackedChanges is true again)
    - Test: "Submit disabled while detecting"
      Input: mock detectTrackedChanges with a Promise that doesn't resolve immediately (use a deferred promise)
      Expected: Submit button has `disabled` attribute while detection is pending; enabled after resolution
  </behavior>
  <action>
Add the three new tests to the existing describe block in `UploadForm.test.tsx`.

Follow the existing patterns in the file exactly:
- Use `vi.hoisted()` for mock variables (existing pattern in the file)
- Use `fireEvent.change` + `Object.defineProperty(input, 'files', { value: [mockFile] })` for file input changes (existing pattern in the file)
- The `mockDetect` vi.fn() is already hoisted — control its return value per test with `mockDetect.mockResolvedValueOnce(true)`

For the "Submit disabled while detecting" test:
```typescript
let resolveDetect!: (val: boolean) => void
mockDetect.mockImplementationOnce(() => new Promise(r => { resolveDetect = r }))
// trigger file change
// assert button disabled
resolveDetect(false)
// await act
// assert button not disabled
```

Do NOT modify existing tests. Append only.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx vitest run src/__tests__/UploadForm.test.tsx 2>&1 | tail -20</automated>
  </verify>
  <done>
    - Test count in output is ≥ 25 (was 22 + 3 new)
    - Test names present (grep-verifiable):
      `grep -n "second upload\|re-selection\|disabled while detecting" frontend/src/__tests__/UploadForm.test.tsx`
    - All tests pass (0 failed)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client file picker → UploadForm | File object from OS/browser |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-12-01 | Tampering | detectTrackedChanges | accept | Frontend-only state fix; no new auth surface. Server-side tracked-changes detection in upload.py is the authoritative path — frontend detection is defense-in-depth UX only. A spoofed File object that bypasses JSZip returns false (safe default). |
| T-12-02 | Denial of Service | handleFile (detecting state) | accept | Detection locks Submit for ~50ms (JSZip parse). Not exploitable as DoS — the user controls when they select a file. |
</threat_model>

<verification>
Run the full frontend test suite:
```bash
cd /home/thu/dev/projects/ai-translation/frontend && npx vitest run
```
Expected: all tests pass, count ≥ 25 in UploadForm.test.tsx.

Grep checks:
```bash
grep -n "detecting" frontend/src/components/UploadForm.tsx
# Must show: useState(false), setDetecting(true), setDetecting(false), !detecting in canSubmit

grep -n "second upload\|re-selection\|disabled while detecting" frontend/src/__tests__/UploadForm.test.tsx
# Must show all 3 new test names
```
</verification>

<success_criteria>
- `UploadForm.tsx` contains `const [detecting, setDetecting] = useState(false)` and `canSubmit` includes `!detecting`
- `setDetecting(true)` fires before `await detectTrackedChanges(f)` in handleFile
- `setDetecting(false)` fires after `setHasTrackedChanges(hasTC)` in handleFile
- `setShowTrackedModal(false)` is called in handleFile before detect to ensure the previous modal state doesn't carry over
- Three new tests exist in UploadForm.test.tsx covering back-to-back, cancel-then-reselect, and detecting-disabled scenarios
- All vitest tests pass (0 failures)
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-12-SUMMARY.md`
</output>
