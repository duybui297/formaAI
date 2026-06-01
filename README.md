# AI Translation PoC

Web-based AI document translation PoC. Upload office documents (DOCX, PDF, PPTX) in any language pair and get back translated versions that preserve the original layout as closely as the format allows. Built as an internal demo for the **AICore** team to evaluate Qwen-class LLMs + layout-aware processing against commodity tools (Azure Translator, DeepL, Google Docs).

Ships with a full **License Management** subsystem (issue / activate / validate / suspend / revoke / extend licenses) gating the translation API.

---

## Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12 · FastAPI · SQLAlchemy 2.0 async · Alembic · arq (Redis queue) |
| Translation | `qwen-mt-turbo` on Alibaba DashScope via the OpenAI-compatible SDK |
| Docs | python-docx · python-pptx · PyMuPDF · PaddleOCR (scanned PDFs) |
| Frontend | Next.js (App Router) · TanStack Query · shadcn/ui |
| Data | PostgreSQL 16 · Redis 7 |
| Infra | Docker Compose |

---

## Quick start (Docker)

```bash
cp .env.example .env          # set DASHSCOPE_API_KEY, SECRET_KEY, LICENSE_SIGNING_SECRET (rest have defaults)
make up                       # build + run: api + worker + web + postgres + redis
docker compose exec api alembic upgrade head   # first run only — migrates + seeds admin
```

| Service | URL |
|---------|-----|
| Web | http://localhost:8080 |
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Postgres | localhost:**5433** (→ `postgres:5432` inside Docker) |
| Redis | localhost:6379 |

Stop: `make down` (keeps the `pgdata` volume).

> Compose does **not** auto-migrate (the api container only runs uvicorn). Run the `alembic upgrade head` step above on a fresh DB.
> Local-dev (no Docker) instructions: see **[RUN.md](./RUN.md)**.

---

## Demo accounts

| Role | Email | Password |
|------|-------|----------|
| Admin (`is_superuser`) | `admin123@gmail.com` | `Admin@123` |
| User | `user@demo.com` | `User@12345` |

## Demo flow

1. **`/register`** — create a non-admin user → auto-login.
2. **`/pricing`** — pick a plan → receive a **raw license key (shown once)** → link to `/activate`.
3. **`/activate`** — enter the key (auto-formats `XXXX-XXXX-XXXX-XXXX`) → license becomes `ACTIVE`.
4. **`/admin/licenses`** (admin) — list / filter / sort, create, detail drawer + activity timeline, bulk suspend/revoke, extend expiry.

Plan → tier mapping: Free → `starter` (TRIAL), Pro → `professional` (PRO), Business → `enterprise` (ENTERPRISE).

---

## Admin License API

Admin cookie auth required. The admin API speaks the **frontend vocabulary** (tier `starter`/`professional`/`enterprise`, lowercase status incl. `pending`) and takes/returns `customer_id` as an **email** — a thin mapping layer translates to the BE domain enums (`TRIAL`/`PRO`/`ENTERPRISE`, uppercase, UUID) at the boundary. Core domain (activation, checkout, cron, middleware) keeps the BE enums.

```
GET  /api/admin/licenses?tier=&status=&issued_after=&issued_before=&page=&page_size=&sort_by=&sort_dir=
                                   → { licenses[], total, page, page_size }
GET  /api/admin/licenses/{id}      → License
GET  /api/admin/licenses/{id}/activities          → LicenseActivity[]  (newest-first)
POST /api/admin/licenses           { tier, customer_id(email), max_devices?, expired_at? }
                                   → 201 { license, raw_key }   (raw_key once)
POST /api/admin/licenses/suspend   { ids: [...] }
POST /api/admin/licenses/revoke    { ids: [...] }
POST /api/admin/licenses/{id}/extend  { expired_at: "<ISO>" }  → License
```

- `customer_id` must be the email of an **existing** user (unknown → 400).
- `key_masked` = `****-****-****-XXXX` (a hash suffix — the real key is returned only once, at create/checkout).
- Client API: `POST /api/licenses/activate`, plus license-validation middleware on `/api/v1/**`.

---

## Tests & workflow

```bash
make healthcheck                              # DashScope + DB + Redis + fonts
make test                                     # backend suite
cd frontend && npx vitest run                 # FE unit
cd frontend && npx playwright test            # FE e2e (npx playwright install first)

python3 scripts/verify_task.py status         # task board
python3 scripts/verify_task.py verify TASK-x.y # run a task's behaviors → projects PROGRESS
```

Work is **verification-driven**: every behavior in `featurelist.json` has a runnable command that must exit 0 before its task is `DONE`. See **[RULES.md](./RULES.md)**.

---

## Docs map

| File | Purpose |
|------|---------|
| [RUN.md](./RUN.md) | Full run guide — Docker **and** local dev, env vars |
| [CLAUDE.md](./CLAUDE.md) | Project brief, tech-stack rationale, conventions |
| [FEATURELIST.md](./FEATURELIST.md) / `featurelist.json` | Behavior-level backlog (source of truth) |
| [PROGRESS.md](./PROGRESS.md) | Live task status (script-owned — don't hand-edit) |
| [RULES.md](./RULES.md) | Verification-driven task workflow |
| [SESSIONS.md](./SESSIONS.md) | Cross-session running memory |
| `backend/ARCHITECTURE.md` · `backend/BACKEND.md` | Backend structure + skill reference |

## Status

License Management: **12 / 13 tasks DONE**. `TASK-4.2` (load test P99<50ms @1000 users) is `BLOCKED` — needs a separate load-gen host + multi-node deploy; a single dev box hits ~250ms (a/b/c pass).
