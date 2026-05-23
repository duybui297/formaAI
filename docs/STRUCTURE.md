# AI Translation PoC — Structure & Run Guide

Tài liệu tổng quan repo cho thành viên mới. Mục tiêu: hiểu cây thư mục, biết chạy local, biết file nào để đâu.

> **Bối cảnh nhanh**: web app dịch tài liệu (DOCX / PDF / PPTX) giữ nguyên format, dùng `qwen-mt-turbo` qua DashScope. FastAPI backend + Next.js frontend + Postgres + Redis (arq) + worker. PoC nội bộ cho team AICore.

---

## 1. Top-level layout

```
ai-translation/
├── backend/              # FastAPI app, arq worker, pipeline xử lý tài liệu
├── frontend/             # Next.js 16 (App Router) — UI upload / jobs / review / glossary
├── scripts/              # Tiện ích cấp repo (healthcheck DashScope + DB + Redis + fonts)
├── docker-compose.yml    # 5 services: api, worker, web, postgres, redis
├── Makefile              # Shortcut: up / down / test-* / lint / typecheck / healthcheck
├── .env.example          # Mẫu env vars — copy → .env trước khi chạy
├── .planning/            # GSD workflow artifacts: ROADMAP, phases, specs, spikes, handoff
├── .remember/            # Session memory (auto, không edit tay)
├── .claude/              # Cấu hình Claude Code project-local
├── CLAUDE.md             # Project instructions cho AI assistant (stack, conventions)
└── docs/                 # Tài liệu cho người (file này nằm đây)
```

---

## 2. Backend (`backend/`)

Python 3.12 + FastAPI + SQLAlchemy 2.0 async + arq. Quản lý gói bằng `uv`.

```
backend/
├── Dockerfile
├── pyproject.toml        # Deps + tooling (ruff, mypy, pytest)
├── scripts/              # Script ad-hoc (vd: wave0_html_probe.py)
├── src/app/              # Mã nguồn chính
│   ├── main.py           # FastAPI entry, lifespan: engine → redis → arq_pool
│   ├── api/
│   │   ├── deps.py       # FastAPI deps: get_redis, get_arq_pool, get_settings
│   │   ├── middleware/cors.py
│   │   └── routes/       # upload, jobs, segments, sse, export, glossaries, languages, health
│   ├── core/             # config (pydantic-settings), logging (structlog)
│   ├── db/
│   │   ├── models.py     # ORM: Job, Segment, Glossary, SegmentFlag, ...
│   │   ├── session.py    # AsyncSession factory
│   │   └── migrations/   # Alembic (env.py + versions/0001..0007)
│   ├── schemas/          # HTTP request/response DTOs (Pydantic) — tách khỏi ORM + LLM
│   │   ├── segment.py    # SegmentPatchRequest, segment_to_dict, flag_to_dict
│   │   └── glossary.py   # Create/Rename/CreateTerm/UpdateTerm requests
│   ├── llm/              # DashScope client + sentinel-batched translator
│   │   ├── client.py     # openai SDK trỏ về dashscope-intl
│   │   ├── translator.py # batch + retry + glossary injection
│   │   ├── terminology.py
│   │   ├── token_budget.py
│   │   └── schemas.py    # LLM-internal contract: TranslateBatchRequest/Response, TokenUsage
│   ├── pipeline/         # Trích xuất + tái lắp theo từng format
│   │   ├── segment.py        # Unit chung
│   │   ├── placeholder.py    # Token sentinel
│   │   ├── docx/             # extractor / reassembler / tracked-changes
│   │   ├── pdf/              # extractor / reassembler / columns / fonts
│   │   ├── pptx/             # extractor / reassembler / smartart
│   │   └── scanned_pdf/      # detector / extractor (OCR) / segment_to_md / composer
│   ├── services/         # Logic ứng dụng (job, glossary, export)
│   └── workers/
│       └── translate_worker.py   # arq worker: pipeline → translate → reassemble → emit SSE
├── fonts/                # Noto bundle cho fpdf2 D-04-27 (gitignored; README docs download)
└── tests/                # marker-based: `pytest -m "not integration"` vs `-m integration`
    ├── api/  db/  llm/  pipeline/  services/  workers/  integration/
    └── fixtures/         # tài liệu mẫu (gồm fixtures/scanned)
```

**Mental model**: route nhận file → `services.job_service` tạo Job + enqueue arq → `workers.translate_worker` chạy `pipeline.<format>.extractor` → `llm.translator` dịch batch → `pipeline.<format>.reassembler` ráp lại → ghi `output.<ext>` + segments.json → SSE đẩy progress về UI.

