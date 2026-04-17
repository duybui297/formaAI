# Phase 1: Foundation + DOCX Pipeline - Context

**Gathered:** 2026-04-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Validate DashScope + `qwen-mt-turbo` from the dev machine, stand up the full docker-compose stack (FastAPI + arq worker + Next.js + Postgres + Redis), and ship DOCX translation end-to-end with every pipeline correctness invariant active from day one (segment-count assertion, NFC normalization, `⟦T{n}⟧` placeholder protection, run-merge strategy, Noto fonts). Glossary CRUD, PPTX, PDF, and OCR belong to later phases.

</domain>

<decisions>
## Implementation Decisions

### Repo layout & dev topology
- **D-01:** Monorepo with `backend/` + `frontend/` top-level dirs. Single `docker-compose.yml` and `.env.example` at root.
- **D-02:** Backend Python package layout is domain-oriented:
  `src/app/{api,services,pipeline,db,core,workers}/...` with `main.py` as the FastAPI entry and `workers/translate_worker.py` as the arq entry.
- **D-03:** docker-compose brings up everything locally: `api` (uvicorn with `--reload` and bind-mounted `backend/src`), `worker` (arq, same image as api), `web` (Next.js dev with bind-mounted `frontend/src`), `postgres`, `redis`. Single `docker-compose up`. Pin pgdata volume for persistence across restarts.
- **D-04:** On-disk file layout is per-job: `.data/jobs/{job_id}/source.{ext}`, `.data/jobs/{job_id}/output.{ext}`, plus `segments.json` (debug dump) and `errors.log` (durable per-job error tail). `.data/` gitignored. `Job.input_path` / `Job.output_path` in Postgres reference these paths.

### Segmentation & batching strategy
- **D-05:** DOCX content is serialized into a **structural tree of Segments**. Each Segment carries a parent reference (paragraph → cell → row → table → body) so reassembly can walk the tree back into OOXML. Reading order is preserved via sibling ordering within each parent. This schema is deliberately richer than a flat list because PPTX and PDF (later phases) will reuse it.
- **D-06:** Segment ID is `sha256(source_text + structural_position)[:16]`. Deterministic and job-independent — unlocks translation-memory reuse in v2 without a schema migration. Sequential `seq_in_job` is also stored for human-readable logs (`segment 143/210`).
- **D-07:** Translation batching is **token-budgeted**: pack Segments into a batch until the next Segment would exceed `~2-4K input tokens` (configurable via env). One `qwen-mt-turbo` call per batch. The segment-count assertion (CORE-03) runs per batch.
- **D-08:** A Segment whose source text alone exceeds the batch budget is sent as its own single-segment batch. If it still exceeds the qwen-mt-turbo 1M context window, the job fails loudly with a clear error pointing to the offending paragraph (`segment {id}, {N} tokens`). We never silently sentence-split — that would break the run-merge invariant (DOCX-02).

### Job status UX — transport + error detail
- **D-09:** **Hybrid transport: SSE primary, TanStack Query cache + polling fallback.**
  - Server: `sse-starlette` `EventSourceResponse` on `GET /jobs/{id}/stream`. Async generator tails job state from Redis pub/sub (key: `job:{id}`) that the arq worker writes to on every progress change. `ping=15s`, closes stream on terminal state or `request.is_disconnected()`.
  - Client: `@microsoft/fetch-event-source` opens the stream and calls `queryClient.setQueryData(['job', jobId], newState)` on every event. All UI components read via `useQuery(['job', jobId])` — the TanStack cache is the single source of truth.
  - Fallback: `useQuery` has `refetchInterval: (q) => isTerminal(q.state.data?.status) ? false : 2000`, suppressed while `eventSource.readyState === OPEN`.
- **D-10:** SSE/job payload shape:
  `{ status: 'queued'|'running'|'needs_review'|'failed'|'done', stage: 'parse'|'translate'|'reassemble'|'done'|'failed', segments_done: int, segments_total: int, current_batch: int, retry_count: int, last_message: str, error?: { code, message, failing_segments: [{id, source_text, batch_id}] } }`
- **D-11:** Error surface on the job status page: top-level banner (`Translation failed after 3 retries on batch 7`) + expandable details pane showing the DashScope HTTP error and the source_text of the failing segment(s). Full traceback is NOT rendered in the UI — it goes to the per-job `errors.log` for developer debugging.
- **D-12:** Retries (CORE-06) surface as `Retrying batch 7 (2/3)` in a subdued text chip next to the progress bar — non-alarming, progress bar keeps advancing. Red coloring is reserved for terminal failures.

