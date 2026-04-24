# Phase 2: Review UX + Glossary - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the Phase 1 DOCX pipeline with the two demo differentiators for AICore:

1. **Glossary system** — Postgres-backed CRUD (create, CSV/TBX upload, list, edit, delete) scoped one glossary per `(source_lang, target_lang)` pair. Injection into `qwen-mt-turbo` via the native `terminology` API parameter (already plumbed in Phase 1 via `backend/src/app/llm/terminology.py`). Post-translation enforcement pass flags segments where a glossary term's target does not appear in the output.

2. **Review UX** — Side-by-side CAT-tool-style segment table on completed jobs. Source segments read-only on left, editable translations on right. Inline edit with debounced persistence. Per-segment regenerate. Segment-level flags visibly surfaced (overflow, glossary violation, placeholder mismatch, LLM refusal). Export reassembles DOCX using `edited_text ?? translated_text`, idempotent.

3. **UPLD-04 fulfilment** — Glossary picker on the upload form (deferred from Phase 1 per D-15). Single-select, filtered to matching-pair glossaries, locked at submit.

Out of scope (explicit):
- PPTX / native PDF / scanned-PDF parsers (→ Phase 3 / Phase 4)
- LAYOUT-02/03 format-specific overflow detectors (→ Phase 3, requires REQUIREMENTS.md edit)
- Translation memory / segment-version history (→ v2)
- Multi-user / multi-tenant / auth (→ v2 per PROJECT.md)
- Multi-select glossaries per job (→ v2)

</domain>

<decisions>
## Implementation Decisions

### Glossary data model
- **D-02-01:** Two-table relational schema — `glossaries(id, name, source_lang, target_lang, created_at, updated_at)` + `glossary_terms(id, glossary_id FK CASCADE, source_term, target_term, notes, created_at)`. No JSONB blob, no materialized view. Sub-ms lookups for expected PoC volume (<100 terms/glossary). LLM-swap portable — zero coupling to qwen-mt-turbo.
- **D-02-02:** Glossary is scoped to one language pair. `glossaries.source_lang` + `glossaries.target_lang` are required. User creates "AICore VN→EN" and "AICore VN→JA" as separate glossaries. Simpler picker UX + cleaner `terminology` injection (only relevant terms load).
- **D-02-03:** Term uniqueness: `(glossary_id, source_term)` unique constraint. Editing a term = PATCH row. No soft-delete (PoC scope).
- **D-02-04:** GLOS-02 CSV/TBX import: Phase 2 supports CSV only as the primary path; TBX is Claude's Discretion (see below). CSV schema TBD in plan phase (minimal headers: `source_term,target_term,notes`).

### Glossary injection (GLOS-03) — LLM-swap-aware
- **D-02-05:** `qwen-mt-turbo` keeps using the native `terminology` param via existing `glossary_to_terms()` helper in `backend/src/app/llm/terminology.py`. No change to call site.
- **D-02-06:** Swap-path documented: if the project later swaps qwen-mt-turbo for Claude Sonnet / GPT-5.5 / another LLM without a native terminology API, glossary injection becomes **prompt-text** — adapter lives at the LLM client boundary, DB schema + UI + post-check pass stay unchanged. Record this in the canonical refs of LLM client + translator modules as a future hook; no code in Phase 2.

### Glossary violation enforcement (GLOS-04)
- **D-02-07:** Post-translation check is **case-insensitive substring**: `target_term.lower() in translated_segment.lower()`. Minimum term length 2 characters to avoid spurious matches (e.g., "IT" inside "BIT"). Uniform across VN/EN/JA/ZH. Zero native deps, LLM-swap-portable.
- **D-02-08:** A violation = a `glossary_violation` row in `segment_flags` with `details JSONB = {"term": source_term, "expected": target_term}`. The flag surfaces a "re-translate with stricter prompt" hint in the UI, but the system never silently rewrites the translation.

### Segment-flags schema (REV-03)
- **D-02-09:** Separate `segment_flags` table (not denormalized columns, not a JSONB blob):
  ```
  segment_flags(id, segment_id FK CASCADE, flag_type ENUM, severity ENUM, details JSONB, created_at)
  ```
  `flag_type` enum: `overflow`, `glossary_violation`, `placeholder_mismatch`, `llm_refusal`. `severity` enum: `info`, `warn`, `block` (reserved for future; Phase 2 uses `warn` for all four types).
  Rationale: extensible to future flag types (e.g., `profanity`, `bias`) without Alembic churn; LLM-swap-portable; explicit flag history if we ever want per-flag metadata.
