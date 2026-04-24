# Phase 2: Review UX + Glossary - Research

**Researched:** 2026-04-24
**Domain:** Glossary CRUD + CAT-tool review UX + segment flags + export idempotency
**Confidence:** HIGH (core patterns), MEDIUM (paper skill CLI)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-02-01:** Two-table glossary schema -- `glossaries(id, name, source_lang, target_lang, created_at, updated_at)` + `glossary_terms(id, glossary_id FK CASCADE, source_term, target_term, notes, created_at)`.
- **D-02-02:** One glossary per (source_lang, target_lang) language pair.
- **D-02-03:** `(glossary_id, source_term)` unique constraint. Hard-delete only.
- **D-02-04:** CSV is the primary import path. TBX is Claude's Discretion.
- **D-02-05:** Injection via existing `glossary_to_terms()` helper in `backend/src/app/llm/terminology.py`. No call-site change.
- **D-02-06:** LLM-swap hook documented in translator module docs; no code changes.
- **D-02-07:** Post-translation check = case-insensitive substring, min 2 chars.
- **D-02-08:** Violation stored as `segment_flags` row with `details JSONB = {"term": source_term, "expected": target_term}`.
- **D-02-09:** `segment_flags(id, segment_id FK CASCADE, flag_type ENUM, severity ENUM, details JSONB, created_at)`. `flag_type` = overflow / glossary_violation / placeholder_mismatch / llm_refusal. `severity` = info / warn / block.
- **D-02-10:** Index on (segment_id, flag_type). UI counts via GROUP BY on page load.
- **D-02-11:** `segments.expansion_ratio FLOAT` (nullable), populated on translation completion.
- **D-02-12:** Thresholds in `EXPANSION_RATIO_THRESHOLDS` env var as JSON string.
- **D-02-13:** LAYOUT-02/LAYOUT-03 move to Phase 3. Phase 2 ships LAYOUT-01 + flag slot only.
- **D-02-14:** CAT-tool segment table pattern (NOT Monaco DiffEditor). shadcn Table + Textarea.
- **D-02-15:** Monaco stays in package.json for now; re-evaluate after Phase 2.
- **D-02-16:** react-virtuoso for segment table virtualization.
- **D-02-17:** Keyboard shortcuts: j/k next/prev segment, n next flag, e focus edit, r regenerate, ? toggle help panel.
- **D-02-18:** Debounce 500ms on textarea onChange -> PATCH /segments/{id}.
- **D-02-19:** Optimistic TanStack Query update -- `setQueryData(['segments', jobId], ...)` rollback + toast on error.
- **D-02-20:** Regenerate overwrites `translated_text`; `edited_text` preserved. Export uses `edited_text ?? translated_text`.
- **D-02-21:** Regenerate uses job's locked glossary.
- **D-02-22:** Export writes to `.data/jobs/{job_id}/output.docx` (overwrite). Idempotent. Advisory lock on Job.id during reassembly.
- **D-02-23:** Export button visible only on `done` or `needs_review` state.
- **D-02-24:** Single-select glossary picker on upload form (UPLD-04).
- **D-02-25:** Picker filters to matching-pair glossaries only; hides non-matching.
- **D-02-26:** `jobs.glossary_id FK glossaries(id) ON DELETE SET NULL`; locked at submit.
- **D-02-27:** Pull paper skill via `npx typeui.sh pull paper`. Roboto/Montserrat/PT Mono. Apply to new screens first.
- **D-02-28:** Primary `#111111` / secondary `#8B5CF6`. Override secondary via Tailwind if brand color specified later.

### Claude's Discretion

- CSV column order + header variants accepted
- TBX support depth (minimal term-pair extraction recommended -- see below)
- `segment_flags.severity` enum default (use `warn` for all Phase 2 flag types)
- Keyboard shortcut help panel style (? modal vs cheatsheet chip -- recommend Popover/cheatsheet)
- Exact filter bar chip layout + counts rendering
- Advisory-lock implementation for export (pg advisory lock vs in-memory -- see Section 7)
- Optimistic rollback toast copy ("Could not save -- edit restored.")
- Glossary table row density + bulk-delete UX
- Paper skill font loading strategy (next/font self-host -- see Section 9)
- Whether to rework Phase 1 screens to paper tokens in Phase 2 or defer

### Deferred Ideas (OUT OF SCOPE)

- LAYOUT-02, LAYOUT-03 (Phase 3)
- Multi-select glossaries per job (v2)
- Translation memory / segment-version history (v2)
- Per-job expansion threshold override (v2)
- Token-aware per-language tokenizers (v2)
- Full TBX-v3 import (v2)
- Soft-delete on glossary terms (v2)
- Collaborative review / auth / workspaces (v2)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GLOS-01 | Glossary CRUD: create named glossary, add term pairs | DB schema (D-02-01/02/03), REST pattern (Section 3) |
| GLOS-02 | CSV (primary) + TBX (discretion) import | stdlib `csv` module, `xml.etree.ElementTree` for TBX (Section 4) |
| GLOS-03 | Inject terms via terminology API param on every batch | Existing `glossary_to_terms()` in `terminology.py`; worker extension (Section 5) |
| GLOS-04 | Post-translation enforcement: flag violations | Case-insensitive substring check; `segment_flags` write (Section 5) |
| GLOS-05 | Glossaries listable, editable, deletable via UI | REST + shadcn Table/Dialog components (Section 3) |
| REV-01 | Side-by-side CAT-tool segment table | react-virtuoso variable-height rows; shadcn Table + Textarea (Section 6) |
| REV-02 | Inline editable segments with debounced persistence | TanStack Query optimistic mutation pattern (Section 7) |
| REV-03 | Segment-level flags visible | `segment_flags` table; FlagBadge component per flag_type (Section 5) |
| REV-04 | Single-segment regenerate button | Sync FastAPI endpoint; overwrites translated_text; edited_text untouched (Section 8) |
| REV-05 | Export reassembles with `edited_text ?? translated_text` | Reassembler extension; download trigger (Section 9) |
| REV-06 | Export is idempotent, does not mutate segments | Advisory lock on Job.id; read-snapshot pattern (Section 9) |
| LAYOUT-01 | Expansion ratio per segment, surfaced in review | `segments.expansion_ratio FLOAT`; threshold env var (Section 5) |

</phase_requirements>

---

## Summary

Phase 2 builds on Phase 1's complete DOCX pipeline by adding two demo-differentiator systems: a Postgres-backed glossary CRUD + qwen-mt-turbo injection pass, and a CAT-tool-style review UX with optimistic inline editing, per-segment regeneration, and idempotent export.

The backend work is primarily schema extension (three new tables + three column adds), worker augmentation (load glossary from DB -> inject -> post-check), and six new REST endpoints. The critical correctness invariant is that the existing `glossary_to_terms()` helper and `translator.translate_batch(..., glossary=...)` call-site are already wired; Phase 2 only needs to supply real data to those hooks.

The frontend work centers on two new routes: `/glossaries` (CRUD) and `/jobs/[id]/review` (CAT table). The review route requires three new patterns not used in Phase 1: react-virtuoso variable-height virtualization, TanStack Query v5 optimistic mutations with rollback, and keyboard shortcut management with focus-awareness via `react-hotkeys-hook`. All shadcn primitives needed are already installed except `textarea`, `input`, `popover`, and `command` (one `npx shadcn@latest add` command).

