# Backend Architecture

Aggregate view of the AI Translation PoC backend. Per-module detail lives in each module's own `ARCHITECTURE.md` (linked below). For stack + run instructions see [`BACKEND.md`](./BACKEND.md).

## 1. Layers

```
api/          HTTP edge — FastAPI routers, DI (deps.py), CORS, auth dependencies
schemas/       pydantic request/response DTOs (separate from ORM)
services/      business logic — job state machine, glossary CRUD, export
workers/       arq async worker — runs translation jobs off the request path
llm/           Qwen/DashScope translation engine (batching, glossary, token budget)
pipeline/      format-aware extract → reassemble (docx/pdf/pptx + scanned OCR)
db/            SQLAlchemy 2.0 async ORM models, session, Alembic migrations
core/          cross-cutting: config (Settings), logging (structlog), security (JWT/bcrypt)
main.py        app factory + lifespan (engine, redis, arq pool, llm client)
```

Request path is **thin**: routes validate (schemas) → call services → return DTOs. Heavy work (translate a document) is enqueued to arq and runs in `workers/`, reporting progress over Redis → SSE.

## 2. Modules

| Module | Purpose | Doc |
|--------|---------|-----|
| api | FastAPI routers, DI, CORS, auth deps | [api/ARCHITECTURE.md](./src/app/api/ARCHITECTURE.md) |
| schemas | pydantic request/response models | [schemas/ARCHITECTURE.md](./src/app/schemas/ARCHITECTURE.md) |
| services | job FSM, glossary CRUD, export | [services/ARCHITECTURE.md](./src/app/services/ARCHITECTURE.md) |
| workers | arq translation worker | [workers/ARCHITECTURE.md](./src/app/workers/ARCHITECTURE.md) |
| llm | DashScope translate, terminology, token budget | [llm/ARCHITECTURE.md](./src/app/llm/ARCHITECTURE.md) |
| pipeline | per-format extract/reassemble + OCR | [pipeline/ARCHITECTURE.md](./src/app/pipeline/ARCHITECTURE.md) |
| db | ORM models, session, migrations | [db/ARCHITECTURE.md](./src/app/db/ARCHITECTURE.md) |
| core | config, logging, security | [core/ARCHITECTURE.md](./src/app/core/ARCHITECTURE.md) |

## 3. Composition root (main.py)

`lifespan` builds shared resources **once** and injects them via `app.state` + DI:
- SQLAlchemy `AsyncEngine` (pool 5/+10; SQLite skips pool args for tests)
- Redis async client (progress pub/sub)
- **arq pool created once** (`get_arq_pool()` dependency — never per-request)
- shared LLM client (sync segment regenerate endpoint)

Startup order: logging → engine → redis → arq pool → llm. Teardown reverse. Routers mounted flat (no prefix).

## 4. End-to-end job lifecycle

```
POST /upload ─► save file {data_dir}/jobs/{job_id}/ ─► job_service.create (status=queued)
            ─► enqueue arq translate_job ─► 202 {job_id}

worker translate_job(ctx, job_id):
  queued → running
  pipeline extract  (docx | pdf | pptx | scanned_pdf by format)
  llm.translate_batch  (worker_concurrency batches, glossary terminology)
  persist Segment rows + flags
  pipeline reassemble
  → done   (on exception: re-raise → arq marks failed)
  progress each step ─► Redis channel ─► SSE GET /jobs/{id}/stream ─► client

review:  GET /jobs/{id}/segments → PATCH edit / POST regenerate (sync LLM)
export:  POST /jobs/{id}/export → reassemble final → GET /jobs/{id}/download
```

**Job status FSM** (in `job_service`): `queued → running → done | failed`. `needs_review` is an exportable status surfaced by flags/OCR confidence, not a transition written by `job_service` — see services doc.

## 5. Data model (db)

`Job` 1─* `Segment` 1─* `SegmentFlag`. `Glossary` 1─* `GlossaryTerm`; `Job` references a glossary + `User`. `User` 1─* `PasswordResetToken`. Enums: `JobStatus`, `JobStage`, `TrackedChangesAction`, `FlagType`, `FlagSeverity`. Alembic chain: init → phase-2 glossary/flags → segment compound PK → flag-type phase 3 → widen flag → phase-4 OCR → job low_confidence_pages → auth users → job glossary/user_id → seed default user.

## 6. Translation engine (llm)

`make_llm_client` → `AsyncOpenAI` against DashScope intl compat endpoint (`qwen-mt-turbo`). `translate_batch`: NFC-normalize, passthrough detection (skip non-text), sentinel-escape table cells, dedup, token-budgeted packing (`token_budget.py`, tiktoken), glossary via native `terminology` param (`terminology.py`). Frozen pydantic schemas for I/O.

## 7. Pipeline

Shared: `segment.py` (segment abstraction), `placeholder.py` (protect non-translatable tokens). Per format: `extractor` pulls translatable segments preserving structural refs, `reassembler` writes translations back.
- **docx** — run-level replacement; tracked-changes handling (`tracked.py`).
- **pdf** — PyMuPDF redact-and-reinsert; Noto font embedding (`fonts.py`); multi-column reorder (`columns.py`); overflow detection.
- **pptx** — shapes/tables/notes; SmartArt (`smartart.py`).
- **scanned_pdf** (OCR) — `detector` routes by text density → `extractor` (PaddleOCR PP-StructureV3) → `segment_to_md` → `composer` (fpdf2 rebuild).
Flags raised: `overflow`, `smartart`, `multi_column_degraded`, `figure_passthrough`, `ocr_page_error`, etc.

## 8. Auth & security

JWT HS256 (`core/security`): access 15m + refresh 30d, bcrypt hashing, password-reset + email-verify tokens. Login lockout (5 / 10m → 15m). Refresh uses CSRF cookie → `X-CSRF-Token`. Most routes require `current_user`; `GET /languages` + `GET /health` intentionally open.

## 9. Known issues / gaps (from module docs)

- `DELETE /glossaries/{id}/terms/{term_id}` has **no auth dependency** — every other glossary route enforces ownership. Likely a gap.
- CORS `allow_credentials=False` while refresh/CSRF rely on httpOnly cookies → works same-origin/proxied only, not true cross-origin cookie auth.
- Login cookies set `secure=False` (dev-only — must flip for prod/HTTPS).
- `GET /languages` and `GET /health` carry `TODO(phase-2): add JWT auth`.