- **D-02-10:** Filter queries (e.g., "show me all glossary-violation segments") use a JOIN + `WHERE flag_type = 'glossary_violation'`. Index on `(segment_id, flag_type)`. UI counts per flag type on page load via one GROUP BY query.

### Text-expansion ratio (LAYOUT-01)
- **D-02-11:** Stored as `segments.expansion_ratio FLOAT` (nullable; populated on translation completion: `len(target) / len(source)`). Flag emitted when ratio > threshold for the job's `(source_lang, target_lang)` pair.
- **D-02-12:** Threshold is a **per-language-pair map** in Settings. Env var: `EXPANSION_RATIO_THRESHOLDS` as JSON string, e.g., `{"en->vi": 1.3, "vi->en": 0.9, "ja->vi": 1.5, "vi->ja": 0.9, "vi->zh": 0.85, "en->ja": 1.6}`. Initial values tuned empirically during Phase 2 testing; override via env without code change.

### LAYOUT-02/03 scope deferral
- **D-02-13:** LAYOUT-02 (PPTX text-box + PDF bbox overflow detectors) and LAYOUT-03 (PPTX auto-fit + PDF font scaling) **move to Phase 3**. Phase 2 ships LAYOUT-01 (expansion ratio) + the `segment_flags.overflow` enum slot + UI surface. Format-specific detectors implement against the actual format parsers that land in Phase 3.
- **Follow-up:** REQUIREMENTS.md Traceability table must move LAYOUT-02 + LAYOUT-03 from Phase 2 → Phase 3. ROADMAP.md §Phase 2/3 requirement lists updated to match.

### Review UI layout (REV-01)
- **D-02-14:** **CAT-tool segment table pattern**, not Monaco DiffEditor, not two-pane Monaco. Each segment = one row: `| # | source (read-only) | target (editable textarea) | flags |`. Follows Trados/memoQ/Phrase/Lokalise convention that translators recognize. Uses shadcn `Table` + `Textarea` per row. Zero Monaco bundle cost on this screen.
- **D-02-15:** Monaco was originally pinned in CLAUDE.md for the review phase; with CAT-table chosen, the Monaco editor is no longer used for translation review. `@monaco-editor/react` dep stays in `frontend/package.json` for now — re-evaluate removal after Phase 2 plan review. **Follow-up:** CLAUDE.md §"Frontend" table needs a note once Phase 2 ships.

### Large-document handling
- **D-02-16:** Virtualize the segment table with `react-virtuoso` (variable row heights — translations vary wildly). Only visible rows + small overscan render. Scales to 10k segments without browser lag. Adds one dep (~30KB gz).

### Segment-flag navigation
- **D-02-17:** Primary navigation = **filter bar + keyboard shortcuts**:
  - Filter chips at top: `All (N) | Overflow (n₁) | Glossary violation (n₂) | Placeholder (n₃) | Refusal (n₄)`. Click = list filters to flagged segments only.
  - Keyboard: `j` next segment, `k` prev, `n` next flag, `e` focus edit on current segment, `r` regenerate current segment. Shortcuts visible in a discoverable help panel (`?`).

### Edit persistence (REV-02)
- **D-02-18:** Debounce **500ms** on textarea `onChange` → PATCH `/segments/{id}` with `{edited_text}`. Tab-close safety window is ≤500ms.
- **D-02-19:** **Optimistic update** via TanStack Query — cache `setQueryData(['segments', jobId], ...)` immediately; background PATCH reconciles; rollback + toast on error. Reuses the cache-as-single-source-of-truth pattern from Phase 1 D-09.

### Single-segment regenerate (REV-04)
- **D-02-20:** Regenerate overwrites `segments.translated_text`; `segments.edited_text` is preserved untouched. Export (REV-05) formula: `edited_text ?? translated_text`. User must explicitly "discard edit" to adopt the new LLM output as the exported value.
- **D-02-21:** Regenerate uses the same glossary + language pair as the job (locked at submit per D-02-26). No per-regenerate glossary override.

### Export idempotency (REV-05, REV-06)
- **D-02-22:** Export writes to `.data/jobs/{job_id}/output.docx` (overwrite, same path as Phase 1 D-04). Export is idempotent — re-exporting produces the same output from the same `edited_text ?? translated_text` state; does not mutate segment rows. Segments are NOT locked during export (export reads a snapshot of the segment state at reassemble time). Concurrent re-export guard = simple advisory lock on `Job.id` during the reassemble stage (release on completion or failure).
- **D-02-23:** Export button visible only when job is in `done` or `needs_review` state. Button disabled while reassembly is running; re-enabled on completion.