**Primary recommendation:** Build in wave order -- schema migration first, worker extension second, backend REST endpoints third, frontend glossary pages fourth, review page last. The review page depends on `PATCH /segments/{id}` and `GET /jobs/{id}/segments` being stable, so defer it to the final wave.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Glossary CRUD (create/list/edit/delete) | API / Backend | Database | Pure CRUD; no LLM involvement; frontend reads via REST |
| CSV / TBX import parsing | API / Backend | -- | File parsing is a server concern; client just POSTs the file |
| Glossary injection into translation batches | API / Backend (worker) | -- | Already wired in arq worker; just needs real glossary data |
| Post-translation violation check | API / Backend (worker) | -- | Runs in worker after batch; writes segment_flags rows |
| Expansion ratio computation | API / Backend (worker) | -- | len(target)/len(source) per segment in worker |
| Segment flags persistence | Database | -- | segment_flags table; indexed on (segment_id, flag_type) |
| Optimistic segment edit (UI) | Browser / Client | API | TanStack cache is source of truth; PATCH reconciles |
| Segment regeneration | API / Backend | Browser / Client (trigger) | Sync endpoint; single-segment translate call; returns new text |
| Export / DOCX reassembly | API / Backend | Database (read snapshot) | Reassembler reads `edited_text ?? translated_text`; writes file |
| Export advisory lock | API / Backend | -- | asyncio.Lock or pg_advisory_lock per Job.id |
| Glossary picker (upload form) | Browser / Client | API | Client fetches `/glossaries?source_lang=&target_lang=`; sent as Form field |
| Keyboard shortcut handling | Browser / Client | -- | react-hotkeys-hook; focus-aware (disabled in textarea unless e/r) |
| Virtualized segment table | Browser / Client | -- | react-virtuoso; variable row heights; overscan for smooth scroll |
| Paper skill font loading | Frontend Server (SSR) | -- | next/font/google loaded in root layout.tsx; CSS vars injected server-side |

---

## Standard Stack

### Core (extends Phase 1 stack -- no new backend infra)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `react-virtuoso` | 4.18.6 | Variable-height list virtualization | Only React virtualizer with native variable-height + scrollIntoView API; react-window requires fixed heights |
| `react-hotkeys-hook` | 5.2.4 | Keyboard shortcut management | Declarative, focus-aware; disabled in form tags by default (perfect for textarea guard); v5 is React 19 compatible |
| Python `csv` (stdlib) | built-in | CSV glossary import parsing | Zero new dependency; handles quoting, encoding, delimiter variants per RFC 4180 |
| `xml.etree.ElementTree` (stdlib) | built-in | TBX minimal import (Claude's Discretion) | Zero new dependency; TBX-Core is valid XML; full TBX-v3 deferred to v2 |

[VERIFIED: npm registry -- react-virtuoso 4.18.6 published 2026-04-24; react-hotkeys-hook 5.2.4 published 2026-02-02]

### Supporting (new shadcn components)

| Component | Install | Purpose | Notes |
|-----------|---------|---------|-------|
| shadcn `textarea` | `npx shadcn@latest add textarea` | Target cell in segment row | Styled shadcn wrapper over native textarea |
| shadcn `input` | `npx shadcn@latest add input` | Glossary term add/edit fields | Styled input |
| shadcn `popover` | `npx shadcn@latest add popover` | Keyboard help panel, regenerate confirm | Radix Popover already in node_modules (used by Select internally) |
| shadcn `command` | `npx shadcn@latest add command` | Glossary picker combobox (optional) | If Select is insufficient for searchability; can defer |

[VERIFIED: npm registry -- all in shadcn official registry; `@radix-ui/react-popover` already installed per package.json scan]

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `react-hotkeys-hook` | Native `window.addEventListener('keydown', ...)` | Native: no new dep; but managing focus guards, cleanup, and React 19 Strict Mode double-invoke is fiddly. react-hotkeys-hook handles all three in 3 lines. |
| `react-virtuoso` | `@tanstack/react-virtual` | TanStack Virtual: lower-level, more control, but requires manual height measurement wiring. Virtuoso handles variable heights automatically. |
| `csv` stdlib | `pandas` | pandas would add ~50MB to Docker image. Stdlib csv is sufficient for PoC glossary files. |
| TBX via `xml.etree.ElementTree` | `lxml` | lxml is already in PaddleOCR's dep tree but not backend's. ElementTree is sufficient for minimal TBX-Core extraction. |

**Installation (frontend):**
```bash
cd frontend
npm install react-virtuoso react-hotkeys-hook
npx shadcn@latest add textarea input popover command
```

**Installation (backend -- no new packages needed):**
```bash
# csv and xml.etree.ElementTree are Python stdlib
# All other Phase 2 backend work uses existing deps
```

---

## Architecture Patterns

### System Architecture Diagram

```
GLOSSARY CRUD FLOW
  Browser
    POST /glossaries                    --> create glossary row
    POST /glossaries/{id}/terms         --> add/edit terms
    POST /glossaries/{id}/terms/import  --> CSV/TBX file upload
                  |
                  v
            FastAPI (sync REST)
                  |
                  v
            PostgreSQL: glossaries + glossary_terms tables

UPLOAD + TRANSLATION FLOW (Phase 2 extension)
  Browser
    POST /upload (file + source_lang + target_lang + glossary_id?)
                  |
                  v
            FastAPI: create Job with glossary_id FK
                  |
                  v
            arq Queue (enqueue translate_job)
                  |
                  v
            Worker: load glossary_terms --> dict[str, str]
                  |
                  +-- translate_batch_with_retry(glossary=terms_dict)
                  |           |
                  |           v
                  |     qwen-mt-turbo (terminology param injected)
                  |
                  +-- post_check: violation scan --> write segment_flags rows
                  |
                  +-- expansion_ratio: len(target)/len(source)
                  |    segment.expansion_ratio written per segment
                  |    if ratio > threshold --> write overflow segment_flag
                  |
                  +-- reassemble DOCX --> output.docx
                  |
                  v
            Redis pub/sub: publish final status
                  |
                  v
            Browser (SSE): job transitions to "needs_review" or "done"

REVIEW UX FLOW
  Browser /jobs/[id]/review
    GET /jobs/{id}/segments --> TanStack cache ['segments', jobId]
                  |
                  v
            SegmentTable (react-virtuoso)
              each SegmentRow:
                textarea onChange (debounce 500ms)
                       |
                       v
                   PATCH /segments/{id} (edited_text)
                       | optimistic: setQueryData immediately
                       | error: rollback + toast
                       v
                   PostgreSQL: segments.edited_text
              FlagCell: FlagBadge per flag in segment.flags
              RegenerateButton --> POST /segments/{id}/regenerate
                                     |
                                     v
                                 sync endpoint: translate 1 segment
                                     overwrites translated_text
                                     returns new translated_text
              ExportButton --> POST /jobs/{id}/export
                                  | advisory lock on Job.id
                                  v
                              reassembler(edited_text ?? translated_text)
                                  |
                                  v
                              output.docx (overwrite) --> FileResponse download
```

### Recommended Project Structure (Phase 2 additions)

```
backend/src/app/
+-- api/routes/
|   +-- glossaries.py        # REPLACE stub -- full CRUD + terms + import
|   +-- segments.py          # NEW -- PATCH, GET list, POST regenerate
|   +-- export.py            # NEW -- POST /jobs/{id}/export
+-- db/
|   +-- models.py            # EXTEND -- Glossary, GlossaryTerm, SegmentFlag; column adds
|   +-- migrations/versions/
|       +-- 0002_phase2_glossary_flags.py  # NEW -- single migration file
+-- pipeline/
|   +-- docx/
|       +-- reassembler.py   # EXTEND -- use edited_text ?? translated_text
+-- services/
|   +-- job_service.py       # EXTEND -- create_job accepts glossary_id
|   +-- glossary_service.py  # NEW -- DB CRUD helpers + CSV/TBX parsers
|   +-- export_service.py    # NEW -- advisory lock + reassemble + write file
+-- workers/
    +-- translate_worker.py  # EXTEND -- load glossary; post-check; expansion ratio

frontend/src/
+-- app/
|   +-- glossaries/
|   |   +-- page.tsx         # NEW -- glossary list
|   |   +-- [id]/page.tsx    # NEW -- glossary detail + terms table
|   +-- jobs/[id]/
|   |   +-- page.tsx         # KEEP -- status page (add Review link when terminal)
|   |   +-- review/page.tsx  # NEW -- CAT-tool segment table
|   +-- layout.tsx           # EXTEND -- add 3 paper fonts
+-- components/
|   +-- UploadForm.tsx        # EXTEND -- add GlossarySelect
|   +-- GlossarySelect.tsx   # NEW
|   +-- FlagBadge.tsx        # NEW
|   +-- SegmentTable.tsx     # NEW -- react-virtuoso wrapper
|   +-- SegmentRow.tsx       # NEW
|   +-- ReviewFilterBar.tsx  # NEW
|   +-- ReviewPageHeader.tsx # NEW
|   +-- KeyboardHelpPanel.tsx# NEW
|   +-- glossary/
|       +-- GlossaryList.tsx
|       +-- GlossaryCreateDialog.tsx
|       +-- TermsTable.tsx
|       +-- CSVUploadButton.tsx
+-- hooks/
|   +-- useSegments.ts       # NEW -- TanStack Query ['segments', jobId] + optimistic PATCH
|   +-- useSegmentFlags.ts   # NEW -- per-segment flag count query
+-- lib/
    +-- types.ts             # EXTEND -- Segment, SegmentFlag, Glossary, GlossaryTerm types
```

---

## Section 1: TanStack Query v5 Optimistic Mutations (REV-02)

### Pattern: Segment PATCH with cache rollback

[VERIFIED: context7.com/tanstack/query -- optimistic-updates.md]

The correct v5 pattern for segment edits. Key difference from v4: `onMutate` receives the new variables as its first argument (not via a context object). The return value from `onMutate` becomes `context` passed to `onError`/`onSettled`.

```typescript
// hooks/useSegments.ts
import { useMutation, useQueryClient, useQuery } from "@tanstack/react-query"

interface Segment {
  id: string
  seq_in_job: number
  source_text: string
  translated_text: string | null
  edited_text: string | null
  expansion_ratio: number | null
  flags: SegmentFlag[]
}

function useSegmentPatch(jobId: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ segmentId, editedText }: { segmentId: string; editedText: string | null }) => {
      const res = await fetch(`/api/segments/${segmentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edited_text: editedText }),
      })
      if (!res.ok) throw new Error("Save failed")
      return res.json()
    },

    onMutate: async ({ segmentId, editedText }) => {
      // Cancel outgoing refetches (prevent overwriting optimistic state)
      await queryClient.cancelQueries({ queryKey: ["segments", jobId] })

      // Snapshot previous state for rollback
      const previousSegments = queryClient.getQueryData<Segment[]>(["segments", jobId])

      // Optimistically update the cache
      queryClient.setQueryData<Segment[]>(["segments", jobId], (old) =>
        old?.map((seg) =>
          seg.id === segmentId ? { ...seg, edited_text: editedText } : seg
        ) ?? []
      )

      // Return snapshot -- becomes `context` in onError/onSettled
      return { previousSegments }
    },

    onError: (_err, _vars, context) => {
      // Rollback to snapshot
      if (context?.previousSegments) {
        queryClient.setQueryData(["segments", jobId], context.previousSegments)
      }
      toast({ title: "Could not save -- edit restored.", variant: "destructive" })
    },

    onSettled: () => {
      // Refetch to sync with server truth after error or success
      queryClient.invalidateQueries({ queryKey: ["segments", jobId] })
    },
  })
}
```

**Critical notes:**
- `cancelQueries` MUST run before `setQueryData` in `onMutate` to prevent a pending refetch from overwriting the optimistic state
- `onSettled` invalidation after success is safe (triggers a refetch but the user sees instant feedback)
- For debounce: implement in `TargetCell` with `useRef` + `setTimeout`; cancel on unmount

### Debounce pattern in TargetCell

```typescript
// components/SegmentRow.tsx
const debounceRef = useRef<ReturnType<typeof setTimeout>>()

