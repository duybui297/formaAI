# Backend — AI Translation PoC

FastAPI service: upload office docs → translate via Qwen (DashScope) → review/edit segments → export format-preserving output. Async job queue (arq), layout-aware pipelines per format.

## Tech Stack

| Layer | Tech | Version | Notes |
|-------|------|---------|-------|
| Runtime | Python | 3.12 | |
| Pkg mgr | uv | — | `uv pip install --system -e ".[test]"` |
| API | FastAPI | 0.115 | flat routers, no prefix |
| ASGI | uvicorn[standard] | 0.30 | |
| Config | pydantic-settings | 2 | `.env`, `SecretStr` for keys |
| Logging | structlog | 24 | configured first in lifespan |
| LLM | openai SDK | 1.40 | `AsyncOpenAI` → DashScope intl compat endpoint |
| Model | qwen-mt-turbo | — | `dashscope-intl.aliyuncs.com/compatible-mode/v1` |
| Tokens | tiktoken | 0.7 | batch token budgeting |
| DOCX | python-docx | 1.2.0 | run-level replace |
| PDF | PyMuPDF | 1.26 | extract + reinsert |
| PPTX | python-pptx | 1.0.2 | + smartart handling |
| OCR | paddleocr (PP-StructureV3, PP-OCRv5) | 3.5 | scanned PDF; models baked at build |
| PDF gen | fpdf2 | 2.7 | OCR output compose, Noto fonts |
| DB | PostgreSQL + SQLAlchemy[asyncio] 2.0 + asyncpg | — | `postgresql+asyncpg://` |
| Migrations | Alembic | 1.13 | |
| Queue | arq | 0.27.0 | asyncio-native, Redis broker |
| Cache/broker | redis[hiredis] | 5 | |
| SSE | sse-starlette | 1.6 | job progress stream |
| Auth | bcrypt + python-jose[cryptography] + email-validator | — | JWT HS256, access 15m / refresh 30d |
| Email | aiosmtplib | 3 | password reset |
| Lint | ruff | — | line 88, py312, `E,F,I,UP,B,SIM` |
| Test | pytest + pytest-asyncio + httpx + aiosqlite | — | cov ≥80%, `asyncio_mode=auto` |

## Structure

```
src/app/
  main.py                 # FastAPI entry; lifespan builds engine/redis/arq pool/llm client
  core/    config.py (Settings) logging.py security.py (JWT/bcrypt)
  api/
    deps.py               # DI: db session, arq pool, current_user
    middleware/cors.py
    routes/  auth jobs upload segments sse export glossaries languages health
  db/
    models.py             # Job, Segment, Glossary, GlossaryTerm, SegmentFlag, User, PasswordResetToken
    session.py
    migrations/versions/   # alembic 0002..0010 + init
  llm/     client.py translator.py (translate_batch) terminology.py token_budget.py schemas.py
  pipeline/
    segment.py placeholder.py
    docx/    extractor reassembler tracked
    pdf/     extractor reassembler fonts columns
    pptx/    extractor reassembler smartart
    scanned_pdf/  detector extractor composer segment_to_md   # OCR path
  schemas/  auth glossary segment       # pydantic I/O
  services/ job_service glossary_service export_service
  workers/  translate_worker.py (arq WorkerSettings)
tests/  api db llm pipeline services workers integration fixtures
fonts/  Noto bundle (fpdf2 explicit-path registration)
Dockerfile  alembic.ini  pyproject.toml  uv.lock
```

## Architecture

Full architecture (layers, per-module breakdown, composition root, job lifecycle, data model) → [`ARCHITECTURE.md`](./ARCHITECTURE.md).

Per-module docs:
- [api](./src/app/api/ARCHITECTURE.md) — FastAPI routers, DI, CORS, auth deps
- [schemas](./src/app/schemas/ARCHITECTURE.md) — pydantic request/response models
- [services](./src/app/services/ARCHITECTURE.md) — job FSM, glossary CRUD, export
- [workers](./src/app/workers/ARCHITECTURE.md) — arq translation worker
- [llm](./src/app/llm/ARCHITECTURE.md) — DashScope translate, terminology, token budget
- [pipeline](./src/app/pipeline/ARCHITECTURE.md) — per-format extract/reassemble + OCR
- [db](./src/app/db/ARCHITECTURE.md) — ORM models, session, migrations
- [core](./src/app/core/ARCHITECTURE.md) — config, logging, security

## API Endpoints (flat, no prefix)

```
Health      GET  /health
Languages   GET  /languages
Upload      POST /upload                              (202; creates job, enqueues)
Jobs        GET  /jobs   /jobs/{id}   /jobs/{id}/artifacts
            GET  /jobs/{id}/pages/{n}.png   /jobs/{id}/download
Segments    GET  /jobs/{id}/segments
            PATCH /jobs/{id}/segments/{sid}           (edit translation)
            POST  /jobs/{id}/segments/{sid}/regenerate (sync LLM re-translate)
SSE         GET  /jobs/{id}/stream                    (progress events)
Export      POST /jobs/{id}/export
Glossary    GET/POST /glossaries  +  /{id} GET/PATCH/DELETE
            /{id}/terms GET/POST  /terms/import  /terms/{tid} PATCH/DELETE
Auth        POST /register /login /refresh /logout
            GET  /me   POST /forgot-password /reset-password
```

## Config (env / `.env`)

Required: `DASHSCOPE_API_KEY` (intl key), `DATABASE_URL` (postgresql+asyncpg DSN), `SECRET_KEY` (JWT — `python -c "import secrets; print(secrets.token_urlsafe(64))"`).
Defaults: `DASHSCOPE_BASE_URL`, `DASHSCOPE_MODEL=qwen-mt-turbo`, `REDIS_URL=redis://redis:6379/0`, `DATA_DIR=/data`, `TOKEN_BUDGET=3000` (500–7000), `WORKER_CONCURRENCY=4`, `OCR_PAGE_DPI=300`, `OCR_TEXT_DENSITY_THRESHOLD=50.0`, `EXPANSION_RATIO_THRESHOLDS` (JSON per lang-pair), SMTP_* (default Gmail). Validated at startup (fail-fast).

## Run

Prereqs: Python 3.12, Postgres, Redis. Or use Docker (handles fonts + PaddleOCR models).

```bash
# install (uv)
uv pip install --system -e ".[test]"     # or: uv sync

# migrate
alembic upgrade head

# API (set PYTHONPATH=src)
PYTHONPATH=src uvicorn app.main:app --reload --port 8000

# arq worker (separate process)
PYTHONPATH=src arq app.workers.translate_worker.WorkerSettings

# tests / lint
pytest                  # cov ≥80%
ruff check src
```

**Docker** — `Dockerfile` (python:3.12-slim): installs Noto CJK/VN fonts, uv deps, paddlepaddle 3.0.0 from Alibaba index, bakes PP-StructureV3 models (~700MB–1GB, avoids cold-start), copies `fonts/` + `alembic.ini` + `src/`. `PYTHONPATH=/backend/src`, exposes 8000. Orchestrated via root `docker-compose.yml` (api + worker + postgres + redis):

```bash
# repo root
docker compose up
```
