---
phase: 02-review-ux-glossary
plan: "05"
type: execute
wave: 2
depends_on: ["02-01", "02-03"]
files_modified:
  - frontend/src/lib/types.ts
  - frontend/src/app/layout.tsx
  - frontend/src/components/FlagBadge.tsx
  - frontend/src/components/GlossarySelect.tsx
  - frontend/src/components/NavBar.tsx
  - frontend/src/components/UploadForm.tsx
  - frontend/src/app/glossaries/page.tsx
  - frontend/src/app/glossaries/[id]/page.tsx
  - frontend/src/components/glossary/GlossaryList.tsx
  - frontend/src/components/glossary/GlossaryCreateDialog.tsx
  - frontend/src/components/glossary/TermsTable.tsx
  - frontend/src/components/glossary/CSVUploadButton.tsx
autonomous: true
requirements: [GLOS-01, GLOS-02, GLOS-05]

must_haves:
  truths:
    - "User can navigate to /glossaries from the nav bar"
    - "User can create a new glossary (name + source/target lang pair)"
    - "User can view glossary terms in a table at /glossaries/[id]"
    - "User can add, edit, and delete individual terms inline"
    - "User can import terms from a CSV file"
    - "Glossary picker appears on the upload form filtered to matching lang pair"
    - "Paper skill fonts (Roboto/Montserrat/PT Mono) applied to layout"
  artifacts:
    - path: "frontend/src/lib/types.ts"
      provides: "Segment, SegmentFlag, Glossary, GlossaryTerm, SegmentsResponse types"
    - path: "frontend/src/app/layout.tsx"
      provides: "Paper skill font loading via next/font/google"
    - path: "frontend/src/components/FlagBadge.tsx"
      provides: "Reusable flag badge with semantic colors"
    - path: "frontend/src/components/GlossarySelect.tsx"
      provides: "Single-select glossary picker filtered by lang pair"
    - path: "frontend/src/app/glossaries/page.tsx"
      provides: "Glossary list page"
    - path: "frontend/src/app/glossaries/[id]/page.tsx"
      provides: "Glossary detail + terms management page"
  key_links:
    - from: "GlossarySelect.tsx"
      to: "GET /glossaries?source_lang=&target_lang="
      via: "useQuery from TanStack Query — response shape: {glossaries: Glossary[]}"
      pattern: "fetch.*glossaries.*glossaries"
    - from: "UploadForm.tsx"
      to: "GlossarySelect component"
      via: "import + render after language fields"
      pattern: "GlossarySelect"
    - from: "glossaries/[id]/page.tsx"
      to: "POST /glossaries/{id}/terms/import"
      via: "CSVUploadButton component"
      pattern: "terms/import"
---

<objective>
Build the glossary frontend: shared type extensions, paper font setup, reusable FlagBadge and GlossarySelect components, NavBar "Glossaries" link, /glossaries list+create page, /glossaries/[id] terms management page, CSVUploadButton import, and UploadForm glossary picker integration.

Purpose: Delivers GLOS-01 (create glossary), GLOS-02 (CSV import UI), GLOS-05 (list/edit/delete via UI), and UPLD-04 (glossary picker on upload form). After this plan, users can manage glossaries end-to-end from the browser.

Output: 12 new/modified frontend files. All glossary CRUD surfaces wired to Wave 1 backend endpoints.
</objective>

<execution_context>
@/home/thu/.claude/get-shit-done/workflows/execute-plan.md
@/home/thu/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-review-ux-glossary/02-CONTEXT.md
@.planning/phases/02-review-ux-glossary/02-UI-SPEC.md
@.planning/phases/02-review-ux-glossary/02-PATTERNS.md
@.planning/phases/02-review-ux-glossary/02-01-deps-test-scaffolding-PLAN.md
@.planning/phases/02-review-ux-glossary/02-03-glossary-backend-PLAN.md

<interfaces>
<!-- Phase 1 types already in frontend/src/lib/types.ts -->
```typescript
export type JobStatus = "pending" | "processing" | "done" | "failed" | "needs_review";
export interface Language { code: string; name: string; }
export interface UploadResponse { job_id: string; status: JobStatus; }
export interface JobSummary { id: string; status: JobStatus; source_lang: string; target_lang: string; input_filename: string; created_at: string; }
```