### UPLD-04 glossary picker (deferred from Phase 1)
- **D-02-24:** Single-select dropdown on the upload form. Options: `None` (default) + glossaries matching the selected `(source_lang, target_lang)` pair. Multi-select deferred to v2.
- **D-02-25:** Picker **filters** to matching-pair glossaries only. Empty state when zero matches: "No glossary for this pair — create one" with a link to the glossary UI. Non-matching glossaries never appear (not greyed-out — hidden).
- **D-02-26:** Glossary is **locked at submit**. `jobs.glossary_id FK glossaries(id) ON DELETE SET NULL` stored at job creation; immutable for the job's lifetime. Changing glossary requires creating a new job.

### Paper design skill
- **D-02-27:** Pull `paper` skill via `npx typeui.sh pull paper` during Phase 2 setup. Keep the full font stack (Roboto / Montserrat / PT Mono). Apply paper tokens to `frontend/tailwind.config.ts`; migrate Phase 1 screens opportunistically (no mass rewrite — new Phase 2 screens are the priority).
- **D-02-28:** Primary `#111111` / secondary `#8B5CF6` from the skill are kept as-is. If AICore brand color is specified later, override the secondary token via Tailwind config without editing skill files.

### Claude's Discretion
- CSV column order + header variants accepted (`"source","target"` vs `"source_term","target_term"` etc.)
- TBX support depth (full TBX-Core subset or minimal term-pair extraction) — decide during plan
- `segment_flags.severity` enum default — likely `warn` for all four Phase 2 flag types
- Keyboard shortcut help panel style (? modal vs cheatsheet chip)
- Exact filter bar chip layout + counts rendering
- Advisory-lock implementation for export (pg advisory lock vs in-memory per-worker)
- Optimistic rollback toast copy
- Glossary table row density + bulk-delete UX
- Paper skill font loading strategy (next/font self-host vs Google Fonts CDN)
- Whether to rework Phase 1 screens to paper tokens in Phase 2 or defer to a polish pass

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level specs
- `.planning/PROJECT.md` — Core value, active requirements, out-of-scope list, key decisions
- `.planning/REQUIREMENTS.md` — All v1 requirements. Phase 2 owns GLOS-01..05, REV-01..06, LAYOUT-01 (NOTE: LAYOUT-02/03 move to Phase 3 per D-02-13; traceability table edit required before planning).
- `.planning/ROADMAP.md` §"Phase 2: Review UX + Glossary" — Goal, dependencies, success criteria

### Phase 1 carry-forward (MUST read to avoid re-deciding)
- `.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md` — All 20 Phase 1 decisions (D-01..D-20). Especially: D-04 (per-job `.data/jobs/{id}/` layout), D-05/D-06 (Segment tree + deterministic IDs), D-09/D-10 (hybrid SSE + TanStack transport), D-15 (glossary plumbing landed in Phase 1, CRUD deferred to Phase 2 — this phase fulfils it), D-20 (Next.js 16 + React 19 pin)
- `.planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md` §"Glossary injection" — `terminology` param shape in `translation_options`
- `.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md` §"Glossary + terminology" — qwen-mt-turbo behavior on terms present vs absent
- `.planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md` — Phase 1 codebase patterns to extend

### Technical stack & pipeline invariants
- `CLAUDE.md` §"Technology Stack" → specifically "DashScope SDK vs OpenAI-Compatible Endpoint", "Glossary / Terminology Injection", "FastAPI + Next.js for Long-Running Jobs" (Monaco DiffEditor reference is superseded by D-02-14)
- `CLAUDE.md` §"What NOT to Use" — `paragraph.text = value` forbidden (DOCX-02); `dashscope` SDK forbidden; relevant anti-patterns stay in force
- `CLAUDE.md` §"Version Compatibility Notes" — Pinned versions
- **Follow-up:** CLAUDE.md §"Frontend" needs a note after Phase 2 ships documenting the CAT-table choice over Monaco editor (D-02-14, D-02-15)

