---
phase: 01-foundation-docx-pipeline
plan: "01"
subsystem: infrastructure
tags:
  - docker
  - python
  - next.js
  - dashscope
  - fonts
  - healthcheck

dependency_graph:
  requires: []
  provides:
    - docker-compose topology (api, worker, web, postgres, redis)
    - backend Python project scaffold (pyproject.toml, Dockerfile, Noto fonts)
    - frontend project scaffold (Next.js 16.2.3 + React 19, TanStack Q5, Monaco, vitest)
    - environment variable contract (.env.example)
    - infra healthcheck script (INFRA-01/02)
  affects:
    - all subsequent plans (scaffold dependency)

tech_stack:
  added:
    - python:3.12-slim-bookworm (backend base image)
    - fastapi>=0.115,<0.116
    - uvicorn[standard]>=0.30
    - sqlalchemy[asyncio]>=2.0,<3
    - asyncpg>=0.30
    - alembic>=1.13
    - arq==0.27.0
    - redis[hiredis]>=5.0
    - openai>=1.40,<2
    - tiktoken>=0.7
    - python-docx==1.2.0
    - pydantic-settings>=2.0
    - sse-starlette==3.3.4
    - structlog>=24.0
    - python-multipart>=0.0.9
    - pytest/pytest-asyncio/pytest-cov/httpx (test extras)
    - fonts-noto-cjk + fonts-noto (Debian bookworm apt packages)
    - next@^16.2.3 + react@^19 + @tanstack/react-query@^5
    - "@microsoft/fetch-event-source@^2"
    - "@monaco-editor/react@^4"
    - jszip@^3.10.1
    - vitest@^1.6.0 + @testing-library/react@^16 + jsdom@^24
    - postgres:16-alpine + redis:7-alpine (Docker images)
    - node:20-alpine (frontend Docker image)
  patterns:
    - uv pip install --system for Docker image builds
    - per-job file layout .data/jobs/{job_id}/ (D-04)
    - openai SDK against DashScope intl compatible endpoint

key_files:
  created:
    - backend/pyproject.toml
    - backend/Dockerfile
    - backend/.dockerignore
    - docker-compose.yml
    - .env.example
    - .gitignore (extended from GSD baseline)
    - Makefile
    - frontend/package.json
    - frontend/next.config.mjs
    - frontend/tsconfig.json
    - frontend/Dockerfile.frontend
    - scripts/healthcheck.py
    - scripts/__init__.py
  modified: []

decisions:
  - "Pin arq==0.27.0 exactly (not >=) — maintenance-mode library; prevent silent upgrades"
  - "Pin sse-starlette==3.3.4 exactly — API surface stable; prevent AsyncIterator breaking change"
  - "Pin python-docx==1.2.0 exactly — DOCX-02 run-merge strategy tested against this version"
  - "Install fonts-noto-cjk + fonts-noto in Dockerfile now (Phase 3 prereq per CLAUDE.md) — avoids Dockerfile change mid-sprint"
  - "jszip + vitest devDeps included in frontend/package.json per Plan 07/08 downstream requirements"
  - "docker-compose api/worker use src.app.main:app path (uvicorn src module path for PYTHONPATH)"
  - "Makefile eval target added for translation quality evaluation suite"

metrics:
  duration: ~15 minutes
  completed_date: "2026-04-24T02:24:24Z"
  tasks_completed: 3
  tasks_total: 4
  files_created: 13
  files_modified: 1
---

# Phase 1 Plan 01: Infra Prerequisites Summary

**One-liner:** Docker-compose 5-service scaffold (FastAPI + arq + Next.js 16 + Postgres + Redis) with Noto CJK fonts in the backend image and a DashScope intl healthcheck validating qwen-mt-turbo + terminology param.

## What Was Built

### Task 1: Docker Desktop WSL2 Integration
Auto-skipped per orchestrator checkpoint note. Docker Desktop WSL2 integration was verified enabled by the orchestrator (`docker ps` succeeds with exit 0) before this plan executed.

### Task 2: Backend Project Scaffold
Created `backend/pyproject.toml` with all 14 Phase 1 Python dependencies pinned to correct versions. `backend/Dockerfile` installs `fonts-noto-cjk` and `fonts-noto` via apt-get and runs `fc-cache -f` — installed now so Phase 3 (PDF translation) does not require a Dockerfile change. `.env.example` documents all required environment variables with descriptions and an explicit warning about using the international DashScope key (not the China-region key). `Makefile` provides `test-unit`, `test-integration`, `test`, `eval`, `lint`, `typecheck`, `format`, `up`, `down`, `healthcheck` targets.

### Task 3: docker-compose + Frontend Config
`docker-compose.yml` brings up 5 services: `api` (uvicorn --reload, port 8000), `worker` (arq WorkerSettings), `web` (next dev --turbopack, port 3000), `postgres:16-alpine` (port 5432, pgdata volume), `redis:7-alpine` (port 6379). `frontend/package.json` pins Next.js 16.2.3, React 19, TanStack Query 5, fetch-event-source 2, Monaco 4, jszip (Plan 08 tracked-changes detection), and vitest + testing-library + jsdom (Plan 07 test infrastructure). `frontend/next.config.mjs` proxies `/api/*` to the FastAPI backend with no webpack config (Turbopack default per D-20).