const handleChange = (value: string) => {
  setLocalValue(value)  // instant local state for smooth typing
  clearTimeout(debounceRef.current)
  debounceRef.current = setTimeout(() => {
    patchMutation.mutate({ segmentId: segment.id, editedText: value })
  }, 500)  // D-02-18: 500ms debounce
}

useEffect(() => () => clearTimeout(debounceRef.current), [])
```

---

## Section 2: react-virtuoso Variable-Height Rows (REV-01)

### Verified pattern: variable-height Virtuoso with scrollIntoView

[VERIFIED: context7 /petyosi/react-virtuoso -- auto-resizing.md + keyboard-navigation.md]

react-virtuoso 4.x handles variable heights automatically -- no `estimatedItemSize` needed. The `Virtuoso` component measures each rendered item and adjusts the scroll container accordingly. For keyboard navigation (j/k), use `ref.current.scrollIntoView({ index, behavior: 'auto' })`.

```typescript
// components/SegmentTable.tsx
"use client"
import { Virtuoso, VirtuosoHandle } from "react-virtuoso"
import { useRef, useCallback } from "react"

interface SegmentTableProps {
  segments: Segment[]
  focusedIndex: number
  onFocusChange: (index: number) => void
}

export function SegmentTable({ segments, focusedIndex, onFocusChange }: SegmentTableProps) {
  const virtuosoRef = useRef<VirtuosoHandle>(null)

  const scrollToIndex = useCallback((index: number) => {
    virtuosoRef.current?.scrollIntoView({ index, behavior: "auto" })
    onFocusChange(index)
  }, [onFocusChange])

  return (
    <Virtuoso
      ref={virtuosoRef}
      style={{ height: "calc(100vh - 168px)" }}  // 168px = nav(56) + review header(64) + filter bar(48)
      data={segments}
      increaseViewportBy={{ top: 300, bottom: 500 }}  // pre-render ahead for smooth j/k nav
      itemContent={(index, segment) => (
        <SegmentRow
          segment={segment}
          isFocused={index === focusedIndex}
          onFocus={() => onFocusChange(index)}
        />
      )}
    />
  )
}
```

**Key config:**
- `style={{ height: "calc(100vh - 168px)" }}` -- Virtuoso MUST have an explicit height. `168px = 56px nav + 64px review header + 48px filter bar`
- `increaseViewportBy={{ top: 300, bottom: 500 }}` -- pre-renders 500px below visible area so j/k navigation feels instant. `bottom > top` because users scroll down.
- No `overscan` prop in v4 -- replaced by `increaseViewportBy`

**Common pitfall:** Wrapping Virtuoso in a `<div style={{ flex: 1 }}>` without giving it an explicit height causes the container to collapse to 0px. Set height explicitly via calc.

---

## Section 3: Keyboard Shortcut Handling (D-02-17)

### Verified pattern: react-hotkeys-hook with focus guard

[VERIFIED: context7 /johannesklauss/react-hotkeys-hook -- disable-hotkeys.mdx + scoping-hotkeys.mdx]

react-hotkeys-hook v5 disables hotkeys when a form element has focus by default. For the review page:
- j/k/n/e/r/?: disabled when focus is inside any textarea or input (default behavior = correct)
- e: fires outside textarea, then programmatically focuses the textarea
- Escape: enabled in textarea to blur and return focus to the row

```typescript
// hooks/useReviewKeyboard.ts
import { useHotkeys } from "react-hotkeys-hook"

export function useReviewKeyboard({
  focusedIndex,
  segmentCount,
  flaggedIndices,
  onNext,
  onPrev,
  onNextFlag,
  onEdit,
  onRegenerate,
  onToggleHelp,
}: ReviewKeyboardOptions) {
  // j/k/n/e/r/? -- disabled in form tags (react-hotkeys-hook default)
  useHotkeys("j", () => onNext(Math.min(focusedIndex + 1, segmentCount - 1)),
    { preventDefault: true })

  useHotkeys("k", () => onPrev(Math.max(focusedIndex - 1, 0)),
    { preventDefault: true })

  useHotkeys("n", () => {
    const next = flaggedIndices.find(i => i > focusedIndex) ?? flaggedIndices[0]
    if (next !== undefined) onNext(next)
  }, { preventDefault: true })

  useHotkeys("e", () => onEdit(focusedIndex), { preventDefault: true })
  useHotkeys("r", () => onRegenerate(focusedIndex), { preventDefault: true })
  useHotkeys("?", () => onToggleHelp(), { preventDefault: true })

  // Escape: enabled in textarea to blur
  useHotkeys("escape", () => { (document.activeElement as HTMLElement)?.blur() },
    { enableOnFormTags: ["textarea"] })
}
```

**Focus guard strategy:**
- `useHotkeys` default: `enableOnFormTags` is undefined (= disabled in form tags) -- correct for j/k/n
- Only `escape` needs `enableOnFormTags: ["textarea"]` to fire when textarea is focused
- `e` key fires outside textarea -> programmatically calls `textareaRef.current?.focus()`

**Phase 1 precedent:** Phase 1 has no keyboard shortcuts. react-hotkeys-hook is a new dep for Phase 2.

---

## Section 4: CSV and TBX Import (GLOS-02)

### CSV parsing: stdlib csv module

[VERIFIED: Python stdlib -- csv module is built-in, no install needed]

CSV import is the primary path. The parser should accept header variants to handle Excel exports and variations:

```python
# backend/src/app/services/glossary_service.py