### Existing code to extend (not rewrite)
- `backend/src/app/db/models.py` — `Job` + `Segment` SQLAlchemy models. Phase 2 adds `Glossary`, `GlossaryTerm`, `SegmentFlag`; extends `Segment` with `edited_text`, `expansion_ratio`; extends `Job` with `glossary_id`.
- `backend/src/app/llm/terminology.py` — `glossary_to_terms()` helper is the injection boundary. Keep pristine; glossary load path in worker reads from DB and passes `dict[str, str]` in.
- `backend/src/app/llm/translator.py` — per-segment call site already accepts `glossary` kwarg; no change to translator, only to caller (worker) that sources glossary from DB.
- `backend/src/app/api/routes/glossaries.py` — **Phase 1 stub** returns empty list. Phase 2 replaces with full CRUD (list, create, get, update, delete, terms CRUD, CSV upload).
- `backend/src/app/api/routes/upload.py` — accepts multipart upload; extend with optional `glossary_id` Form field (UPLD-04).
- `backend/src/app/services/job_service.py` — extend to persist `glossary_id` + load glossary terms for worker.
- `backend/src/app/workers/translate_worker.py` (or equivalent arq entry) — load job's glossary terms → dict, pass to translator; on batch completion, run post-check + write `segment_flags` rows.
- `backend/src/app/pipeline/docx/reassembler.py` — export path; extend to use `edited_text ?? translated_text`; ensure idempotent reads.
- `frontend/src/app/jobs/[id]/page.tsx` — current status page. Phase 2 replaces/augments with the review editor route (likely `/jobs/[id]/review`).
- `frontend/src/components/UploadForm.tsx` — add glossary picker (UPLD-04).
- `frontend/src/components/ui/*` — existing shadcn primitives (table, badge, dialog, select, separator) all reusable.
- `frontend/src/hooks/useJobProgress.ts` — TanStack-Query + SSE pattern to extend for segment state.

### External library docs (context7-verified Phase 1 set — reuse)
- `/sysid/sse-starlette` — no changes in Phase 2 (status stream stays)
- `/websites/tanstack_query` — new use: optimistic mutations via `onMutate` / `onError` rollback
- `python-docx` 1.2.0 — run-merge strategy extended for the reassembler's `edited_text ?? translated_text` path (DOCX-02 invariant stays)

### New external deps (to vet in plan phase via context7 / docs)
- `react-virtuoso` — list virtualization for the segment table (D-02-16)
- `typeui.sh` CLI — pull `paper` skill (D-02-27). `bergside/awesome-design-skills` registry path: `skills/paper/SKILL.md`

### Paper design skill
- `SKILL.md` to be written to the frontend project root (or provider path) by `npx typeui.sh pull paper`. After pull, path becomes a canonical ref for planner + executor to align component styling decisions with. Source: https://raw.githubusercontent.com/bergside/awesome-design-skills/main/skills/paper/SKILL.md

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets (from Phase 1)
- **shadcn/ui primitives already installed**: `table`, `badge`, `button`, `dialog`, `select`, `skeleton`, `separator`, `radio-group`, `toast`, `alert`, `label`, `collapsible`, `progress`. Covers 100% of Phase 2's glossary CRUD + segment-table UI needs.
- **TanStack Query provider + toast provider** in `frontend/src/components/providers/`. `useQuery` cache pattern is the basis for optimistic segment edits.
- **`useJobProgress` hook** — SSE + polling-fallback pattern ready to extend for per-segment state.
- **Radix primitives** (`@radix-ui/react-*`) cover dropdowns, dialogs, radios — zero new Radix deps expected.
- **`fetch-event-source` + `@tanstack/react-query`** — already wired. Segment state can reuse the same cache key pattern (`['segments', jobId]`).
- **DOCX reassembler** (`backend/src/app/pipeline/docx/reassembler.py`) — round-trip proven in Phase 1; Phase 2 extends the text-source rule (`edited_text ?? translated_text`).
- **LLM glossary plumbing** (`glossary_to_terms` in `llm/terminology.py`) — live today; Phase 2 feeds real glossaries into it.
- **Alembic migration scaffold** — Phase 1 migration in place; Phase 2 adds a new migration for `glossaries`, `glossary_terms`, `segment_flags`, `segments.edited_text`, `segments.expansion_ratio`, `jobs.glossary_id`.

### Established Patterns (from Phase 1)
- **Async FastAPI + SQLAlchemy 2.0 async + asyncpg + Alembic** — all Phase 2 DB work follows this stack.
- **Pydantic V2 immutable DTOs** (`frozen=True`) — all Phase 2 request/response schemas follow.
- **Structured JSON logging with bound `job_id`** — extend with `segment_id` + `glossary_id` context vars for Phase 2 operations.
- **Hybrid SSE + TanStack cache** (D-09) — not used for segment edits (optimistic PATCH is synchronous); SSE stays for job status only.
- **Per-job file layout** (`.data/jobs/{job_id}/...`) — output.docx overwrite on re-export (D-02-22).
- **Alembic-managed schema** — every new table / column needs a migration file.