<!-- Phase 2 types to ADD to types.ts -->
```typescript
// Segment types
export type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal";
export type FlagSeverity = "info" | "warn" | "block";
export interface SegmentFlag { id: string; segment_id: string; flag_type: FlagType; severity: FlagSeverity; details: Record<string, unknown>; created_at: string; }
export interface Segment { id: string; job_id: string; seq_in_job: number; source_text: string; translated_text: string | null; edited_text: string | null; expansion_ratio: number | null; flags: SegmentFlag[]; }
export interface SegmentsResponse { segments: Segment[]; total: number; }
// Glossary types
export interface GlossaryTerm { id: string; glossary_id: string; source_term: string; target_term: string; notes: string | null; created_at: string; }
export interface Glossary { id: string; name: string; source_lang: string; target_lang: string; created_at: string; updated_at: string; terms?: GlossaryTerm[]; }
```

<!-- GET /glossaries response shape (Plan 03 backend) -->
<!-- CRITICAL: API returns {"glossaries": Glossary[]} — wrapped object, NOT bare Glossary[] array -->
<!-- GET /glossaries -> {"glossaries": Glossary[]} -->
<!-- GET /glossaries?source_lang=vi&target_lang=en -> {"glossaries": Glossary[]} (filtered) -->
<!-- All call sites must extract .glossaries from the response -->

<!-- Phase 1 NavBar: src/components/NavBar.tsx — add "Glossaries" nav link -->
<!-- Phase 1 UploadForm uses LanguageSelect: src/components/LanguageSelect.tsx -->
<!-- TanStack Query v5 useQuery pattern already used in Phase 1 -->

<!-- FlagBadge color map (from UI-SPEC) -->
```typescript
const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:              { label: "Overflow",    className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:    { label: "Glossary",    className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch:  { label: "Placeholder", className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:           { label: "Refusal",     className: "text-red-700 bg-red-50 border-red-200" },
};
```

<!-- Radix UI SelectItem runtime constraint (CRITICAL) -->
<!-- SelectItem value="" throws at runtime: "A <Select.Item /> must have a value prop that is not an empty string." -->
<!-- Use sentinel value="__none__" and map back to "" in onChange handler -->
<!-- Pattern:
  value={value || "__none__"}
  onValueChange={(v) => onChange(v === "__none__" ? "" : v)}
  ...
  <SelectItem value="__none__">None</SelectItem>
-->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Extend types.ts + apply paper fonts to layout.tsx</name>
  <files>
    frontend/src/lib/types.ts
    frontend/src/app/layout.tsx
  </files>
  <behavior>
    - types.ts exports all Phase 2 types without breaking Phase 1 exports
    - layout.tsx loads Roboto/Montserrat/PT_Mono from next/font/google with correct subsets
    - CSS variables --font-roboto / --font-montserrat / --font-pt-mono injected on html element
    - Existing layout structure and metadata unchanged
  </behavior>
  <action>
**types.ts** — append Phase 2 types below the existing Phase 1 exports. Do NOT remove or modify existing exports. Add:

```typescript
// --- Phase 2 types ---
export type FlagType = "overflow" | "glossary_violation" | "placeholder_mismatch" | "llm_refusal";
export type FlagSeverity = "info" | "warn" | "block";

export interface SegmentFlag {
  id: string;
  segment_id: string;
  flag_type: FlagType;
  severity: FlagSeverity;
  details: Record<string, unknown>;
  created_at: string;
}

export interface Segment {
  id: string;
  job_id: string;
  seq_in_job: number;
  source_text: string;
  translated_text: string | null;
  edited_text: string | null;
  expansion_ratio: number | null;
  flags: SegmentFlag[];
}

export interface SegmentsResponse {
  segments: Segment[];
  total: number;
}

export interface GlossaryTerm {
  id: string;
  glossary_id: string;
  source_term: string;
  target_term: string;
  notes: string | null;
  created_at: string;
}

export interface Glossary {
  id: string;
  name: string;
  source_lang: string;
  target_lang: string;
  created_at: string;
  updated_at: string;
  terms?: GlossaryTerm[];
}
```

**layout.tsx** — add font imports from `next/font/google`. Read the current file first to preserve existing imports and structure. Per D-02-27/28 (paper skill fonts):