import csv
import io

HEADER_VARIANTS: dict[str, set[str]] = {
    "source_term": {"source_term", "source", "src", "Source Term", "Source"},
    "target_term": {"target_term", "target", "tgt", "Target Term", "Target"},
    "notes": {"notes", "note", "comment", "Notes"},
}

def parse_csv_glossary(file_content: bytes, encoding: str = "utf-8-sig") -> list[dict]:
    """
    Parse CSV glossary file. Accepts header variants.
    utf-8-sig strips BOM from Excel-exported CSV.
    Returns list of {"source_term": str, "target_term": str, "notes": str | None}
    Raises ValueError with row number on parse error.
    """
    text = file_content.decode(encoding, errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ValueError("CSV has no header row")

    # Normalize headers
    field_map: dict[str, str] = {}
    for field in reader.fieldnames:
        if field is None:
            continue
        for canonical, variants in HEADER_VARIANTS.items():
            if field.strip() in variants:
                field_map[field] = canonical
                break

    if "source_term" not in field_map.values() or "target_term" not in field_map.values():
        raise ValueError(
            "CSV must have 'source_term'/'source' and 'target_term'/'target' columns"
        )

    terms: list[dict] = []
    for row_num, row in enumerate(reader, start=2):  # start=2: row 1 is header
        src = (row.get(field_map.get("source_term", "")) or "").strip()
        tgt = (row.get(field_map.get("target_term", "")) or "").strip()
        notes = (row.get(field_map.get("notes", "")) or "").strip() or None

        if not src or not tgt:
            raise ValueError(f"Row {row_num}: source_term and target_term are required")
        if len(src) < 2 or len(tgt) < 2:
            raise ValueError(f"Row {row_num}: terms must be at least 2 characters (D-02-07)")

        terms.append({"source_term": src, "target_term": tgt, "notes": notes})

    return terms
```

**Duplicate handling (per UI-SPEC copywriting):** After bulk insert, count rows that violated the `(glossary_id, source_term)` unique constraint and return `{"imported": N, "skipped_duplicates": M}`.

### TBX minimal parsing (Claude's Discretion -- recommend implementing)

TBX-Core is valid XML. A minimal extractor reads `termEntry` -> `langSet xml:lang` -> `tig/term` triples. This is ~30 lines of stdlib XML and zero new deps. Recommended even though it's Claude's Discretion, because CAT tool users (Trados, memoQ, OmegaT) export glossaries as TBX.

```python
import xml.etree.ElementTree as ET

def parse_tbx_minimal(file_content: bytes, source_lang: str, target_lang: str) -> list[dict]:
    """
    Minimal TBX-Core extraction: termEntry -> (source_lang term, target_lang term).
    Supports TBX-Core and TBX-Basic. Ignores full TBX-v3 metadata.
    Returns same shape as parse_csv_glossary for uniform downstream handling.
    """
    parser = ET.XMLParser()  # ElementTree does not expand external entities by default
    root = ET.fromstring(file_content, parser=parser)
    terms: list[dict] = []

    for entry in root.iter("termEntry"):
        lang_terms: dict[str, str] = {}
        for lang_set in entry.iter("langSet"):
            lang = lang_set.get("{http://www.w3.org/XML/1998/namespace}lang", "")
            for tig in lang_set.iter("tig"):
                term_el = tig.find("term")
                if term_el is not None and term_el.text:
                    lang_terms[lang.lower()] = term_el.text.strip()
            # ntig format (TBX-Basic)
            for ntig in lang_set.iter("ntig"):
                term_grp = ntig.find("termGrp")
                if term_grp is not None:
                    term_el = term_grp.find("term")
                    if term_el is not None and term_el.text:
                        lang_terms[lang.lower()] = term_el.text.strip()

        src = lang_terms.get(source_lang.lower())
        tgt = lang_terms.get(target_lang.lower())
        if src and tgt and len(src) >= 2 and len(tgt) >= 2:
            terms.append({"source_term": src, "target_term": tgt, "notes": None})

    return terms
```

---

## Section 5: Worker Extension + Flags (GLOS-03, GLOS-04, LAYOUT-01)

### Glossary load in worker

The worker's `_translate_one_batch` call currently passes `glossary=None` (Phase 1 placeholder at line 323 of translate_worker.py). Phase 2 changes this one line to pass real data:

```python
# In _run_translation(), before the batch loop:
from app.services.glossary_service import load_glossary_terms_for_job

glossary: dict[str, str] | None = await load_glossary_terms_for_job(session, job.glossary_id)

# Then in _translate_one_batch():
glossary=glossary,   # replaces: glossary=None
```

```python
# glossary_service.py
async def load_glossary_terms_for_job(
    session: AsyncSession, glossary_id: str | None
) -> dict[str, str] | None:
    """Load {source_term: target_term} dict for the job's glossary. Returns None if no glossary."""
    if glossary_id is None:
        return None
    result = await session.execute(
        select(GlossaryTerm.source_term, GlossaryTerm.target_term)
        .where(GlossaryTerm.glossary_id == glossary_id)
    )
    rows = result.all()
    if not rows:
        return None
    return {row.source_term: row.target_term for row in rows}
```

### Post-translation violation check (GLOS-04)

Run per-batch after `translated_map` is populated with all results for the batch. This batches all DB writes into one `flush()` per batch instead of one per segment.

```python
async def run_post_check(
    session: AsyncSession,
    batch_segs: list[Segment],
    translated_map: dict[str, str],
    glossary: dict[str, str] | None,
    source_lang: str,
    target_lang: str,
    expansion_thresholds: dict[str, float],
) -> None:
    """
    For each translated segment:
    1. Check expansion ratio -> write overflow flag if above threshold (LAYOUT-01)
    2. Check each glossary term -> write glossary_violation flag (GLOS-04)
    """
    lang_pair = f"{source_lang.lower()}->{target_lang.lower()}"
    expansion_threshold = expansion_thresholds.get(lang_pair, 1.5)  # default 1.5

    flags_to_insert: list[SegmentFlag] = []

    for seg in batch_segs:
        translated = translated_map.get(seg.id)
        if translated is None:
            continue

        # LAYOUT-01: expansion ratio
        if len(seg.source_text) > 0:
            ratio = len(translated) / len(seg.source_text)
            await session.execute(
                update(Segment)
                .where(Segment.id == seg.id)
                .values(expansion_ratio=ratio)
            )
            if ratio > expansion_threshold:
                flags_to_insert.append(SegmentFlag(
                    segment_id=seg.id,
                    flag_type=FlagType.overflow,
                    severity=FlagSeverity.warn,
                    details={"ratio": ratio, "threshold": expansion_threshold},
                ))

        # GLOS-04: violation check -- case-insensitive substring, min 2 chars (D-02-07)
        if glossary:
            translated_lower = translated.lower()
            for src_term, tgt_term in glossary.items():
                if len(tgt_term) < 2:
                    continue  # D-02-07: skip sub-2-char terms to avoid spurious matches
                if tgt_term.lower() not in translated_lower:
                    flags_to_insert.append(SegmentFlag(
                        segment_id=seg.id,
                        flag_type=FlagType.glossary_violation,
                        severity=FlagSeverity.warn,
                        details={"term": src_term, "expected": tgt_term},
                    ))

    if flags_to_insert:
        session.add_all(flags_to_insert)
        await session.flush()
```

**Performance note:** Per-batch (not per-segment) is correct. 10K segments across ~50 batches = 50 DB writes vs 10K writes.

### Expansion ratio thresholds

```python
# config.py addition
class Settings(BaseSettings):
    expansion_ratio_thresholds: str = Field(
        default='{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}',
        description="JSON map of lang-pair to expansion ratio threshold"
    )

    @property
    def expansion_thresholds_dict(self) -> dict[str, float]:
        import json
        return json.loads(self.expansion_ratio_thresholds)
```

---

## Section 6: Database Schema (Alembic Migration)

### New tables and column adds

One migration file for all Phase 2 changes (single file is correct -- all changes belong to the same logical upgrade):

```python
# migrations/versions/0002_phase2_glossary_flags.py

def upgrade() -> None:
    # glossaries table
    op.create_table(
        "glossaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_lang", sa.String(64), nullable=False),
        sa.Column("target_lang", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # glossary_terms table
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("glossary_id", sa.String(36),
                  sa.ForeignKey("glossaries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_term", sa.Text, nullable=False),
        sa.Column("target_term", sa.Text, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_glossary_terms_source", "glossary_terms", ["glossary_id", "source_term"])
    op.create_index("ix_glossary_terms_glossary_id", "glossary_terms", ["glossary_id"])

    # segment_flags table
    op.create_table(
        "segment_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("segment_id", sa.String(16),
                  sa.ForeignKey("segments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flag_type",
                  sa.Enum("overflow", "glossary_violation", "placeholder_mismatch", "llm_refusal",
                          name="flagtype", native_enum=False),  # native_enum=False for SQLite test compat
                  nullable=False),
        sa.Column("severity",
                  sa.Enum("info", "warn", "block",
                          name="flagseverity", native_enum=False),
                  nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_segment_flags_segment_flag", "segment_flags", ["segment_id", "flag_type"])

    # jobs: add glossary_id FK
    op.add_column("jobs", sa.Column("glossary_id", sa.String(36), nullable=True))
    op.create_foreign_key(
        "fk_jobs_glossary_id", "jobs", "glossaries",
        ["glossary_id"], ["id"], ondelete="SET NULL")

    # segments: add edited_text, expansion_ratio
    op.add_column("segments", sa.Column("edited_text", sa.Text, nullable=True))
    op.add_column("segments", sa.Column("expansion_ratio", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("segments", "expansion_ratio")
    op.drop_column("segments", "edited_text")
    op.drop_constraint("fk_jobs_glossary_id", "jobs", type_="foreignkey")
    op.drop_column("jobs", "glossary_id")
    op.drop_index("ix_segment_flags_segment_flag")
    op.drop_table("segment_flags")
    op.drop_index("ix_glossary_terms_glossary_id")
    op.drop_constraint("uq_glossary_terms_source", "glossary_terms", type_="unique")
    op.drop_table("glossary_terms")
    op.drop_table("glossaries")
    # native_enum=False means no separate PostgreSQL TYPE was created -- no DROP TYPE needed
```

**SQLite compatibility:** Using `native_enum=False` serializes enum values as VARCHAR in both SQLite and PostgreSQL. This avoids the `CREATE TYPE` statement that breaks SQLite in unit tests. The existing conftest.py uses `sqlite+aiosqlite:///:memory:` for unit tests.

---

## Section 7: Export Idempotency + Advisory Lock (REV-05, REV-06)

### Advisory lock decision (Claude's Discretion)

Two valid options:

| Option | Implementation | Pros | Cons |
|--------|---------------|------|------|
| `asyncio.Lock` per job_id | In-process dict of Lock objects | Simple; no DB round-trip | Not process-safe across multiple API workers |
| `pg_advisory_lock` | Raw SQL `SELECT pg_advisory_lock(hashtext(job_id))` | Process-safe | Ties a DB connection for the lock duration |

**Recommendation: `asyncio.Lock` in-process dict** for Phase 2.

Rationale: Export is triggered from the FastAPI API process. With a single uvicorn process (PoC default), in-memory lock is safe and adds zero complexity. Document the pg_advisory_lock upgrade path with a TODO comment.

```python
# services/export_service.py
import asyncio
from weakref import WeakValueDictionary

# In-process advisory lock per job_id (sufficient for single-process API)
# TODO(v2): upgrade to pg_advisory_lock if deploying multiple API workers
_export_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
_locks_mutex = asyncio.Lock()

async def get_export_lock(job_id: str) -> asyncio.Lock:
    async with _locks_mutex:
        lock = _export_locks.get(job_id)
        if lock is None:
            lock = asyncio.Lock()
            _export_locks[job_id] = lock
        return lock

async def export_job(session: AsyncSession, job_id: str, data_dir: str) -> str:
    """
    Idempotent: reads edited_text ?? translated_text snapshot; writes output.docx.
    Does NOT mutate segment rows (REV-06).
    Returns the output file path.
    """
    lock = await get_export_lock(job_id)
    async with lock:
        job = await get_job(session, job_id)
        if job is None or job.status not in (JobStatus.done, JobStatus.needs_review):
            raise ValueError("Job not in exportable state")

        result = await session.execute(
            select(Segment)
            .where(Segment.job_id == job_id)
            .order_by(Segment.seq_in_job)
        )
        segments = result.scalars().all()

        # Build translated_texts map: edited_text ?? translated_text (D-02-20)
        # Use explicit None check, not `or`, to handle edge case of empty string edit
        translated_map = {
            seg.id: (seg.edited_text if seg.edited_text is not None else seg.translated_text or "")
            for seg in segments
            if (seg.edited_text is not None or seg.translated_text)
        }

        from docx import Document
        doc = Document(job.input_path)
        doc = reassemble_docx_runs(doc, list(segments), translated_map)

        output_path = str(Path(data_dir) / "jobs" / job_id / "output.docx")
        doc.save(output_path)
        return output_path
```

### Download trigger (frontend)

```typescript
// In ReviewPageHeader.tsx
async function handleExport() {
  setIsExporting(true)
  try {
    const res = await fetch(`/api/jobs/${jobId}/export`, { method: "POST" })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unknown error" }))
      throw new Error(err.detail)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `${job.original_filename.replace(".docx", "")}_translated.docx`
    a.click()
    URL.revokeObjectURL(url)
    toast({ title: "Export ready -- downloading." })
  } catch (e) {
    toast({ title: `Export failed -- ${(e as Error).message}. Try again.`, variant: "destructive" })
  } finally {
    setIsExporting(false)
  }
}
```

**FastAPI route streams the file:**
```python
from fastapi.responses import FileResponse

@router.post("/jobs/{job_id}/export")
async def export_document(
    job_id: str,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    output_path = await export_service.export_job(session, job_id, settings.data_dir)
    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=Path(output_path).name,
    )
```

---

## Section 8: Single-Segment Regenerate (REV-04)

### Decision: synchronous FastAPI endpoint (not arq)

A single segment is at most ~500 input tokens. qwen-mt-turbo latency for a short segment is ~1-3 seconds. This is well within acceptable HTTP response time for an interactive action. Enqueueing via arq would require SSE or polling for the result -- adding ~500ms overhead and significant complexity for no quality gain.

```python
# api/routes/segments.py

@router.post("/segments/{segment_id}/regenerate")
async def regenerate_segment(
    segment_id: str,
    session: AsyncSession = Depends(get_session),
    llm_client: AsyncOpenAI = Depends(get_llm_client),
) -> dict:
    """
    Synchronously re-translate one segment.
    D-02-20: overwrites translated_text; edited_text is NOT touched.
    D-02-21: uses job's locked glossary.
    """
    seg = await get_segment(session, segment_id)
    if seg is None:
        raise HTTPException(status_code=404, detail="Segment not found")

    job = await get_job(session, seg.job_id)
    if job is None or job.status not in (JobStatus.done, JobStatus.needs_review):
        raise HTTPException(status_code=409, detail="Job not in reviewable state")

    glossary = await load_glossary_terms_for_job(session, job.glossary_id)

    # Single-segment batch -- no token budget partitioning needed
    translated_list = await translate_batch(
        client=llm_client,
        segments=[seg.source_text],
        source_lang=job.source_lang,
        target_lang=job.target_lang,
        glossary=glossary,
    )
    new_translated_text = translated_list[0]

    # Update translated_text ONLY -- never touch edited_text (D-02-20)
    await session.execute(
        update(Segment)
        .where(Segment.id == segment_id)
        .values(translated_text=new_translated_text)
    )
    await session.commit()

    return {"segment_id": segment_id, "translated_text": new_translated_text}
```

**PATCH endpoint validation notes:**
- `edited_text` max length: 10,000 characters
- `edited_text=None` is valid (clears the edit; reverts to `translated_text` on export)
- No 409 conflict for concurrent edits -- last write wins (PoC: single reviewer)

---

## Section 9: Paper Skill + Font Loading (D-02-27/28)

### typeui.sh pull paper workflow

[ASSUMED -- CLI version 0.1.0 confirmed; exact pull behavior not verified end-to-end]

The CLI is interactive (TUI). Wave 0 of the plan must include an explicit step:
```bash
cd /home/thu/dev/projects/ai-translation
npx typeui.sh pull paper
# When prompted, select: SKILL.md (provider-specific paths)
# Commit the output SKILL.md before starting any Phase 2 frontend work
```

If the CLI proves non-interactive-compatible, the fallback is to apply UI-SPEC paper tokens directly to `tailwind.config.ts` and `layout.tsx` manually (all tokens are documented in `02-UI-SPEC.md` §Typography and §Color).

### Font loading: next/font/google (self-host)

[VERIFIED: UI-SPEC code snippet + Next.js 16 backward-compatible font API]

`next/font/google` downloads fonts at build time and serves them from the same origin -- no Google Fonts CDN request at runtime. This is correct for the internal demo (no third-party network dependency on demo day).

```typescript
// frontend/src/app/layout.tsx -- additions to existing layout
import { Roboto, Montserrat, PT_Mono } from "next/font/google"

const roboto = Roboto({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-roboto",
  display: "swap",
})

const montserrat = Montserrat({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-montserrat",
  display: "swap",
})

const ptMono = PT_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pt-mono",
  display: "swap",
})
// Apply: className={`${roboto.variable} ${montserrat.variable} ${ptMono.variable}`} on <html>
```

**Tailwind config additions:**
```typescript
// frontend/tailwind.config.ts -- fontFamily extension
fontFamily: {
  sans: ["var(--font-roboto)", "system-ui", "sans-serif"],
  heading: ["var(--font-montserrat)", "system-ui", "sans-serif"],
  mono: ["var(--font-pt-mono)", "ui-monospace", "monospace"],
}
```

**Vietnamese subset note:** Roboto and Montserrat include the `"vietnamese"` subset. PT Mono only has `"latin"` -- Vietnamese diacritics in source cells (displayed in PT Mono per D-02-27) will fall back to the system font for unsupported glyphs. This is acceptable for the PoC demo.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Variable-height virtual list | Custom virtualizer | `react-virtuoso` | Intersection Observer + height measurement + scroll sync is ~500 lines of bug-prone code |
| Keyboard shortcuts with focus guards | `window.addEventListener('keydown', ...)` | `react-hotkeys-hook` | React 19 Strict Mode double-fires effects; cleanup across re-renders is error-prone |
| Optimistic cache with rollback | Manual state machine | TanStack Query useMutation + onMutate/onError | TanStack handles race conditions (cancelQueries), concurrent mutations, and retry semantics |
| CSV quoting + BOM handling | Manual string splitting | Python `csv.DictReader` | CSV edge cases (quoted commas, CRLF, BOM from Excel) require RFC 4180 parsing |
| Export lock across concurrent requests | Per-request flag | `asyncio.Lock` per job_id | Without a lock, two concurrent export requests can produce a torn output.docx |
| Post-check for all terms | Regex per-term | `.lower() in str.lower()` | Simple substring is correct and fast for under 100 terms; regex adds no value and requires escaping |

**Key insight:** The review UX complexity lives in state management and virtualization, not in domain logic. TanStack + Virtuoso handle the hard parts; the domain code is straightforward PATCH + `edited_text ?? translated_text` logic.

---

## Common Pitfalls

### Pitfall 1: react-virtuoso requires explicit height

**What goes wrong:** `<Virtuoso>` with no fixed height collapses to 0px and renders nothing (no error thrown).
**Why it happens:** Virtuoso measures the scroll container to determine what to render. Without a height, it sees 0px and renders 0 items.
**How to avoid:** Always set `style={{ height: "calc(100vh - Npx)" }}` or wrap in a div with an explicit pixel height.
**Warning signs:** Virtuoso renders 0 rows despite `data` being non-empty.

### Pitfall 2: TanStack v5 onMutate context shape differs from v4

**What goes wrong:** Accessing `context.client.setQueryData(...)` inside `onMutate` -- `context.client` does not exist in v5. Many online examples are v4.
**Why it happens:** v5 changed callback signatures. `onMutate` receives `(variables)` and its return value becomes `context` in `onError`/`onSettled`.
**How to avoid:** Use `const queryClient = useQueryClient()` outside the mutation definition; capture it via closure. Return snapshot from `onMutate`; destructure as `context?.previousSegments` in `onError`.
**Warning signs:** TypeScript error on `context.client` or `TypeError: context.client is undefined` at runtime.

### Pitfall 3: Alembic named ENUMs not dropped on downgrade

**What goes wrong:** `alembic downgrade` fails with "type flagtype still exists" if `drop_table` runs but the named ENUM is not dropped.
**Why it happens:** With `native_enum=True` (default), PostgreSQL creates an independent TYPE object. Alembic does not auto-drop it in all cases.
**How to avoid:** Use `native_enum=False` (as specified in Section 6). This avoids the issue entirely -- no separate TYPE is created.
**Warning signs:** `alembic downgrade` raises `ProgrammingError: type "flagtype" still exists`.

### Pitfall 4: Optimistic update overwritten by background refetch

**What goes wrong:** User edits a segment cell; the optimistic update renders immediately; a background refetch overwrites the cache with the prior server state before the PATCH completes.
**Why it happens:** `useQuery` with `staleTime: 0` refetches on window focus; if the refetch returns before the PATCH completes, it overwrites the optimistic state.
**How to avoid:** Call `queryClient.cancelQueries({ queryKey: ['segments', jobId] })` inside `onMutate` before `setQueryData`. Set `staleTime: 30_000` on the segments query to reduce refetch frequency.
**Warning signs:** Edited text flickers back to the previous value ~1-2 seconds after typing.

### Pitfall 5: `edited_text ?? translated_text` with empty string

**What goes wrong:** In Python, `seg.edited_text or seg.translated_text` returns `translated_text` even when `edited_text` is `""` (empty string is falsy). A user who deliberately clears a segment would have their change silently dropped on export.
**Why it happens:** Python `or` is falsy-based; `"" or "translated"` evaluates to `"translated"`.
**How to avoid:** Use explicit None check: `seg.edited_text if seg.edited_text is not None else seg.translated_text`. The column is nullable; `NULL` = no edit; empty string = the user explicitly cleared the text.
**Warning signs:** An empty edit field on a segment produces the original translation in the exported document.

### Pitfall 6: CSV encoding BOM from Excel

**What goes wrong:** Excel exports CSV with UTF-8 BOM (`0xEF 0xBB 0xBF`). `csv.DictReader` reads the first header cell as `Source Term` with a leading invisible BOM character, breaking header matching.
**Why it happens:** Excel adds BOM to mark encoding. The `csv` module does not strip it when using `encoding="utf-8"`.
**How to avoid:** Decode with `encoding="utf-8-sig"` (not `"utf-8"`). `utf-8-sig` automatically strips the BOM if present and is a no-op if absent.
**Warning signs:** Import fails with "CSV must have source_term column" even though the file looks correct in a text editor.

### Pitfall 7: Segment table scroll height and sticky headers

**What goes wrong:** The `calc(100vh - 168px)` Virtuoso height becomes incorrect if the sticky header heights change (e.g., paper skill fonts load with different line heights).
**Why it happens:** The 168px = 56px nav + 64px review header + 48px filter bar. Paper font loading could shift these by a few pixels.
**How to avoid:** Use a CSS approach that measures the actual header heights: wrap the Virtuoso in a flex container with `flex: 1` inside a `flex-col` layout that fills the viewport. Alternatively, use a CSS custom property set in the header elements and read in the Virtuoso height calc.
**Warning signs:** A horizontal scrollbar appears at the bottom, or the last few segments are hidden behind the browser chrome.

---

## Code Examples

### Glossary REST endpoint pattern

```python
# Source: Phase 2 new -- backend/src/app/api/routes/glossaries.py

@router.get("/glossaries")
async def list_glossaries(
    source_lang: str | None = None,
    target_lang: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List glossaries, optionally filtered by language pair (for UPLD-04 picker)."""
    q = select(Glossary)
    if source_lang:
        q = q.where(Glossary.source_lang == source_lang)
    if target_lang:
        q = q.where(Glossary.target_lang == target_lang)
    result = await session.execute(q)
    return {"glossaries": [to_response(g) for g in result.scalars().all()]}
```

### Flag counts GROUP BY query

```python
# For ReviewFilterBar chip counts -- single query on page load (D-02-10)
from sqlalchemy import func

async def count_flags_by_type(session: AsyncSession, job_id: str) -> dict[str, int]:
    result = await session.execute(
        select(SegmentFlag.flag_type, func.count(SegmentFlag.id).label("count"))
        .join(Segment, SegmentFlag.segment_id == Segment.id)
        .where(Segment.job_id == job_id)
        .group_by(SegmentFlag.flag_type)
    )
    return {row.flag_type: row.count for row in result.all()}
```

### FlagBadge component

```typescript
// Source: Phase 2 new -- components/FlagBadge.tsx
import { Badge } from "@/components/ui/badge"

type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal"

const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:             { label: "Overflow",    className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:   { label: "Glossary",    className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch: { label: "Placeholder", className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:          { label: "Refusal",     className: "text-red-700 bg-red-50 border-red-200" },
}

export function FlagBadge({ flagType }: { flagType: FlagType }) {
  const config = FLAG_CONFIG[flagType]
  return (
    <Badge variant="outline" className={`text-xs ${config.className}`}>
      {config.label}
    </Badge>
  )
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `react-window` with fixed row heights | `react-virtuoso` with variable heights | ~2022 | Variable-height rows (expandable textareas) require Virtuoso; react-window is effectively deprecated for variable-height use cases |
| TanStack Query v4: `onMutate(context)` -- access `context.client` | TanStack Query v5: `useQueryClient()` outside mutation; `onMutate(variables)` returns snapshot as context | Late 2023 | Breaking change; many online examples are v4 and will fail silently in v5 |
| `react-hotkeys-hook` v4: default fires in form tags | v5: default disabled in form tags | 2024 | Correct default for Phase 2 (j/k should not fire in textarea) |
| `alembic upgrade head` auto-drops named ENUMs | Must use `native_enum=False` or explicit `DROP TYPE` for downgrade safety | Alembic 1.x | Downgrade fails without explicit type drop or native_enum=False |

**Deprecated/outdated:**
- `react-window`: Fixed height only; no active development. Use `react-virtuoso`.
- TanStack Query v4 `context.client` pattern: Fails in v5. Use `useQueryClient()` at hook level.
- `@monaco-editor/react` for segment review: Superseded by D-02-14 (CAT-table). Monaco stays in package.json per D-02-15 but is not used in Phase 2.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `npx typeui.sh pull paper` produces a SKILL.md with Tailwind token configuration; CLI can be run semi-interactively in the dev environment | Section 9 | If fully non-interactive-capable mode is absent, Wave 0 becomes a manual step. Mitigation: UI-SPEC captures all paper tokens; executor can apply them directly without the CLI. |
| A2 | `asyncio.Lock` per job_id in a single FastAPI process is sufficient for export concurrency guard (PoC runs 1 API process via `uvicorn`) | Section 7 | If multiple API processes are deployed (`--workers N`), in-process lock fails. Mitigation: document pg_advisory_lock upgrade path in a TODO comment. |
| A3 | Single-segment regenerate completes in under 5 seconds for typical segment lengths under qwen-mt-turbo | Section 8 | If latency exceeds 5s, the synchronous endpoint may feel slow. Mitigation: UI shows spinner; acceptable for PoC. arq queue would add complexity without benefit. |

---

## Open Questions (RESOLVED)

1. **Paper skill CLI non-interactive mode**
   - What we know: `npx typeui.sh --version` = `0.1.0`. The CLI is interactive (TUI prompt observed).
   - What's unclear: Whether `npx typeui.sh pull paper` can be scripted or requires a TTY.
   - Recommendation: Wave 0 plan step should say "Run `npx typeui.sh pull paper` interactively, select SKILL.md output format, commit the result before starting frontend waves."
   - **RESOLVED:** Plan 01 Task 1 Step 2 — attempt `npx typeui.sh pull paper` first; if unavailable or non-interactive, apply paper-ink/#111111 and paper-accent/#8B5CF6 tokens directly to `frontend/tailwind.config.ts` via manual fallback. All paper tokens documented in 02-UI-SPEC.md.

2. **Segments endpoint: pagination vs full load**
   - What we know: The PoC demo documents are of unknown size; react-virtuoso virtualizes DOM rendering regardless of data size.
   - What's unclear: Whether 1,000-2,000 segment JSON payloads cause latency issues on the dev machine.
   - Recommendation: Load all segments for the job in one request (no pagination). JSON for 1,000 segments is ~500KB over localhost. Re-evaluate only if demo documents exceed 2,000 segments.
   - **RESOLVED:** Plan 04 Task 2 — GET /jobs/{id}/segments returns full segment list (no pagination). react-virtuoso handles DOM virtualization. Re-evaluate only if demo docs exceed 2,000 segments.

3. **Flag count query: separate endpoint vs bundled in segment list**
   - What we know: UI-SPEC requires per-type counts in filter chips. Options: (a) bundle flags in `GET /jobs/{id}/segments`, (b) separate `GET /jobs/{id}/flag-counts`.
   - Recommendation: Bundle. `selectinload(Segment.flags)` is one extra JOIN. Avoids a second round-trip and simplifies frontend state. Re-evaluate if benchmark shows more than 2s load time.
   - **RESOLVED:** Plan 04 Task 2 — flag_counts bundled in GET /jobs/{id}/segments response as a GROUP BY sub-query. Returns `{"segments": [...], "flag_counts": {"overflow": N, ...}, "total": N}`. No second round-trip.


4. **llm_refusal heuristic: false positives on short terms**
   - What we know: The original heuristic flagged `llm_refusal` when `translated == source OR len(translated) < 3`. This caused false positives on short valid translations like "AI" → "AI" (correct: acronym stays as-is).
   - What was unclear: Where to set the length threshold to distinguish "acronym preserved correctly" from "LLM refused to translate".
   - **RESOLVED (cross-AI review):** Plan 03 Task 1 — heuristic changed to `len(source_stripped) > 8 AND translated_stripped == source_stripped`. Removes the `len < 3` branch entirely. Only flags identical output when the source is longer than 8 characters, which excludes acronyms (AI, OK, etc.) and short proper nouns while still catching genuine refusals on normal-length sentences. Documented in Plan 03 action and test_post_check.py::test_llm_refusal_flag_written (source "Hello world" = 11 chars > 8 threshold).
---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | glossaries/flags schema | Yes (docker) | 16-alpine | -- |
| Redis | arq job queue | Yes (docker) | 7-alpine | -- |
| Docker + Compose | Dev stack | Yes | Docker 29.2.1 | -- |
| Node.js | Frontend build | Yes | v24.13.1 | -- |
| Python 3.12 | Backend (via Docker) | Yes (container) | 3.12 | -- |
| `react-virtuoso` 4.18.6 | Segment table virtualization | Not yet installed | -- | Must install in Wave 0 |
| `react-hotkeys-hook` 5.2.4 | Keyboard shortcuts | Not yet installed | -- | Must install in Wave 0 |
| `typeui.sh` CLI | Paper skill pull | Yes (npx 0.1.0) | 0.1.0 | Manual: apply UI-SPEC tokens to tailwind.config.ts + layout.tsx |

**Missing dependencies with no fallback:**
- `react-virtuoso` and `react-hotkeys-hook` must be installed in Wave 0 before any review page work

**Missing dependencies with fallback:**
- `typeui.sh` paper pull: if interactive issues arise, apply UI-SPEC paper tokens manually

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 8.x + pytest-asyncio (`asyncio_mode = "auto"` in pyproject.toml) |
| Frontend framework | vitest 1.x + Testing Library (`jsdom` environment in vitest.config.mts) |
| Backend config | `backend/pyproject.toml` `[tool.pytest.ini_options]` |
| Frontend config | `frontend/vitest.config.mts` |
| Backend quick run | `uv run pytest backend/tests/ -m "not integration" -x --no-header -q` |
| Backend full suite | `uv run pytest backend/tests/ --cov=src/app --cov-fail-under=80` |
| Frontend quick run | `npm --prefix frontend run test` |
| Frontend full suite | `npm --prefix frontend run test -- --coverage` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| GLOS-01 | Glossary CRUD: create, list, get, update, delete | unit | `uv run pytest backend/tests/api/test_glossaries.py -x` | Wave 0 gap |
| GLOS-01 | GlossaryTerm add/edit/delete | unit | `uv run pytest backend/tests/services/test_glossary_service.py -x` | Wave 0 gap |
| GLOS-02 | CSV parse: valid, BOM, header variants, duplicate | unit | `uv run pytest backend/tests/services/test_csv_import.py -x` | Wave 0 gap |
| GLOS-02 | TBX minimal parse: valid TBX-Core, malformed XML | unit | `uv run pytest backend/tests/services/test_tbx_import.py -x` | Wave 0 gap |
| GLOS-03 | Worker loads glossary terms and passes to translate_batch | unit | `uv run pytest backend/tests/workers/test_worker_glossary.py -x` | Wave 0 gap |
| GLOS-04 | Post-check: violation flag written when term absent from output | unit | `uv run pytest backend/tests/services/test_post_check.py -x` | Wave 0 gap |
| GLOS-04 | Post-check: min-2-char guard skips short terms | unit | `uv run pytest backend/tests/services/test_post_check.py::test_short_term_skipped -x` | Wave 0 gap |
| GLOS-05 | List/edit/delete glossaries via UI | manual | Demo walkthrough | manual-only |
| REV-01 | Segment table renders all segments without DOM explosion | unit (frontend) | `npm --prefix frontend run test -- SegmentTable` | Wave 0 gap |
| REV-02 | Optimistic update: cache updated immediately on textarea change | unit (frontend) | `npm --prefix frontend run test -- useSegments` | Wave 0 gap |
| REV-02 | Rollback: cache restored and toast shown on PATCH error | unit (frontend) | `npm --prefix frontend run test -- useSegments` | Wave 0 gap |
| REV-03 | Flag badges render correct type and color per flag_type | unit (frontend) | `npm --prefix frontend run test -- FlagBadge` | Wave 0 gap |
| REV-04 | Regenerate overwrites translated_text, not edited_text | unit | `uv run pytest backend/tests/api/test_segments.py::test_regenerate -x` | Wave 0 gap |
| REV-05 | Export: reassembled DOCX uses edited_text when set | unit | `uv run pytest backend/tests/services/test_export_service.py::test_export_prefers_edited_text -x` | Wave 0 gap |
| REV-06 | Export: concurrent exports do not corrupt output | unit | `uv run pytest backend/tests/services/test_export_service.py::test_export_idempotent -x` | Wave 0 gap |
| LAYOUT-01 | Expansion ratio stored; overflow flag emitted above threshold | unit | `uv run pytest backend/tests/services/test_post_check.py::test_expansion_ratio -x` | Wave 0 gap |
| UPLD-04 | Glossary picker appears when language pair matches; hides when no glossaries exist for pair | unit (frontend) | `npm --prefix frontend run test -- GlossarySelect` | Wave 0 gap |

### Sampling Rate

- **Per task commit:** `uv run pytest backend/tests/ -m "not integration" -x --no-header -q`
- **Per wave merge:** `uv run pytest backend/tests/ --cov=src/app --cov-fail-under=80` + `npm --prefix frontend run test -- --coverage`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/api/test_glossaries.py` -- covers GLOS-01, GLOS-05
- [ ] `backend/tests/api/test_segments.py` -- covers REV-02, REV-04 (extend existing conftest)
- [ ] `backend/tests/services/test_glossary_service.py` -- covers GLOS-01 service layer
- [ ] `backend/tests/services/test_csv_import.py` -- covers GLOS-02 CSV
- [ ] `backend/tests/services/test_tbx_import.py` -- covers GLOS-02 TBX
- [ ] `backend/tests/services/test_post_check.py` -- covers GLOS-04, LAYOUT-01
- [ ] `backend/tests/services/test_export_service.py` -- covers REV-05, REV-06
- [ ] `backend/tests/workers/test_worker_glossary.py` -- covers GLOS-03 (extend translate_worker tests)
- [ ] `frontend/src/__tests__/SegmentTable.test.tsx` -- covers REV-01
- [ ] `frontend/src/__tests__/useSegments.test.ts` -- covers REV-02 optimistic update + rollback
- [ ] `frontend/src/__tests__/FlagBadge.test.tsx` -- covers REV-03
- [ ] `frontend/src/__tests__/GlossarySelect.test.tsx` -- covers UPLD-04

Existing `backend/tests/conftest.py` already has SQLite in-memory engine and mock Redis fixtures. Extend with `Glossary`, `GlossaryTerm`, `SegmentFlag` factory fixtures for Phase 2 tests.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | PoC is single-team internal; no auth in Phase 2 |
| V3 Session Management | No | No session state; stateless REST |
| V4 Access Control | No | No multi-user; no resource ownership per PROJECT.md |
| V5 Input Validation | Yes | Pydantic `Field(min_length, max_length)` on all request bodies; CSV term validation in service layer |
| V6 Cryptography | No | No new crypto in Phase 2 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Oversized CSV upload | DoS | `MAX_UPLOAD_BYTES = 25 * 1024 * 1024` already enforced in upload.py; apply same guard to CSV import endpoint |
| CSV formula injection | Tampering | Terms are stored as TEXT and rendered in React JSX (auto-escapes HTML); never executed or rendered as HTML |
| Malformed TBX causing XML expansion | DoS | `xml.etree.ElementTree` does not expand external entities by default; safe for untrusted XML input |
| Glossary FK pair mismatch on upload | Integrity | Backend validates `glossary.source_lang == job.source_lang && glossary.target_lang == job.target_lang`; returns 422 per UI-SPEC copy |
| Segment text rendered as raw HTML | XSS | Segment source and translated text are rendered via React JSX text nodes (not raw HTML injection); no risk |

---

## Sources

### Primary (HIGH confidence)

- Context7 `/tanstack/query` -- optimistic-updates.md, `onMutate`/`onError`/`onSettled` pattern [VERIFIED]
- Context7 `/petyosi/react-virtuoso` -- auto-resizing.md, keyboard-navigation.md, overscan/increaseViewportBy guide [VERIFIED]
- Context7 `/johannesklauss/react-hotkeys-hook` -- disable-hotkeys.mdx, scoping-hotkeys.mdx, enableOnFormTags [VERIFIED]
- Codebase scan: `backend/src/app/llm/terminology.py`, `backend/src/app/db/models.py`, `backend/src/app/workers/translate_worker.py`, `backend/src/app/pipeline/docx/reassembler.py` -- verified Phase 1 integration points [VERIFIED]
- npm registry: `react-virtuoso@4.18.6` (published 2026-04-24), `react-hotkeys-hook@5.2.4` (published 2026-02-02) [VERIFIED]
- `02-CONTEXT.md` D-02-01..D-02-28 -- all locked decisions [VERIFIED]
- `02-UI-SPEC.md` -- component inventory, typography, font loading code snippets [VERIFIED]

### Secondary (MEDIUM confidence)

- `01-PATTERNS.md` -- established patterns to extend (SQLite conftest, arq worker lifecycle, pydantic frozen models) [VERIFIED]
- `01-CONTEXT.md` D-01..D-20 -- Phase 1 carry-forward decisions [VERIFIED]
- Python stdlib docs: `csv.DictReader` (BOM handling via utf-8-sig), `xml.etree.ElementTree` -- built-in modules, no version constraint [VERIFIED]

### Tertiary (LOW confidence)

- `npx typeui.sh pull paper` CLI interactive behavior -- version 0.1.0 confirmed; full flow not end-to-end verified [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified via npm registry + Context7 docs
- Architecture: HIGH -- based on verified Phase 1 codebase + locked decisions
- Pitfalls: HIGH -- derived from verified library docs + existing test patterns
- Paper skill CLI behavior: LOW -- interactive flow not fully verified

**Research date:** 2026-04-24
**Valid until:** 2026-05-24 (30 days; react-virtuoso and TanStack are stable releases)
