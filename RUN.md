# Run — AI Translation PoC (BE + FE)

Two ways: **A) Docker Compose** (all-in-one) or **B) Local dev** (what this machine is set up for).

Services: FastAPI API (8000) · arq worker · Next.js web (3000) · PostgreSQL (5432) · Redis (6379).

---

## A) Docker Compose (recommended, one command)

Needs Docker daemon running.

```bash
# from repo root
cp .env.example .env            # then edit: set DASHSCOPE_API_KEY + SECRET_KEY (others have defaults)
make up                         # = docker compose up --build
```

Endpoints:
- API → http://localhost:8000  (docs: http://localhost:8000/docs)
- Web → http://localhost:8080   (compose maps host 8080 → container 3000)

Migrations run inside the api container; if needed manually:
```bash
docker compose exec api alembic upgrade head
```

Stop: `make down`

---

## B) Local dev (no Docker)

Prereqs on this machine: `uv`, Node 20 + npm, local **PostgreSQL** (:5432) and **Redis** (:6379).
`backend/.env` already exists (dev values, DB=`aitranslation`).

### 0. Start datastores
```bash
redis-server --daemonize yes --port 6379          # brew redis
# Postgres: ensure a server runs on :5432 with db `aitranslation`
#   createdb aitranslation         # if missing (user/pass postgres per backend/.env)
```

### 1. Backend — API (terminal 1)
```bash
cd backend
uv pip install --system -e ".[test]"   # first time only (or: uv sync). .venv already present here.
uv run alembic upgrade head            # apply migrations
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
API at http://localhost:8000  · docs /docs · health /health

### 2. Backend — arq worker (terminal 2, for translation jobs)
```bash
cd backend
uv run arq app.workers.translate_worker.WorkerSettings
```
(Worker also runs the license expiry cron @ 2 AM.)

### 3. Frontend (terminal 3)
```bash
cd frontend
npm install                                        # first time only (node_modules already present)
BACKEND_URL=http://localhost:8000 npm run dev      # Next.js dev (Turbopack) on :3000
```
Web at http://localhost:3000. `next.config.mjs` proxies `/api/*` → `BACKEND_URL`.

Default login (seeded): `admin123@gmail.com` / `Admin@123` (see `.env.example` ADMIN_*).

---

## Env vars (key ones)
- `DASHSCOPE_API_KEY` — Qwen translation key (required for real translation; dummy ok for license-only work)
- `SECRET_KEY` — JWT secret (required)
- `DATABASE_URL` — `postgresql+asyncpg://postgres:postgres@localhost:5432/aitranslation` (local) / `@postgres:5432` (docker)
- `REDIS_URL` — `redis://localhost:6379/0` (local) / `redis://redis:6379/0` (docker)
- `BACKEND_URL` (frontend) — proxy target, default `http://api:8000` (docker); use `http://localhost:8000` for local dev

---

## License Management feature (this build)
- Admin dashboard: `/admin/licenses` (create/suspend/revoke/extend licenses)
- Client activation: `/activate` (enter key XXXX-XXXX-XXXX-XXXX)
- API: `POST /api/admin/licenses` (admin), `POST /api/licenses/activate`, validation middleware on `/api/v1/**`

## Tests / checks
```bash
cd backend && uv run pytest                 # backend suite
cd frontend && npx vitest run               # FE unit
cd frontend && npx playwright test          # FE e2e (needs browsers: npx playwright install)
make lint && make typecheck                 # if defined in Makefile
```

## Feature backlog / progress
- Task backlog + verification: `FEATURELIST.md`, `featurelist.json`
- Live status (script-owned): `PROGRESS.md` — `python3 scripts/verify_task.py status`
- Rules: `RULES.md`
