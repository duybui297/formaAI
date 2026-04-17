# Phase 1: Foundation + DOCX Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `01-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-17
**Phase:** 01-foundation-docx-pipeline
**Areas discussed:** Repo layout & dev topology, Segmentation & batching strategy, Job status UX (transport + error detail), DOCX edge cases + Phase 1 glossary scope, Language detection, Concurrency & infra

---

## Repo layout & dev topology

### Repository layout

| Option | Description | Selected |
|--------|-------------|----------|
| Monorepo: backend/ + frontend/ | One git repo, two top-level dirs. Shared .env.example, single docker-compose.yml, single README. | ✓ |
| Monorepo: apps/ + packages/ | apps/api + apps/web; reserves a packages/ slot for shared types later. | |
| Two separate repos | ai-translation-api + ai-translation-web. Cleaner separation, separate deploy cycles. | |

**User's choice:** Monorepo: backend/ + frontend/

### Backend Python package structure

| Option | Description | Selected |
|--------|-------------|----------|
| Domain-oriented | `src/app/{api,services,pipeline,db,core,workers}` | ✓ |
| Flat by responsibility | routes.py, services.py, models.py, pipeline.py | |
| DDD-lite feature modules | Each feature self-contained (translation/, jobs/, docx/) | |

**User's choice:** Domain-oriented (Recommended)

### docker-compose topology

| Option | Description | Selected |
|--------|-------------|----------|
| Everything in compose | api + worker + web + postgres + redis all in compose, bind-mounted src for hot reload | ✓ |
| Infra in compose, apps local | Only postgres + redis in compose; FastAPI + Next.js run on host | |
| Split: dev-compose + demo-compose | Two configs, one for local work, one for demo | |

**User's choice:** Everything in compose (Recommended)

### File storage layout

| Option | Description | Selected |
|--------|-------------|----------|
| `.data/jobs/{job_id}/{source,output}.ext` | One directory per job, easy cleanup and debugging | ✓ |
| Flat directories by type | uploads/, outputs/, logs/ with {job_id}.ext | |
| Postgres bytea / large objects | Store file blobs in postgres | |

**User's choice:** `.data/jobs/{job_id}/...` (Recommended)

---

## Segmentation & batching strategy

### Segment serialization

| Option | Description | Selected |
|--------|-------------|----------|
| Document-order walk, one Segment per translatable unit | Flat list, each paragraph / cell = 1 Segment | |
| Structural tree with nesting | Parent references (para → cell → row → table) | ✓ |
| Sentence-level segmentation | Split paragraphs into sentences before sending | |

**User's choice:** Structural tree with nesting
**Notes:** Chosen to carry schema forward to PPTX/PDF (Phase 3) without a mid-sprint migration.

### Batch size

| Option | Description | Selected |
|--------|-------------|----------|
| Token-budgeted batches, ~2-4K input tokens | Pack until next would exceed budget | ✓ |
| Fixed N=20 segments | Simple to reason about; ignores paragraph length variance | |
| One segment per call | Blows latency and quota budgets | |

**User's choice:** Token-budgeted batches (Recommended)

### Segment ID scheme

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic sha256(source_text + position) | Job-independent; enables v2 translation memory | ✓ |
| Sequential integer per job | Readable in logs; not reusable across jobs | |
| UUIDv7 per segment | Time-sortable; overkill for single-worker PoC | |

**User's choice:** Deterministic sha256 (Recommended)

### Long paragraph handling

| Option | Description | Selected |
|--------|-------------|----------|
| Own single-segment batch; fail loudly if over context | Keeps run-merge intact | ✓ |
| Sentence-split on overflow | Breaks run-merge for those segments | |
| Hard character cap + reject upload | Worst UX | |

**User's choice:** Own single-segment batch (Recommended)

---

## Job status UX — transport + error detail

### Transport

| Option | Description | Selected |
|--------|-------------|----------|
| SSE via sse-starlette | Server pushes events; auto-reconnect lib-side | |
| TanStack Query polling, 1s | Zero server-push complexity | |
| Hybrid: polling for list, SSE for detail | More code paths | |
| **Both together (user-requested, research-backed)** | SSE primary + TanStack cache + polling fallback | ✓ |

**User's choice:** Both together — user asked for research on latest libs and a recommendation. After querying current context7 docs for `/sysid/sse-starlette` and `/websites/tanstack_query`, the recommended hybrid was presented and accepted.

**Locked-in pattern:**
- Server: `sse-starlette` `EventSourceResponse` + Redis pub/sub keyed by job_id
- Client: `@microsoft/fetch-event-source` calls `queryClient.setQueryData` on every event
- Fallback: `useQuery` with dynamic `refetchInterval` (2s, stop on terminal), suppressed while SSE OPEN

