# Architecture + Codebase Tour

> Mục tiêu: sau khi đọc, bạn biết **nên mở file nào** khi nhận 1 task mới.

## 30-second mental model

```
User (browser)
    │  upload .docx/.pdf/.pptx
    ▼
Next.js (port 8080)   ──── nginx (prod) ──── FastAPI (port 8000)
                                                    │
                                                    │ enqueue
                                                    ▼
                                            Redis (arq queue)
                                                    │
                                                    ▼
                            arq Worker  ─── DashScope qwen-mt-turbo
                                    │
                                    ▼
                            PostgreSQL  +  .data/jobs/{id}/
                                    │
                                    ▼
                            SSE progress  →  back to browser
```

Full diagram + sequence flow: **[../../.planning/codebase/ARCHITECTURE.md](../../.planning/codebase/ARCHITECTURE.md)**
(Mermaid diagrams; xem qua GitHub web UI hoặc IDE Mermaid plugin.)

## Domain WHY — đọc trước khi code

> Translated documents *usable as-is, without forcing reviewers to re-create layouts*.

3 hệ quả thực tế:

1. **Format fidelity > UX polish.** Đừng đề xuất UI feature nếu nó trade layout quality. Xem [constitution Principle I](../../.specify/memory/constitution.md).
2. **Hero formats**: DOCX (near pixel-perfect), native PDF (high fidelity), PPTX (text-box auto-fit). Scanned PDF chỉ cần *readable*, không cần perfect.
3. **Eval trước prompt.** Translation code = non-deterministic → không đổi prompt thiếu eval delta. Xem [constitution Principle II](../../.specify/memory/constitution.md).

## Repo layout

```
ai-translation/
├── backend/                  # Python / FastAPI / arq
├── frontend/                 # Next.js 16 / React 19 / TanStack Query
├── docs/                     # ← bạn đang đọc đây
│   ├── PROJECT.md            # what + why + constraints
│   ├── REQUIREMENTS.md       # REQ IDs (INFRA-01, UPLD-01...)
│   ├── ROADMAP.md            # phase plan
│   ├── STATE.md              # current state
│   ├── decisions/            # 10 ADRs
│   └── onboarding/           # setup, this file, workflow, deploy
├── deploy/                   # nginx config, prod artifacts
├── scripts/                  # healthcheck + utility scripts
├── .specify/                 # Spec-Kit infra (memory/constitution.md)
├── .planning/                # FROZEN — historical GSD artifacts
├── docker-compose.yml        # dev stack
├── docker-compose.prod.yml   # prod stack (host-only ports)
├── CLAUDE.md                 # tech stack details + do/don't
└── Makefile                  # test, lint, format, eval shortcuts
```

## Backend (`backend/src/app/`)

```
app/
├── main.py                   # FastAPI entry + lifespan (engine, redis, arq pool)
├── core/
│   ├── config.py             # Pydantic Settings (env-driven)
│   └── logging.py            # structlog setup
├── api/
│   ├── middleware/cors.py    # env-driven CORS
│   ├── dependencies.py       # get_session, get_arq_pool injection
│   └── routes/
│       ├── health.py         # GET /health (liveness)
│       ├── upload.py         # POST /upload — file → DB row → arq enqueue
│       ├── languages.py      # GET /languages (Qwen-supported)
│       ├── jobs.py           # GET /jobs, GET /jobs/{id}, /download, /artifacts
│       ├── segments.py       # GET/PATCH /jobs/{id}/segments[...]
│       ├── glossaries.py     # CRUD glossaries
│       ├── export.py         # POST /jobs/{id}/export (apply user edits → re-render)
│       └── sse.py            # GET /jobs/{id}/stream (Server-Sent Events)
├── db/
│   ├── models.py             # SQLAlchemy ORM: Job, Segment, SegmentFlag, Glossary
│   ├── session.py            # AsyncSession factory
│   └── (alembic/ ở backend root)
├── services/
│   ├── job_service.py        # Job CRUD helpers
│   ├── glossary_service.py   # Glossary CRUD + flag detection
│   └── ...
├── llm/
│   ├── client.py             # openai SDK against DashScope intl
│   ├── translator.py         # Sentinel-batched translate (ADR-0008)
│   └── prompts.py
├── pipeline/
│   ├── docx/{extractor,reassembler}.py     # run-level (ADR-0007)
│   ├── pptx/{extractor,reassembler}.py     # shape/table/SmartArt
│   ├── pdf/{extractor,reassembler,         # PyMuPDF (ADR-0003)
│   │       columns,fonts}.py
│   └── scanned_pdf/{extractor,composer,    # PaddleOCR (ADR-0004)
│                    detector,segment_to_md}.py
└── workers/
    └── translate_worker.py   # arq worker — extract → translate → reassemble
```

**Bắt đầu đọc từ đâu cho từng loại task?**

| Task | Bắt đầu từ |
|---|---|
| Thêm API endpoint mới | `api/routes/` — copy 1 route gần nhất, mount trong `main.py` |
| Thêm format mới (vd. xlsx) | `pipeline/<format>/{extractor,reassembler}.py` + branch trong `workers/translate_worker.py` |
| Sửa prompt / batching | `llm/translator.py` + chạy eval (xem [workflow.md](workflow.md)) |
| Thêm glossary feature | `services/glossary_service.py` + `api/routes/glossaries.py` |
| Sửa DB schema | `db/models.py` → `alembic revision --autogenerate -m "..."` → `alembic upgrade head` |
| Sửa lỗi job stuck | `workers/translate_worker.py` + check logs `docker compose logs worker` |

## Frontend (`frontend/src/`)