### Integration Points
- **Upload form → `POST /upload`**: add optional `glossary_id` Form field. Backend 422 if glossary's pair mismatches job's pair.
- **Worker → DB**: load job's glossary terms at batch prep; pass `dict[str, str]` into `translator.translate_batch(..., glossary=...)`.
- **Worker → post-check**: after `translated_text` is NFC-normalized + persisted, run per-term substring check; write `segment_flags` rows for violations.
- **Worker → expansion ratio**: compute on each completed segment; write `segments.expansion_ratio`; emit `overflow` flag if ratio > threshold for `(source_lang, target_lang)`.
- **Review UI → `GET /jobs/{id}/segments`**: new endpoint returning paged segment list + flags. TanStack Query with `['segments', jobId]` cache key.
- **Review UI → `PATCH /segments/{id}`**: debounced edit persistence + optimistic update.
- **Review UI → `POST /segments/{id}/regenerate`**: re-translate single segment with job's glossary.
- **Review UI → `POST /jobs/{id}/export`**: reassemble DOCX using `edited_text ?? translated_text`; write to `output.docx` (overwrite).
- **Glossary CRUD → `/glossaries` routes**: replace the Phase 1 stub with full REST surface (list, POST create, GET :id, PATCH :id, DELETE :id, POST :id/terms/upload).

</code_context>

<specifics>
## Specific Ideas

- **"Looks like a document we translated"** — paper skill's print-inspired aesthetic is the demo narrative handle. AICore will see tokens + typography that reinforce "this is a document translation tool" at the frame level.
- **LLM-swap-first design** — schema + post-check + UI all stay portable if qwen-mt-turbo is later swapped for Claude Sonnet / GPT-5.5 / another LLM. Only the glossary-injection adapter (native `terminology` param → prompt-text) changes. Record this explicitly in translator module docs for the future maintainer.
- **CAT-tool pattern** over Monaco DiffEditor — reviewers coming from Trados/memoQ/Phrase will feel at home. Flag badges + expansion-ratio + per-segment regenerate all slot naturally into the row pattern.
- **Keyboard-first review** — `j/k/n/e/r` shortcuts exist so Thu can drive the demo without touching the mouse. Paper skill mandates visible focus states, which reinforces keyboard nav.
- **Single glossary per job, pair-scoped** — "one job = one intent" keeps the demo story clean. Multi-glossary is a v2 concern when real customers start mixing terminology sets.
- **Segment flags as a separate table** — extensible to future flag types (profanity, bias, domain-specific checks) without schema churn. Supports the AICore narrative of "we can keep adding quality gates."

</specifics>

<deferred>
## Deferred Ideas

### Moved to Phase 3 (format-specific detectors)
- **LAYOUT-02** — PPTX text-box + PDF bbox overflow detectors (land with format parsers)
- **LAYOUT-03** — PPTX auto-fit (MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE) + PDF font scaling within ±2pt

### Moved to v2 (post-PoC)
- **Multi-select glossaries per job** — union of term lists; conflict resolution rules + UI
- **Translation memory (TM-01)** — sha-indexed cache of prior segment translations. Phase 1 D-06's deterministic segment IDs are the hook.
- **Segment-version history** — `segment_translations` table with per-version metadata; pick-active-version UI
- **Per-job expansion threshold override** — user-settable at submit time
- **Token-aware per-language tokenizers** (jieba / fugashi / underthesea) for stricter violation matching — heavy deps (~170MB Docker growth) without demo payoff
- **Collaborative review / assignment** (COLLAB-01, APPROVE-01) — multi-user workflow per REQUIREMENTS.md v2
- **Full TBX-v3 import** — Phase 2 ships CSV + minimal TBX-Core subset as Claude's Discretion; full TBX is v2
- **Soft-delete on glossary terms** — Phase 2 hard-deletes; soft-delete + audit trail is a v2 concern

### Out-of-scope per PROJECT.md
- **Per-segment LLM streaming to UI** — polling/SSE is sufficient for the PoC
- **Multi-tenant auth / workspaces** — PoC is single-team internal
- **Rate-limit tiers / billing** — not a PoC concern

### Follow-ups (must happen before or during Phase 2 execution)
- **REQUIREMENTS.md edit** — move LAYOUT-02 + LAYOUT-03 traceability from Phase 2 → Phase 3 (D-02-13). Update Phase 2 requirement count from 14 → 12 and Phase 3 from 8 → 10.
- **ROADMAP.md edit** — update Phase 2 Requirements list and Phase 3 Requirements list in §"Phase Details" + Traceability to match.
- **CLAUDE.md note** — after Phase 2 ships, add a note to §"Frontend" that the review editor uses a CAT-tool segment table (not Monaco DiffEditor) per D-02-14.

</deferred>

---

*Phase: 02-review-ux-glossary*
*Context gathered: 2026-04-24*