```typescript
import { Roboto, Montserrat, PT_Mono } from "next/font/google";

const roboto = Roboto({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-roboto",
});
const montserrat = Montserrat({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "600"],
  variable: "--font-montserrat",
});
const ptMono = PT_Mono({
  subsets: ["latin"],
  weight: "400",
  variable: "--font-pt-mono",
});
```

Apply font variables on the `<html>` element:
```tsx
<html lang="en" className={`${roboto.variable} ${montserrat.variable} ${ptMono.variable}`}>
```

The className addition merges with any existing className on html. Use template literal to append; do not remove existing classes.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>TypeScript compiles with no errors on types.ts or layout.tsx. All Phase 2 types exported. Font variables visible in html className.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create FlagBadge, GlossarySelect (with __none__ sentinel), extend NavBar</name>
  <files>
    frontend/src/components/FlagBadge.tsx
    frontend/src/components/GlossarySelect.tsx
    frontend/src/components/NavBar.tsx
  </files>
  <behavior>
    - FlagBadge renders correct semantic color per flag type per UI-SPEC color table
    - GlossarySelect uses value="__none__" sentinel for the "None" option — Radix throws on value=""
    - GlossarySelect maps __none__ back to "" in onValueChange before calling parent onChange
    - GlossarySelect renders "No glossary" empty state when no glossaries match lang pair
    - GlossarySelect passes selected glossary_id to parent via onChange callback
    - GlossarySelect extracts .glossaries from API response (response shape: {"glossaries": Glossary[]})
    - NavBar shows "Glossaries" link between "Jobs" and API status indicator
  </behavior>
  <action>
**FlagBadge.tsx** — analog: `src/components/StatusBadge.tsx`. Single prop `flagType: FlagType`. Uses shadcn Badge with `variant="outline"`.

```tsx
"use client";
import { Badge } from "@/components/ui/badge";
import type { FlagType } from "@/lib/types";

const FLAG_CONFIG: Record<FlagType, { label: string; className: string }> = {
  overflow:             { label: "Overflow",    className: "text-amber-600 bg-amber-50 border-amber-200" },
  glossary_violation:   { label: "Glossary",    className: "text-violet-700 bg-violet-50 border-violet-200" },
  placeholder_mismatch: { label: "Placeholder", className: "text-orange-700 bg-orange-50 border-orange-200" },
  llm_refusal:          { label: "Refusal",     className: "text-red-700 bg-red-50 border-red-200" },
};

interface FlagBadgeProps {
  flagType: FlagType;
  className?: string;
}

export function FlagBadge({ flagType, className }: FlagBadgeProps) {
  const config = FLAG_CONFIG[flagType];
  return (
    <Badge
      variant="outline"
      className={`text-xs font-normal ${config.className} ${className ?? ""}`}
    >
      {config.label}
    </Badge>
  );
}
```

**GlossarySelect.tsx** — analog: `src/components/LanguageSelect.tsx`. Uses shadcn Select. Fetches `GET /api/glossaries?source_lang=X&target_lang=Y` via TanStack Query.

CRITICAL: The API returns `{"glossaries": Glossary[]}` (wrapped object). Extract `.glossaries` from the response.

CRITICAL: Radix UI `<SelectItem>` throws at runtime when `value=""`.
Use sentinel `value="__none__"` for the "None" option and map it back to `""` in `onValueChange`.