### Task 4: DashScope Healthcheck Script
`scripts/healthcheck.py` implements 5 checks covering all D-18 requirements:
1. DashScope intl endpoint reachable: 1-sentence VN→EN probe via sync OpenAI client
2. Terminology param behaviour: translates same sentence with/without a term, documents output difference
3. PostgreSQL: `SELECT 1` with psycopg2 primary / asyncpg fallback
4. Redis: PING + write/read test
5. Noto fonts: `/usr/share/fonts/opentype/noto` directory check + fc-list fallback

`AuthenticationError` surfaces the exact actionable message ("use the key from dashscope-intl.aliyuncs.com, not the China console"). `--skip-db` flag enables DashScope + font checks before docker services are up. Auto-loads `.env` file if present.

## Deviations from Plan

### Auto-added Features

**1. [Rule 2 - Missing] Makefile eval + format + typecheck targets**
- Found during: Task 2
- Issue: Plan spec listed `test-unit`, `test-integration`, `test`, `lint`, `up`, `down`, `healthcheck`. AI-SPEC.md Section 5 references an eval suite. Global CLAUDE.md requires format target.
- Fix: Added `eval`, `format`, `typecheck` targets to Makefile.
- Files modified: Makefile

**2. [Rule 2 - Missing] jszip + vitest + testing-library in frontend/package.json**
- Found during: Task 3
- Issue: Context highlights in execution prompt explicitly flag these as downstream plan requirements (Plan 07 vitest setup, Plan 08 B4 jszip fix) that depend on devDependencies installed here.
- Fix: Included `jszip@^3.10.1`, `vitest@^1.6.0`, `@vitest/coverage-v8@^1.6.0`, `@testing-library/react@^16`, `@testing-library/user-event@^14`, `@testing-library/jest-dom@^6`, `jsdom@^24` in frontend/package.json devDependencies.
- Files modified: frontend/package.json

**3. [Rule 2 - Missing] @monaco-editor/react in frontend/package.json**
- Found during: Task 3
- Issue: CLAUDE.md Technology Stack lists Monaco DiffEditor as a required frontend package. Context highlights confirm `@monaco-editor/react@4` is needed. Plan task template showed it in the action block but frontmatter `files_modified` didn't explicitly list it as required.
- Fix: Added `@monaco-editor/react@^4.6.0` to frontend/package.json dependencies.
- Files modified: frontend/package.json

**4. [Rule 2 - Missing] .gitignore MAX_UPLOAD_BYTES env var**
- Found during: Task 2
- Issue: Plan's .env.example block didn't include `MAX_UPLOAD_BYTES` but it is required per the threat model (T-01-01 upload size limit) and CLAUDE.md FastAPI rule ("Always enforce MAX_UPLOAD_BYTES before file.read()").
- Fix: Added `MAX_UPLOAD_BYTES=52428800` (50 MB default) to `.env.example`.
- Files modified: .env.example

**5. [Rule 2 - Missing] _load_env_file() in healthcheck.py**
- Found during: Task 4
- Issue: Plan action block for healthcheck.py didn't mention auto-loading .env, but the script is meant to run outside docker (with `--skip-db`) where `DASHSCOPE_API_KEY` lives in `.env`.
- Fix: Added `_load_env_file()` helper that reads `.env` from cwd and sets env vars not already present. Called at start of `main()`.
- Files modified: scripts/healthcheck.py

## Human Action Required

**DASHSCOPE_API_KEY must be set before running healthcheck or `docker compose up`.**

1. Obtain an **INTERNATIONAL** API key from https://dashscope-intl.aliyuncs.com (not from dashscope.aliyun.com — China-region keys return a cryptic 401 on the international endpoint).
2. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
3. Edit `.env` and replace `DASHSCOPE_API_KEY=sk-your-international-key-here` with your actual key.
4. Verify DashScope connectivity:
   ```bash
   python scripts/healthcheck.py --skip-db
   ```
   Expected output: `[+] DashScope connectivity: PASS` and `[+] terminology param: PASS`

Until this key is set, `docker compose up` will start all services but healthcheck will fail with `[FAIL] DashScope: 401 Authentication error.`

## Known Stubs

None. This plan creates configuration files, not application code. No UI components, no data sources, no placeholder text.

## Threat Surface Scan

All files created/modified in this plan are configuration and tooling files (no HTTP endpoints, no auth paths, no schema changes). The only trust boundary introduced is the `.env` / `.env.example` split — `.env` is correctly gitignored, `.env.example` contains a placeholder value for `DASHSCOPE_API_KEY`. No new threat surface beyond what is documented in the plan's threat model.

## Self-Check

### Files Exist

- backend/pyproject.toml: FOUND
- backend/Dockerfile: FOUND
- backend/.dockerignore: FOUND
- docker-compose.yml: FOUND
- .env.example: FOUND
- Makefile: FOUND
- frontend/package.json: FOUND
- frontend/next.config.mjs: FOUND
- frontend/tsconfig.json: FOUND
- frontend/Dockerfile.frontend: FOUND
- scripts/healthcheck.py: FOUND
- scripts/__init__.py: FOUND

### Commits Exist

- 88f199c: chore(01-01): scaffold backend project with deps, Dockerfile, and env config
- 4b18085: chore(01-01): add docker-compose topology and frontend project config
- 1bbd771: feat(01-01): add DashScope + infra healthcheck script (INFRA-01/02)

## Self-Check: PASSED