### Progress payload shape

| Option | Description | Selected |
|--------|-------------|----------|
| Counters + current stage + last message | `{status, segments_done, segments_total, stage, current_batch, retry_count, last_message}` | ✓ |
| Counters only | Loses stage visibility | |
| Full segment list per event | Huge payload; Phase 2 concern | |

**User's choice:** Counters + current stage + last message (Recommended)

### Error surface

| Option | Description | Selected |
|--------|-------------|----------|
| Banner + expandable details + failing segment(s) | Banner, expand for HTTP error + source_text | ✓ |
| Banner only; full detail in server logs | Simpler; worse demo experience | |
| Inline error rows per failing segment | Batch-report style; more UI for uncommon case | |

**User's choice:** Banner + expandable details (Recommended)

### In-progress retry surfacing

| Option | Description | Selected |
|--------|-------------|----------|
| Retry count badge + non-alarming message | "Retrying batch 7 (2/3)" subdued | ✓ |
| Silent until final failure | Violates CORE-06 ("surface retries as progress") | |
| Retry event log panel | Transparent; noisy | |

**User's choice:** Retry count badge (Recommended)

---

## DOCX edge cases + Phase 1 glossary scope

### Tracked changes default

| Option | Description | Selected |
|--------|-------------|----------|
| Detect → prompt on upload form | Modal: strip, preserve, cancel | ✓ |
| Always strip with banner | Simpler UX; risky data loss | |
| Always preserve | Messy output | |

**User's choice:** Detect → prompt on upload form (Recommended)

### Comments default

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve + translate comment text | First-class Segments with `is_comment=true` | ✓ |
| Preserve structurally, skip translation | Leaves untranslated text in output | |
| Strip all comments + banner | Destroys reviewer notes | |

**User's choice:** Preserve + translate comment text (Recommended)

### Phase 1 glossary scope

| Option | Description | Selected |
|--------|-------------|----------|
| Wire terminology pass-through, skip glossary UI | INFRA-02 via unit test; no picker in Phase 1 | ✓ |
| Ship full terminology + env-configurable default glossary | Demo-quality terminology before Phase 2 CRUD | |
| Defer UPLD-04 entirely | INFRA-02 as health-check spike only | |

**User's choice:** Wire terminology pass-through, skip glossary UI (Recommended)
**Notes:** UPLD-04 effectively deferred to Phase 2.

### Auto-detect source language

| Option | Description | Selected |
|--------|-------------|----------|
| Pass `source_lang='auto'` to qwen-mt-turbo | Native support; no extra dep | ✓ |
| Client-side detect then lock | `lingua-py`; more deterministic per-job | |
| Skip auto-detect in Phase 1 | Violates UPLD-03 / LANG-01 | |

**User's choice:** `source_lang='auto'` (Recommended)

---

## Concurrency & infra

### Worker concurrency

| Option | Description | Selected |
|--------|-------------|----------|
| 2 workers, 4 parallel batches/job | Demo resilience + bounded rate-limit blast | ✓ |
| 1 worker, sequential | Slowest, single point of failure | |
| 1 worker, 8 parallel batches | Max throughput, min fault tolerance | |

**User's choice:** 2 workers, 4 parallel batches per job (Recommended)

### INFRA-01 health-check scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full stack check | DashScope + terminology + Postgres + Redis + fonts | ✓ |
| DashScope only | Misses Phase 5 DEMO-02 coverage | |
| Split into two scripts | Duplicated bootstrapping | |

**User's choice:** Full stack check (Recommended)

### Logging

| Option | Description | Selected |
|--------|-------------|----------|
| Structured JSON to stdout + per-job errors.log | structlog + bound job_id | ✓ |
| Plain text to stdout | Hard to grep by job_id | |
| JSON stdout + single rolling file | Still grep-by-id | |

**User's choice:** Structured JSON + per-job errors.log (Recommended)

---

## Claude's Discretion

- Exact token-budget value in 2-4K range (tune on sample doc)
- Redis pub/sub channel naming vs sorted-set progress key
- Upload form component choices (shadcn/ui vs plain Tailwind)
- Alembic autogenerate flow + migration file naming
- Exact JSON log line fields beyond "structured"
- Dockerfile base image specifics

## Deferred Ideas

- Glossary picker + CRUD (Phase 2 per D-15)
- UPLD-04 effectively moves to Phase 2
- Per-segment LLM streaming to UI (already out-of-scope in PROJECT.md)
- Translation memory v2 (D-06 provides the hook)
- Observability stack (v2)
- Auth + multi-tenancy (v2)