```tsx
"use client";
import { useQuery } from "@tanstack/react-query";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import type { Glossary } from "@/lib/types";

const NONE_SENTINEL = "__none__";

interface GlossarySelectProps {
  sourceLang: string;
  targetLang: string;
  value: string;          // glossary_id or "" (empty = none selected)
  onChange: (id: string) => void;
}

export function GlossarySelect({ sourceLang, targetLang, value, onChange }: GlossarySelectProps) {
  const enabled = !!sourceLang && !!targetLang;

  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ["glossaries", sourceLang, targetLang],
    queryFn: async () => {
      const res = await fetch(`/api/glossaries?source_lang=${sourceLang}&target_lang=${targetLang}`);
      if (!res.ok) throw new Error("Failed to load glossaries");
      const data = await res.json();
      return data.glossaries as Glossary[];  // unwrap: API returns {"glossaries": [...]}
    },
    enabled,
  });

  // Map "" → NONE_SENTINEL for Radix (value="" throws at runtime)
  const selectValue = value || NONE_SENTINEL;

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-slate-500 font-roboto">Glossary (optional)</label>
      <Select
        value={selectValue}
        onValueChange={(v) => onChange(v === NONE_SENTINEL ? "" : v)}
        disabled={!enabled || isLoading}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder={
            !enabled ? "Select languages first" :
            isLoading ? "Loading…" :
            glossaries.length === 0 ? "No glossary for this pair" :
            "None"
          } />
        </SelectTrigger>
        <SelectContent>
          {/* Use NONE_SENTINEL — Radix throws on value="" */}
          <SelectItem value={NONE_SENTINEL}>None</SelectItem>
          {glossaries.map((g) => (
            <SelectItem key={g.id} value={g.id}>
              {g.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {enabled && !isLoading && glossaries.length === 0 && (
        <p className="text-xs text-slate-400">
          No glossaries for this language pair.{" "}
          <a href="/glossaries" className="text-violet-600 underline">Create one</a>.
        </p>
      )}
    </div>
  );
}
```

**NavBar.tsx** — read existing file first. Add "Glossaries" link between the existing "Jobs" link and whatever follows it. Match the existing `<Link>` style exactly (className, `href`). Use `href="/glossaries"` and label "Glossaries".
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -30</automated>
  </verify>
  <done>
    FlagBadge.tsx, GlossarySelect.tsx, NavBar.tsx exist. TypeScript clean.
    FlagBadge renders correct colors per UI-SPEC.
    GlossarySelect uses value="__none__" for None option (not value="") — no Radix runtime throw.
    GlossarySelect onValueChange maps __none__ → "" before calling parent onChange.
    GlossarySelect extracts `.glossaries` from API response.
    NavBar has Glossaries link.
  </done>
</task>

<task type="auto">
  <name>Task 3: Glossary list/create pages + GlossaryList, GlossaryCreateDialog, TermsTable, CSVUploadButton + extend UploadForm</name>
  <files>
    frontend/src/app/glossaries/page.tsx
    frontend/src/app/glossaries/[id]/page.tsx
    frontend/src/components/glossary/GlossaryList.tsx
    frontend/src/components/glossary/GlossaryCreateDialog.tsx
    frontend/src/components/glossary/TermsTable.tsx
    frontend/src/components/glossary/CSVUploadButton.tsx
    frontend/src/components/UploadForm.tsx
  </files>
  <action>
**Create directory `frontend/src/components/glossary/` if not exists.**

**GlossaryList.tsx** — analog: `src/components/JobsTable.tsx`. Wraps shadcn Table.

Props: `glossaries: Glossary[]`, `onDelete: (id: string) => void`.
Columns: Name (link to `/glossaries/[id]`), Language Pair (`source_lang → target_lang`), Terms count (`g.terms?.length ?? "—"`), Created date (locale date string), Actions (Delete button).

Delete button: `<Button variant="ghost" size="icon" onClick={() => onDelete(g.id)}><Trash2 className="h-4 w-4 text-red-500" /></Button>`.
Wrap delete in a confirm `window.confirm("Delete glossary and all its terms?")` before calling onDelete (no separate Dialog — glossary list is PoC scope).

**GlossaryCreateDialog.tsx** — analog: `src/components/TrackedChangesModal.tsx`. shadcn Dialog.

Props:
```typescript
interface GlossaryCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;  // no argument — dialog closes internally; parent invalidates cache
}
```

Form fields inside DialogContent:
- Name: `<Input>` (required, max 100 chars)
- Source Language: `<LanguageSelect>` (import from Phase 1)
- Target Language: `<LanguageSelect>`
- Submit button: "Create Glossary" with violet-500 styling.

On submit: `POST /api/glossaries` body `{ name, source_lang, target_lang }`. On success: call `onCreated()` (no argument), close dialog. On error: show toast with error message.

**TermsTable.tsx** — analog: `src/components/JobsTable.tsx`. Editable terms table.

Props: `glossaryId: string`, `terms: GlossaryTerm[]`, `onTermsChange: () => void` (triggers parent refetch).