### DOCX edge cases + Phase 1 glossary scope
- **D-13:** Tracked changes (DOCX-04): detect `<w:ins>`/`<w:del>` on upload. If present, the upload form shows a modal with three choices before job creation: (a) strip before translating, (b) preserve and translate both inserted and deleted text, (c) cancel. No silent data loss.
- **D-14:** Comments (DOCX-04): preserve + translate. Extract comment bodies as first-class Segments with `is_comment=true`; author metadata preserved. Translated comments appear in the output DOCX in the target language.
- **D-15:** Phase 1 glossary scope: **wire the `terminology=[...]` plumbing in the qwen client + cover INFRA-02 with a unit/integration test that proves qwen-mt-turbo respects the param on a VN↔EN and VN↔JA sample. Do NOT add a glossary picker to the Phase 1 upload form.** Full glossary CRUD and picker UI belong to Phase 2. UPLD-04 is effectively deferred to Phase 2 per this decision — note in STATE.md when Phase 1 ships.

### Language detection
- **D-16:** Auto-detect source language is handled by `qwen-mt-turbo` natively: pass `source_lang='auto'` in the translation_options. The detected language from the API response metadata is persisted on the Job row and shown in the UI ("Detected: Vietnamese"). No separate detection library.

### Frontend framework version
- **D-20 (added 2026-04-17 after deeper research):** Pin **Next.js `^16.2.3`** + **React 19**, not Next.js 15 as originally sketched in CLAUDE.md. Next.js 16 was released Oct 2025 and is six months into stable point releases; greenfield projects skip the 15→16 migration pain entirely (async `cookies()`/`headers()`/`params`/`searchParams` — we write async from day one; Turbopack default — we have no webpack config to break; `middleware.ts` → `proxy.ts` rename — cosmetic, we have no edge middleware; new `"use cache"` directive — clearer mental model for new code). `@tanstack/react-query` v5 has official Next 16 support; `@monaco-editor/react` (for Phase 2) works unchanged via the existing `dynamic(() => import, { ssr: false })` pattern. Keep `@microsoft/fetch-event-source` (per user direction) — unmaintained library but compatible with Next.js 16 and gives us custom-header support we'll want when auth lands in v2. **Follow-up:** CLAUDE.md needs a small update to reflect Next.js 16 pinning after Phase 1 ships.