---

## 3. Frontend (`frontend/`)

Next.js 16 (App Router, Turbopack) + React 19 + TanStack Query v5 + shadcn/ui + Tailwind.

```
frontend/
├── Dockerfile.frontend
├── package.json          # Scripts: dev / build / start / lint / type-check / test
├── next.config.mjs  tailwind.config.ts  postcss.config.mjs  components.json
├── public/
├── e2e/                  # Playwright specs
└── src/
    ├── app/                       # Route segments (App Router)
    │   ├── layout.tsx                  # Fonts (Roboto, Montserrat, JetBrains Mono) + providers
    │   ├── page.tsx                    # Landing
    │   ├── upload/page.tsx
    │   ├── jobs/page.tsx
    │   ├── jobs/[id]/page.tsx          # Job detail
    │   ├── jobs/[id]/review/page.tsx   # Review view (segment table)
    │   ├── glossaries/page.tsx
    │   ├── glossaries/[id]/page.tsx
    │   └── api/upload/route.ts         # Proxy → BACKEND_URL
    ├── features/                  # Domain-grouped components (+ co-located tests)
    │   ├── upload/                     # UploadForm, GlossarySelect, TrackedChangesModal
    │   ├── jobs/                       # JobsTable, JobMetaRow, StatusBadge, ProgressBar,
    │   │                               # StageIndicator, ErrorDetails
    │   ├── review/                     # SegmentTable, SegmentRow, ReviewPageHeader,
    │   │                               # ReviewFilterBar, KeyboardHelpPanel, FlagBadge
    │   └── glossary/                   # GlossaryList, TermsTable, CSVUploadButton,
    │                                   # GlossaryCreateDialog
    ├── components/                # Cross-feature SHARED only
    │   ├── ui/                         # shadcn primitives
    │   ├── providers/                  # query-provider (+ smoke.test.tsx)
    │   ├── NavBar.tsx
    │   └── LanguageSelect.tsx          # used by upload + glossary → kept shared
    ├── hooks/                     # Cross-feature hooks (+ co-located tests)
    │   ├── useJobProgress.ts           # SSE
    │   ├── useSegments.ts              # TanStack query/mutation
    │   ├── useReviewKeyboard.ts
    │   ├── useCounterAnimation.ts
    │   └── use-toast.ts
    └── lib/                       # Framework-agnostic utils (+ co-located tests)
        ├── api.ts                      # fetch wrapper
        ├── types.ts                    # canonical types (Segment, FlagType, JobProgress, ...)
        ├── formatBreadcrumb.ts
        ├── detectTrackedChanges.ts
        └── utils.ts
```

**Test convention:** Vitest `*.test.{ts,tsx}` co-located cạnh code (no `__tests__/` dir). Auto-discovered.

**Review UI convention (D-02-14)**: shadcn Table + Textarea per row, virtualized bằng `react-virtuoso`, optimistic mutation pattern `onMutate → cancelQueries → setQueryData → onError rollback`. Monaco DiffEditor còn trong deps nhưng không dùng cho review.

---

## 4. Scripts (`scripts/`)

| File | Mục đích |
|------|----------|
| `healthcheck.py` | Validate DashScope key + Postgres + Redis + Noto fonts. `--skip-db` để test mỗi DashScope khi docker chưa lên. |

---

## 5. Planning (`.planning/`)

Artifacts của GSD workflow — không phải code, không deploy.

```
.planning/
├── ROADMAP.md        # 5 phases: Foundation → Review/Glossary → PPTX/PDF → OCR → Demo hardening
├── PROJECT.md        # Mục tiêu + bối cảnh
├── REQUIREMENTS.md   # Yêu cầu cấp PoC
├── HANDOFF.md        # Trạng thái bàn giao giữa sessions
├── STATE.md          # Snapshot context hiện tại
├── config.json
├── codebase/         # Notes về code đã có
├── phases/           # Một thư mục per phase: SPEC.md, plan, execute logs
├── research/         # Notes lib / model
└── spikes/           # Feasibility experiments (throwaway)
```

Đọc trước khi sửa scope: `ROADMAP.md` → `phases/<phase>/SPEC.md`.

---

## 6. Cách chạy local

### 6.1 Prerequisites

- Docker + Docker Compose v2
- (tùy chọn) `uv` + Node 20 + `make` nếu muốn chạy ngoài docker
- DashScope **international** API key (lấy ở `dashscope-intl.aliyuncs.com` — key China-region trả 401 không message)

### 6.2 Setup env