Features:
1. Read rows: source_term | target_term | notes | Actions (Pencil + Trash2 buttons).
2. Edit row: clicking Pencil replaces the row with inline Input fields + "Save" / "Cancel" buttons. PATCH `/api/glossaries/{glossaryId}/terms/{termId}` on Save.
3. Delete: DELETE `/api/glossaries/{glossaryId}/terms/{termId}`, no confirm dialog (single click, terms are cheap per UI-SPEC).
4. Add row at bottom: always-visible `TermAddRow` — three Inputs + "Add Term" button. POST `/api/glossaries/{glossaryId}/terms` on submit. Clear fields after success.

Use local `editingId: string | null` state to track which row is in edit mode.

**CSVUploadButton.tsx** — analog: `src/components/UploadForm.tsx` (file input pattern).

Props: `glossaryId: string`, `onImported: (count: number) => void`.

Renders shadcn `<Button variant="outline">` with hidden `<input type="file" accept=".csv">`. On file select: `POST /api/glossaries/{glossaryId}/terms/import` with `FormData` (field name `file`). On success: toast "Imported N terms", call `onImported(response.imported)`. On error: toast "Import failed: {message}".

```tsx
const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`/api/glossaries/${glossaryId}/terms/import`, {
    method: "POST",
    body: form,
  });
  // ... handle result
  e.target.value = ""; // reset so same file can be re-imported
};
```

**glossaries/page.tsx** — analog: `src/app/jobs/page.tsx`. "use client".

CRITICAL: `GET /api/glossaries` returns `{"glossaries": Glossary[]}` — must extract `.glossaries` from response.

```tsx
"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Glossary } from "@/lib/types";
import { GlossaryList } from "@/components/glossary/GlossaryList";
import { GlossaryCreateDialog } from "@/components/glossary/GlossaryCreateDialog";
import { Button } from "@/components/ui/button";
import { Plus } from "lucide-react";

export default function GlossariesPage() {
  const [createOpen, setCreateOpen] = useState(false);
  const queryClient = useQueryClient();

  const { data: glossaries = [], isLoading } = useQuery<Glossary[]>({
    queryKey: ["glossaries"],
    queryFn: () =>
      fetch("/api/glossaries")
        .then(r => r.json())
        .then(d => d.glossaries as Glossary[]),  // unwrap: API returns {"glossaries": [...]}
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      fetch(`/api/glossaries/${id}`, { method: "DELETE" }).then(r => {
        if (!r.ok) throw new Error("Delete failed");
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["glossaries"] }),
  });

  return (
    <div className="px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold font-[--font-montserrat] text-[#111111]">
          Glossaries
        </h1>
        <Button
          onClick={() => setCreateOpen(true)}
          className="bg-violet-500 hover:bg-violet-600 text-white"
        >
          <Plus className="h-4 w-4 mr-2" />
          Create Glossary
        </Button>
      </div>

      {isLoading ? (
        <p className="text-slate-400">Loading…</p>
      ) : (
        <GlossaryList
          glossaries={glossaries}
          onDelete={(id) => deleteMutation.mutate(id)}
        />
      )}

      <GlossaryCreateDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ["glossaries"] });
          setCreateOpen(false);
        }}
      />
    </div>
  );
}
```

**glossaries/[id]/page.tsx** — analog: `src/app/jobs/[id]/page.tsx`.

```tsx
"use client";
// useParams() to get id
// useQuery(['glossary', id], GET /api/glossaries/{id}) — returns Glossary with terms (no wrapping on single-item endpoint)
// Layout: inline header (back link, glossary name, lang pair chip, CSVUploadButton)
//         TermsTable below
// onTermsChange: () => refetch()
```

Include a simple inline header (no separate GlossaryDetailHeader component — keep scope to listed files):
- Back link: `<Link href="/glossaries">← Back</Link>`
- Glossary name in Montserrat heading
- Language pair chip: `{g.source_lang} → {g.target_lang}` in slate-100 pill
- CSVUploadButton positioned top-right of terms section
- TermsTable below

**UploadForm.tsx** — read existing file first. Add GlossarySelect after the existing target language field and before the submit button.

Local state additions:
```tsx
const [glossaryId, setGlossaryId] = useState("");
```