```
src/
├── app/                      # Next.js App Router
│   ├── layout.tsx            # root layout + fonts (Roboto/Montserrat/JetBrainsMono)
│   ├── page.tsx              # redirect → /upload
│   ├── upload/page.tsx       # upload form
│   ├── jobs/
│   │   ├── page.tsx          # jobs list
│   │   └── [id]/
│   │       ├── page.tsx      # job status + download
│   │       └── review/page.tsx  # segment review UI (CAT-tool table)
│   ├── glossaries/           # glossary CRUD pages
│   └── api/upload/route.ts   # Next.js route — proxies upload to backend (dev only)
├── components/
│   ├── ui/                   # shadcn primitives — bấm vào để hiểu pattern
│   ├── SegmentTable.tsx      # main review table (ADR-0009)
│   ├── SegmentRow.tsx        # one row = source + target Textarea + flags
│   ├── UploadForm.tsx
│   ├── JobsTable.tsx
│   ├── ReviewPageHeader.tsx
│   ├── glossary/             # glossary-specific components
│   └── ...
├── hooks/
│   ├── useSegments.ts        # TanStack Query: fetch + PATCH segment
│   ├── useJobProgress.ts     # SSE subscription
│   └── useCounterAnimation.ts
├── lib/
│   ├── api.ts                # API client (fetch wrappers)
│   ├── types.ts              # TS types matching backend Pydantic models
│   ├── review-types.ts
│   ├── formatBreadcrumb.ts
│   └── utils.ts              # cn() (tailwind merge), etc.
└── __tests__/                # Vitest unit tests
```

**Bắt đầu đọc từ đâu cho từng loại task?**

| Task | Bắt đầu từ |
|---|---|
| Sửa upload UI | `components/UploadForm.tsx` + `app/upload/page.tsx` |
| Sửa review UI | `components/SegmentTable.tsx` + `SegmentRow.tsx` + `hooks/useSegments.ts` |
| Sửa job status page | `app/jobs/[id]/page.tsx` + `hooks/useJobProgress.ts` |
| Thêm shadcn component | `npx shadcn@latest add <component>` → vào `components/ui/` |
| API URL routing | `lib/api.ts` (relative `/api/*` paths — nginx/Next rewrite handle) |

## Key abstractions

### `Job` (DB row)
1 file upload = 1 `Job`. Trạng thái lifecycle:
```
queued → extracting → translating → reassembling → done | needs_review | failed
```
Field quan trọng: `id` (uuid), `status`, `stage`, `source_lang`, `target_lang`, `input_path`, `output_path`, `segments_done/total`, `error_msg`.

### `Segment` (DB row, FK → Job)
1 translatable unit (paragraph, cell, text block). Field: `id`, `job_id`, `source_text`, `translated_text`, `position` (JSON với coords/section info), `is_edited` (true khi user PATCH), `flags` (relationship).

### `SegmentFlag` (DB row, FK → Segment)
Issue detected on a segment: `overflow`, `llm_refusal`, `placeholder_mismatch`, `low_confidence`, etc. Frontend hiển thị badge ⚠️ trên row.

### `Glossary` + `GlossaryTerm`
Per-language-pair term list. Áp dụng qua `terminology` API parameter của qwen-mt-turbo (ADR-0001) + post-translation flagging nếu translation không follow.

## Data flow (1 upload từ A→Z)

1. Browser POST `/api/upload` (multipart). Next.js dev: route handler proxy → FastAPI. Prod: nginx route `/api/` → FastAPI trực tiếp.
2. FastAPI `upload.py`:
   - Validate ext + size + lang.
   - Detect tracked-changes (DOCX) / scanned (PDF).
   - Create `Job` row trong PostgreSQL (status=`queued`).
   - Lưu file vào `.data/jobs/{job_id}/source.{ext}`.
   - `arq_pool.enqueue_job("translate_job", job.id)`.
   - Trả `{job_id, has_tracked_changes, is_scanned}` → HTTP 202.
3. Browser redirect tới `/jobs/{id}` → mở SSE connection `/api/jobs/{id}/stream`.
4. arq Worker:
   - `extractor.extract(input_path)` → list of `Segment` (insert DB).
   - `translator.translate_batch(segments)` → call DashScope (sentinel-batched).
   - `reassembler.reassemble(segments, output_path)` → write translated file.
   - Update `Job.status` mỗi bước → publish progress → SSE pushes.
5. Frontend SSE handler update TanStack Query cache → re-render progress bar.
6. Khi `status=done` → user click Download → FastAPI stream `output_path`.
7. Optional: user vào `/jobs/{id}/review` → edit segments → PATCH `/api/jobs/{id}/segments/{seg_id}` → click Export → re-reassemble with edited segments.

## Test layout

| Loại test | Ở đâu | Run với |
|---|---|---|
| Backend unit | `backend/tests/` (non-integration markers) | `make test-unit` |
| Backend integration (DB + Redis) | `backend/tests/` (`@pytest.mark.integration`) | `make test-integration` (cần docker compose up) |
| Backend eval (translation quality) | `backend/tests/eval/` | `make eval` |
| Frontend unit | `frontend/src/__tests__/` | `cd frontend && npm test` |
| Frontend e2e | `frontend/e2e/` (Playwright) | `cd frontend && npx playwright test` |

## Codegraph (nếu dùng Claude Code)

Project có `.codegraph/` (CodeGraph MCP server) — knowledge graph của symbols. Truy vấn:

- "Tìm function tên X" → `codegraph_search`
- "Cái gì gọi function Y?" → `codegraph_callers`
- "Đổi Z thì gì break?" → `codegraph_impact`

Nhanh hơn grep cho structural questions. Xem global `~/.claude/CLAUDE.md` để chi tiết.

## Tiếp theo

→ [workflow.md](workflow.md) để biết flow contribute (Spec-Kit + PR + commit rules).