### Concurrency & infra
- **D-17:** arq worker topology: **2 worker processes** (demo resilience — one dying doesn't halt the demo). Each job runs on a single worker, but within that worker up to **4 batches translate concurrently via `asyncio.gather`**. This caps per-job DashScope concurrency at 4 (rate-limit blast radius bounded).
- **D-18:** `scripts/healthcheck.py` (INFRA-01) covers the full stack end-to-end: DashScope intl endpoint reachable + `qwen-mt-turbo` responds to a 1-sentence VN→EN probe, `terminology` param behavior (INFRA-02: documented output on glossary term present vs absent), Postgres reachable + Alembic migrations at head, Redis reachable + arq queue writable, Noto CJK + Noto Sans Vietnamese fonts present at expected paths. Same script gets reused in Phase 5 DEMO-02.
- **D-19:** Logging: `structlog` emitting JSON to stdout (captured by `docker logs`). `job_id` is bound as a context var on every log line inside the worker. Per-job errors are also appended to `.data/jobs/{job_id}/errors.log` for durable debugging and to source the "view details" content in the status UI.

### Claude's Discretion
- Exact token-budget default value within the 2-4K range (tune empirically on a sample doc).
- Redis pub/sub channel naming vs sorted-set progress key (either works for the SSE tailer).
- Upload form layout and component choices (shadcn/ui vs plain Tailwind).
- Alembic migration file naming and autogenerate flow.
- Error-log line format (beyond "structured JSON").
- Exact Dockerfile base image (`python:3.12-slim-bookworm` assumed; `apt-get install fonts-noto-cjk fonts-noto` + `fc-cache -f`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project-level specs
- `.planning/PROJECT.md` — Core value, active requirements, out-of-scope list, key decisions
- `.planning/REQUIREMENTS.md` — All v1 requirements with IDs; Phase 1 owns INFRA-01..05, UPLD-01..05, CORE-01..06, JOB-01..04, DOCX-01..04, LANG-01..02 (26 total)
- `.planning/ROADMAP.md` §"Phase 1" — Goal, dependencies, success criteria

### Technical stack & pipeline invariants
- `CLAUDE.md` §"Technology Stack" — Full locked stack (qwen-mt-turbo via openai SDK against DashScope intl, FastAPI, Next.js 15, Postgres 16, Redis 7, arq 0.27, SQLAlchemy 2.0 async, sse-starlette, @microsoft/fetch-event-source, TanStack Query 5, Monaco DiffEditor)
- `CLAUDE.md` §"What NOT to Use" — Explicit anti-patterns (qwen3-max for bulk; `paragraph.text = value` destroys run formatting; Tesseract for JA; FastAPI BackgroundTasks for translation jobs; dashscope SDK over openai SDK; pdf2docx as primary path; ReportLab for CJK)
- `CLAUDE.md` §"Version Compatibility Notes" — Pinned versions and Python compatibility

### Project research
- `.planning/research/STACK.md` — Stack rationale for each choice
- `.planning/research/ARCHITECTURE.md` — Architecture sketch feeding the decisions above
- `.planning/research/FEATURES.md` — Feature-level research
- `.planning/research/PITFALLS.md` — Known-hard problems (text expansion, OCR quality, segment-level context loss, OOXML quirks) — must be read before pipeline implementation

### External library docs (context7-verified)
- `/sysid/sse-starlette` — `EventSourceResponse`, async generator pattern, `ping`, `is_disconnected()`
- `/websites/tanstack_query` — `useQuery` with dynamic `refetchInterval`, `setQueryData` from external source (SSE), query cache invalidation
- `python-docx` 1.2.0 — Run-merge strategy per DOCX-02 (reconstruct para text, write into `para.runs[0]`, blank `para.runs[1:]`)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **None** — Phase 1 is greenfield. No existing source in the repo yet; only planning artifacts.

### Established Patterns
- **From Thu's prior stacks (scala-i-ask, ICOM-P3):** async FastAPI, SQLAlchemy 2.0 async + asyncpg + Alembic, Pydantic V2 + pydantic-settings (`SecretStr` for API keys, `secrets_dir` friendly), domain-oriented `src/app/` layout, `openai` SDK client construction with custom `base_url` (already used against Azure OpenAI in ICOM-P3 — same shape points at DashScope intl).
- **From CLAUDE.md conventions:** `uv` for all Python dep work; ruff + pyright on PostToolUse; structured JSON logging; Pydantic models as DTOs; Protocol for structural subtyping; composition over inheritance; multi-tenant isolation patterns (not needed for Phase 1 — no auth — but patterns transfer to per-job isolation).

### Integration Points
- **DashScope intl** — `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` via the `openai` Python SDK with `api_key` from `DASHSCOPE_API_KEY`. `terminology` parameter passed via `extra_body={"translation_options": {"terminology": [...], "source_lang": "auto", "target_lang": "..."}}`.
- **Frontend → Backend** — Next.js `/api/*` proxied to FastAPI at compose-service DNS (`api:8000`). CORS configured for the Next.js dev origin.
- **Worker ↔ API progress channel** — Redis pub/sub `job:{id}` written by the arq worker; SSE endpoint in the api service subscribes and streams.

</code_context>

<specifics>
## Specific Ideas

- **Health-check script doubles as demo-day confidence** — Thu reuses the same `scripts/healthcheck.py` in Phase 5 (DEMO-02) as the pre-demo smoke.
- **Segment tree is forward-looking** — chose the heavier schema now so PPTX groups and PDF column blocks plug into the same shape in Phase 3, rather than migrating mid-sprint.
- **"Translating while you watch"** — the 143/210 live counter is a core demo beat; the hybrid SSE + TanStack setup exists specifically to keep that counter smooth even on flaky wifi (polling catches up if SSE drops).

</specifics>

<deferred>
## Deferred Ideas

- **Glossary picker + CRUD in upload form** — Phase 2 per D-15. UPLD-04 effectively moves with it.
- **Per-segment LLM streaming to UI** — Already in PROJECT.md out-of-scope; polling/SSE progress is sufficient.
- **Translation memory / sha-indexed cache** — D-06's deterministic IDs are a design hook for v2 TM-01; no code in Phase 1.
- **Observability / traces / dashboards** — v2 per PROJECT.md; stdout JSON logging is sufficient for the PoC.
- **Auth + multi-tenancy** — v2; Phase 1 is single-user single-team.
- **Rate-limit measurement & dynamic batch-size adaptation** — STATE.md notes DashScope intl limits aren't published; measure during Phase 1 testing but keep the config value static for the demo.
- **`qwen3.6-plus` as VLM OCR path (Phase 4 hook)** — Verified 2026-04-17: `qwen3.6-plus` is live on DashScope (released 2026-04-02) and is multimodal with 1M context. Does NOT replace `qwen-mt-turbo` for translation (no native `terminology` param, no `translation_options`, higher cost, general vs specialized). DOES become a candidate for Phase 4 scanned-PDF OCR as a single-model OCR+translate path alongside PaddleOCR PP-OCRv5. Re-evaluate when Phase 4 kicks off.

</deferred>

---

*Phase: 01-foundation-docx-pipeline*
*Context gathered: 2026-04-17*