Add GlossarySelect in JSX:
```tsx
<GlossarySelect
  sourceLang={sourceLang}   // check actual state variable name in existing file
  targetLang={targetLang}   // check actual state variable name in existing file
  value={glossaryId}
  onChange={setGlossaryId}
/>
```

Append `glossary_id` to FormData before submit (only if non-empty):
```tsx
if (glossaryId) {
  formData.append("glossary_id", glossaryId);
}
```

Import `GlossarySelect` from `"@/components/GlossarySelect"`. Do NOT remove or break any existing UploadForm logic. Check actual variable names for `sourceLang`/`targetLang` in the file before editing.
  </action>
  <verify>
    <automated>cd /home/thu/dev/projects/ai-translation/frontend && npx tsc --noEmit 2>&1 | head -40</automated>
  </verify>
  <done>
    TypeScript compiles clean. All glossary pages/components exist at correct paths.
    /glossaries page renders GlossaryList + create button. queryFn extracts .glossaries from response.
    GlossaryCreateDialog.onCreated is () => void (no argument).
    /glossaries/[id] page renders TermsTable + CSVUploadButton.
    UploadForm includes GlossarySelect after language fields.
    No existing UploadForm logic broken.
    GlossarySelect uses value="__none__" sentinel — no Radix runtime throw on "None" item.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → FastAPI | Glossary CRUD requests; file upload for CSV import |
| FastAPI → PostgreSQL | Term writes; glossary reads |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-05-01 | XSS | Segment and glossary term text rendered in React | accept | All text output via React JSX text nodes with framework-level auto-escaping. No raw HTML injection anywhere in glossary or segment components. |
| T-02-05-02 | Information Disclosure | GET /glossaries returns all glossaries | accept | PoC has no auth; single internal user. Multi-tenant isolation deferred to v2 per PROJECT.md. |
| T-02-05-03 | Tampering | CSV import file content | mitigate | Backend plan 03 `parse_csv_glossary` validates encoding and field structure; rejects rows with missing required columns. Frontend sends file as-is to POST endpoint; validation on server side. |
| T-02-05-04 | Denial of Service | Large CSV upload | accept | PoC scope; no external users. File size limit inherited from Phase 1 upload size guard on FastAPI. |
</threat_model>

<verification>
After all tasks complete:

1. TypeScript build: `cd frontend && npx tsc --noEmit` — zero errors
2. NavBar shows "Glossaries" link visible at all routes
3. Font variables present in html element className (inspect DOM or check layout.tsx)
4. FlagBadge renders amber/violet/orange/red per flag type (manual or snapshot test)
5. GlossarySelect disabled when languages not selected; shows filtered list when selected
6. GlossarySelect "None" SelectItem has value="__none__" (not value="") — no Radix runtime throw
7. /glossaries page loads and renders "Create Glossary" button
8. /glossaries/[id] page renders TermsTable with term rows
9. UploadForm includes glossary picker after language fields
10. CSVUploadButton visible on glossary detail page
</verification>

<success_criteria>
- All 12 files created/modified with zero TypeScript errors
- FlagBadge: exactly 4 color configs matching UI-SPEC semantic flag colors
- GlossarySelect: queryFn extracts `.glossaries` from `{"glossaries": Glossary[]}` response (not bare array)
- GlossarySelect: SelectItem for "None" uses value="__none__" sentinel (NOT value="") — Radix runtime safe
- GlossarySelect: onValueChange maps "__none__" → "" before calling parent onChange
- GlossarySelect: disabled when source/target lang empty; shows empty state with link to /glossaries when no matches
- NavBar: "Glossaries" link present, navigates to /glossaries
- /glossaries: queryFn extracts `.glossaries` from response; lists glossaries, opens create dialog, supports delete
- GlossaryCreateDialog: `onCreated: () => void` (no argument — dialog closes internally)
- /glossaries/[id]: shows glossary name + lang pair, TermsTable with inline add/edit/delete, CSVUploadButton
- UploadForm: glossary_id appended to FormData when non-empty; no regression on existing form fields
- Paper fonts (Roboto/Montserrat/PT Mono) loaded via next/font/google with CSS variables injected on html element
</success_criteria>

<output>
After completion, create `.planning/phases/02-review-ux-glossary/02-05-SUMMARY.md` using the template at `@/home/thu/.claude/get-shit-done/templates/summary.md`.
</output>