```bash
cp .env.example .env
# Mở .env, dán DASHSCOPE_API_KEY=sk-...
# Mặc định Postgres/Redis URL đã khớp docker-compose
```

### 6.3 Start full stack (khuyến nghị)

```bash
make up        # docker compose up -d --build
make healthcheck   # validate DashScope + DB + Redis + fonts
```

Services khi `up`:

| Service  | Port (host) | Note |
|----------|-------------|------|
| web      | 8080        | Next.js dev (turbopack) — http://localhost:8080 |
| api      | 8000        | FastAPI uvicorn `--reload` — http://localhost:8000 |
| worker   | —           | arq consumer (cùng image với api) |
| postgres | 5432        | DB `aitranslation`, user/pass `postgres` |
| redis    | 6379        | arq broker + SSE pub/sub |

Volume bind: `./backend/src` và `./frontend/src` hot-reload. `.data/` mount vào `/data` (file per-job).

### 6.4 Stop

```bash
make down
```

### 6.5 Migration (Alembic)

```bash
docker compose exec api alembic upgrade head
# Tạo migration mới:
docker compose exec api alembic revision -m "describe change" --autogenerate
```

### 6.6 Tests

```bash
make test-unit         # backend pytest, không cần services
make test-integration  # cần docker services up (marker `integration`)
make test              # full suite
make eval              # eval suite (translation quality)
```

Frontend:

```bash
cd frontend
npm run test           # vitest run
npm run test:watch
npx playwright test    # e2e (cần stack up)
```

### 6.7 Lint / typecheck / format

```bash
make lint        # ruff
make typecheck   # mypy
make format      # ruff format
cd frontend && npm run lint && npm run type-check
```

---

## 7. Env vars quan trọng

| Var | Default | Ghi chú |
|-----|---------|---------|
| `DASHSCOPE_API_KEY` | — | **Phải là intl key** |
| `DASHSCOPE_BASE_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Đừng đổi |
| `TRANSLATION_MODEL` | `qwen-mt-turbo` | Switch sang `qwen3.5-plus` → mất native glossary |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@postgres:5432/aitranslation` | |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `DATA_DIR` | `/data` (docker) / `.data` (host) | Per-job: `jobs/{id}/source.*`, `output.*`, `segments.json`, `errors.log` |
| `MAX_UPLOAD_BYTES` | 50 MB | |
| `BATCH_TOKEN_BUDGET` | 3000 | Tune cho qwen-mt-turbo |
| `WORKER_CONCURRENCY` | 1 | Free tier DashScope ~60 RPM; bump 4 nếu paid |
| `DASHSCOPE_CALL_SLEEP_S` | 1.2 | ~50 RPM safe; 0 nếu paid 300+ RPM |
| `SENTINEL_BATCH_SIZE` | 10 | 5 = conservative (~4% mismatch), 25 = aggressive (~24%) |

Full list + comment chi tiết: xem `.env.example`.

---

## 8. Per-job file layout

```
.data/jobs/{job_id}/
├── source.{docx|pdf|pptx}
├── output.{docx|pdf|pptx}
├── segments.json          # canonical state cho review UI
└── errors.log
```

`.data/` đã gitignore. Container đọc/ghi qua `/data` bind-mount.

---

## 9. Flow request → output (DOCX ví dụ)

1. UI `POST /api/upload` (Next route proxy) → backend `routes/upload.py`
2. `services.job_service` lưu file vào `.data/jobs/{id}/source.docx`, tạo `Job` row, `enqueue('translate', job_id)`
3. `workers.translate_worker` nhận job:
   - `pipeline.docx.extractor` → list `Segment`
   - `llm.translator` → batch theo `SENTINEL_BATCH_SIZE`, gọi DashScope, retry mismatch
   - `pipeline.docx.reassembler` → ghi `output.docx` giữ run-level formatting
   - publish progress qua Redis pub/sub
4. UI mở SSE `/jobs/{id}/stream` (hook `useJobProgress`) → render `features/jobs/ProgressBar` + `StageIndicator`
5. Done → user vào `/jobs/{id}/review` (`features/review/SegmentTable`), sửa inline (PATCH → optimistic update via `hooks/useSegments`), bấm export → `routes/export.py` trả file đã sửa.

---

## 10. Khi cần biết thêm

- Stack rationale + alternatives: `CLAUDE.md`
- Phase scope: `.planning/ROADMAP.md` + `.planning/phases/<n>/SPEC.md`
- Decisions trong code (D-xx, W-xx): grep trong source — vd `grep -r "D-02-14" backend/ frontend/`
- API contract: chạy stack, mở `http://localhost:8000/docs` (FastAPI swagger)
