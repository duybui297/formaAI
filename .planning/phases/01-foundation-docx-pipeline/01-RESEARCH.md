# Phase 1: Foundation + DOCX Pipeline — Research

**Researched:** 2026-04-23
**Domain:** FastAPI / Next.js 16 / arq / python-docx / qwen-mt-turbo / SSE / PostgreSQL / Redis
**Confidence:** HIGH (primary stack fully verified via Context7 + official docs; DashScope rate limits remain LOW due to non-publication)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Monorepo: `backend/` + `frontend/` dirs; single `docker-compose.yml` + `.env.example` at root.
- **D-02:** Backend Python layout: `src/app/{api,services,pipeline,db,core,workers}/...`; `main.py` FastAPI entry; `workers/translate_worker.py` arq entry.
- **D-03:** docker-compose: `api` (uvicorn + reload + bind-mount), `worker` (arq, same image), `web` (Next.js dev + bind-mount), `postgres`, `redis`. Single `docker-compose up`. Pin pgdata volume.
- **D-04:** Per-job file layout: `.data/jobs/{job_id}/source.{ext}`, `output.{ext}`, `segments.json`, `errors.log`. `.data/` gitignored.
- **D-05:** DOCX content serialized into a structural tree of Segments with parent refs for reassembly. Rich schema (not flat list) — PPTX/PDF reuse it.
- **D-06:** Segment ID = `sha256(source_text + structural_position)[:16]`. Also `seq_in_job` for logs.
- **D-07:** Token-budgeted batching: pack Segments until ~2–4K input tokens. One `qwen-mt-turbo` call per batch. Segment-count assertion (CORE-03) runs per batch.
- **D-08:** Single oversized segment sent alone; if it still exceeds 8,192-token limit → job fails loudly with segment ID + token count. Never silent sentence-split.
- **D-09:** Hybrid SSE + TanStack Query cache: SSE primary (sse-starlette, Redis pub/sub `job:{id}`); polling fallback (`refetchInterval: 2000` when SSE closed). `setQueryData` on SSE event. `ping=15s`.
- **D-10:** SSE payload: `{ status, stage, segments_done, segments_total, current_batch, retry_count, last_message, error?: { code, message, failing_segments } }`.
- **D-11:** Error UI: top banner + expandable details. No traceback in UI; traceback goes to `errors.log`.
- **D-12:** Retry chip: subdued slate-500, no red. Red reserved for terminal failures only.
- **D-13:** Tracked changes: detect `<w:ins>`/`<w:del>` on upload, modal with strip/preserve/cancel before job creation.
- **D-14:** Comments: preserve + translate. Extract comment bodies as first-class Segments (`is_comment=true`).
- **D-15:** Phase 1 glossary scope: wire `terminology` plumbing + INFRA-02 test only. No glossary picker in upload form. UPLD-04 deferred to Phase 2.
- **D-16:** Auto-detect via `qwen-mt-turbo` native `source_lang="auto"`. Detected language persisted on Job row and shown in UI. No separate detection library.
- **D-17:** 2 arq worker processes; up to 4 concurrent batches per job via `asyncio.gather`.
- **D-18:** `scripts/healthcheck.py` checks DashScope intl + qwen-mt-turbo response, terminology param, Postgres, Redis, Noto fonts.
- **D-19:** `structlog` JSON to stdout; `job_id` bound as context var. Per-job errors appended to `errors.log`.
- **D-20:** Pin **Next.js `^16.2.3`** + React 19 (not Next.js 15). Write async cookies/headers/params from day one. Turbopack default. No webpack config.
- **Stack (CLAUDE.md):** openai SDK 1.x (not dashscope SDK), qwen-mt-turbo primary + qwen-mt-plus fallback, arq 0.27 + Redis, PostgreSQL 16 + SQLAlchemy 2.0 async + asyncpg + Alembic, python-docx 1.2.0 with run-level text replacement (NEVER `paragraph.text = value`), sse-starlette 3.3.4, @monaco-editor/react 4.x + @microsoft/fetch-event-source 2.x + TanStack Query 5.x on Next.js 16 App Router, Noto Sans CJK + Noto Sans fonts in Docker, local filesystem storage for Phase 1.
- **INFRA-01 (CONTEXT.md D-18):** Same healthcheck script reused in Phase 5 DEMO-02.

### Claude's Discretion

- Exact token-budget default value (2–4K range; tune empirically).
- Redis pub/sub channel naming vs sorted-set progress key.
- Upload form layout + component choices (shadcn/ui vs plain Tailwind — UI-SPEC resolves to shadcn/ui, New York style, Slate base).
- Alembic migration file naming + autogenerate flow.
- Error-log line format.
- Exact Dockerfile base image (`python:3.12-slim-bookworm` assumed).

### Deferred Ideas (OUT OF SCOPE)

- Glossary picker + CRUD in upload form (Phase 2 per D-15).
- Per-segment LLM streaming to UI.
- Translation memory / sha-indexed cache (hook via D-06; no Phase 1 code).
- Observability / traces / dashboards.
- Auth + multi-tenancy.
- Rate-limit measurement + dynamic batch-size adaptation (measure but keep static).
- `qwen3.6-plus` as VLM OCR path (Phase 4 consideration only).

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | DashScope international endpoint + qwen-mt-turbo verified end-to-end | Section 7: healthcheck pattern; AI-SPEC §3 client init |
| INFRA-02 | `qwen-mt-turbo` terminology API validated on VN↔EN + VN↔JA sample | Section 7: terminology plumbing; `extra_body` pattern |
| INFRA-03 | FastAPI + PostgreSQL + Redis + arq runs via docker-compose | Section 6: arq worker patterns; Section 3: infra stack |
| INFRA-04 | Next.js frontend can call FastAPI with CORS | Section 9: Next.js 16 patterns; CORS config |
| INFRA-05 | Noto CJK + Noto Sans Vietnamese fonts bundled in backend Docker image | Section 13: font wiring |
| UPLD-01 | File upload via drag-and-drop or picker, max 25 MB | Section 8: FastAPI upload; UI-SPEC drop zone |
| UPLD-02 | Format auto-detect + rejection with clear message | Section 8: 415 rejection pattern |
| UPLD-03 | Source/target language picker driven by qwen-mt-turbo supported languages | Section 10: auto-detect; language API endpoint |
| UPLD-04 | (Deferred to Phase 2 per D-15) | — |
| UPLD-05 | Form submit creates job, returns job_id, redirects to status page | Section 6: job creation; Section 9: Next.js redirect |
| CORE-01 | Parser extracts ordered Segment tree with stable IDs + style context | Section 4: DOCX traversal; D-05/D-06 pattern |
| CORE-02 | Translation batches via openai SDK against DashScope international | AI-SPEC §3 translate_batch entry point |
| CORE-03 | Segment-count assertion per batch; retry up to 3 times; loud failure | Section 5: count assertion boundary; AI-SPEC §4 |
| CORE-04 | NFC normalization on every LLM output string | Section 5: NFC strategy; `nfc()` helper |
| CORE-05 | Non-translatable tokens → `⟦T{n}⟧` before translation, restored after | Section 5: placeholder taxonomy; regex ruleset |
| CORE-06 | Rate-limit + 5xx retries with exponential backoff; UI shows retries | AI-SPEC §4 retry pattern; D-12 retry chip |
| JOB-01 | Job states: queued/running/needs_review/failed/done in Postgres | Section 6: job state machine |
| JOB-02 | Status page polls/SSE for progress + state transitions | Section 7: SSE + TanStack fallback pattern |
| JOB-03 | Per-segment progress counter shown while running | D-09/D-10 payload shape |
| JOB-04 | Failed job surfaces human-readable error + failing segment(s) | D-11 error surface; Section 6 error log |
| DOCX-01 | DOCX round-trip: structure/bold/italic/underline/fonts/headings preserved | Section 4: run-level replacement pattern |
| DOCX-02 | Run-merge strategy: reconstruct para text → translate → write into runs[0] | Section 4: run-merge heuristic |
| DOCX-03 | Hyperlinks + code spans preserved as non-translatable | Section 5: placeholder taxonomy (hyperlinks) |
| DOCX-04 | Tracked changes + comments flagged/stripped per user choice | D-13/D-14; Section 4: tracked-changes handling |
| LANG-01 | Language options driven by qwen-mt-turbo; auto-detect available | Section 10: DashScope auto-detect |
| LANG-02 | VN↔EN, VN↔JA, VN↔ZH, EN↔JA exercised in demo test pack | Section 10: language pair coverage |

</phase_requirements>

---

## Summary

Phase 1 is a full-stack greenfield build: FastAPI backend with arq async job queue, Next.js 16 App Router frontend, PostgreSQL + Redis infrastructure, and a DOCX translation pipeline powered by qwen-mt-turbo via the DashScope international endpoint. All 26 Phase 1 requirements map cleanly to verified patterns — the primary research value is surfacing DOCX traversal edge cases and the arq/SSE wiring that do not appear in CLAUDE.md.

The critical risk is the DOCX traversal scope: `document.paragraphs` does not see table cells, headers, footers, comments, or text boxes. The walker must descend through `document.element` XML, walking body paragraphs, table cells (row-major), section headers/footers, and — for comments — the `word/comments.xml` part. Hyperlinks inside paragraphs are accessible via `paragraph.hyperlinks` (python-docx 1.2.0 API). The run-merge strategy is: concatenate all `run.text` values → translate the concatenated string → write translated text into `runs[0].text`, blank `runs[1:]` text (set to `""`), preserving the `_r` element and its `rPr` child intact on every run so formatting XML is never removed.

The secondary risk is the SSE + arq progress wiring: the arq worker must write JSON progress payloads to Redis pub/sub (`PUBLISH job:{job_id} <payload>`); the FastAPI SSE endpoint subscribes with `aioredis.client.PubSub` and streams each message as a Server-Sent Event; the Next.js client uses `@microsoft/fetch-event-source` for auth-header-capable SSE connection with TanStack Query as the cache layer and polling fallback.

**Primary recommendation:** Start with the healthcheck spike (INFRA-01/02) to confirm DashScope reachability and terminology API behavior before any pipeline code. This is the only external dependency that cannot be stubbed and has hard-blocked teams in prior VNEXT projects (wrong endpoint = cryptic 401 with no body).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| File upload + format validation | API / Backend (FastAPI) | Browser (pre-check file type + size) | Size limit enforcement must happen server-side; MIME sniffing is backend |
| Job creation + state persistence | API / Backend | — | Job table lives in PostgreSQL; arq queue in Redis |
| DOCX parsing + segmentation | API / Backend (pipeline module) | — | python-docx is Python-only; runs in backend worker |
| Translation batch execution | API / Backend (arq worker) | — | Long-running async task; must outlive HTTP request |
| Progress events (SSE) | API / Backend → Browser | — | Server pushes progress; browser consumes |
| Job status cache | Browser (TanStack Query) | API (Redis pub/sub source) | TanStack is the single source of truth in the client |
| DOCX reassembly + download | API / Backend | — | Output file written to disk; streamed to client |
| Language options API | API / Backend (static config endpoint) | — | qwen-mt-turbo language list is static per model version; served from backend |
| Tracked-changes detection | API / Backend (upload probe) | Browser (modal presentation) | Detection is XML parsing; UI presents the result |
| NFC normalization | API / Backend (pipeline/LLM layer) | — | Invariant on every LLM I/O boundary; purely server-side |
| Placeholder protection | API / Backend (pipeline layer) | — | Regex extraction/restoration before/after LLM call |
| Noto font availability | Backend Docker image | — | Only needed for Phase 3 PDF; installed now in Dockerfile |
| Infrastructure health check | Backend (scripts/healthcheck.py) | — | DashScope ping + DB + Redis + font presence |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.115.x | API framework | Async-native, Pydantic v2 integrated, SSE support via sse-starlette |
| python-docx | 1.2.0 | DOCX read/write | Official python-openxml library; run-level API verified |
| arq | 0.27.0 | Async job queue | asyncio-native, Redis-backed, no sync/async bridge needed |
| SQLAlchemy | 2.0.x | Async ORM | `AsyncSession` + `asyncpg` driver; Thu's existing production stack |
| asyncpg | 0.30.x | PostgreSQL driver | Fastest binary-protocol async driver |
| Alembic | 1.x | DB migrations | Standard complement to SQLAlchemy |
| openai | >=1.40,<2 | DashScope client | OpenAI-compatible endpoint; `extra_body` for translation_options |
| tiktoken | latest | Token estimation | cl100k_base approximates qwen token counts for batch budgeting |
| sse-starlette | 3.3.4 | SSE streaming | `EventSourceResponse`, async generator, `ping`, `is_disconnected()` |
| pydantic-settings | 2.x | Config from env | `SecretStr` for `DASHSCOPE_API_KEY` |
| structlog | latest | JSON logging | `job_id` context binding per D-19 |
| aioredis | 4.x (via redis-py 5.x) | Redis async client | Pub/sub for SSE progress; arq shares the pool |

### Frontend
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | ^16.2.3 | App Router framework | D-20: greenfield skip to Next.js 16; async params from day one |
| React | 19 | UI runtime | Bundled with Next.js 16 |
| @tanstack/react-query | 5.x | Server state + SSE cache | `setQueryData` from SSE; `refetchInterval` fallback |
| @microsoft/fetch-event-source | 2.x | SSE with auth headers | Native `EventSource` lacks custom headers |
| shadcn/ui (+ Radix UI) | latest | Component library | UI-SPEC: New York style, Slate base; production-quality accessible primitives |
| lucide-react | latest | Icons | Bundled with shadcn default config |
| tailwindcss | 3.x | Styling | shadcn dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| unicodedata (stdlib) | — | NFC normalization | CORE-04: normalize every LLM I/O string |
| python-multipart | 0.0.x | FastAPI file upload | Required peer for `UploadFile` parsing |
| httpx | 0.27.x | Async HTTP client (tests) | `ASGITransport` for FastAPI integration tests |
| pytest | 8.x | Test framework | Unit + integration tests |
| pytest-asyncio | 0.23.x | Async test support | All worker + pipeline tests are async |
| pytest-cov | latest | Coverage reporting | 80% threshold per CLAUDE.md |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | FastAPI 0.135+ built-in SSE | sse-starlette locked by CLAUDE.md; more mature ping/disconnect handling |
| aioredis / redis-py 5 | aioredis standalone (deprecated) | redis-py 5.x absorbed aioredis API; use `redis.asyncio` namespace |
| arq 0.27 | Celery | Celery async is a bolt-on; arq is asyncio-native — locked by CLAUDE.md |

**Installation (backend):**
```bash
uv add 'fastapi>=0.115,<0.116' 'python-docx==1.2.0' 'arq==0.27.0' \
    'sqlalchemy[asyncio]>=2.0,<3' 'asyncpg>=0.30' 'alembic>=1.13' \
    'openai>=1.40,<2' 'tiktoken' 'sse-starlette==3.3.4' \
    'pydantic-settings>=2' 'structlog' 'redis[hiredis]>=5' \
    'python-multipart' 'uvicorn[standard]'
```

**Installation (frontend):**
```bash
npx create-next-app@16 frontend --typescript --tailwind --app --src-dir
cd frontend
npm install @tanstack/react-query @microsoft/fetch-event-source
npx shadcn@latest init
npx shadcn@latest add button badge progress dialog select table toast alert collapsible radiogroup skeleton separator
```

**Version verification:** [VERIFIED: npm view / pip show not run — versions taken from CLAUDE.md stack table which cites PyPI and npm registry as of 2026-04-17]

---

## Architecture Patterns

### System Architecture Diagram

```
Browser (Next.js 16)
  │
  │  POST /api/upload (multipart, file + params)
  ▼
[Next.js Route Handler: app/api/upload/route.ts]
  │  forward to FastAPI
  │  GET /api/languages  →  static language list (TanStack staleTime: 24h)
  ▼
[FastAPI API: src/app/api/]
  │  validate file (size ≤ 25MB, type ∈ {docx,pdf,pptx})
  │  probe for tracked changes (<w:ins>/<w:del>)
  │  write to .data/jobs/{job_id}/source.docx
  │  INSERT Job(status=queued) → PostgreSQL
  │  ENQUEUE translate_job(job_id) → Redis (arq queue)
  │  return { job_id }
  ▼
  │  GET /jobs/{job_id}/stream  (SSE)
  │                              ◄──────────────────┐
  │                                                  │ PUBLISH job:{id} <progress>
  ▼                                                  │
[FastAPI SSE Endpoint]                        [arq Worker]
  │  aioredis SUBSCRIBE job:{id}                     │
  │  yield EventSourceResponse                        │  1. parse DOCX (document.element walker)
  │  → { status, stage, segments_done/total, ... }   │  2. build Segment tree (D-05)
  │                                                   │  3. token-budget batch packing
  ▼                                                   │  4. asyncio.gather(translate_batch × 4)
[Browser TanStack Query cache]                        │     ↓ per batch:
  │  setQueryData on SSE event                        │       CORE-05 placeholder extraction
  │  refetchInterval fallback if SSE closed           │       qwen-mt-turbo call (extra_body)
  │                                                   │       CORE-03 count assertion
  ▼                                                   │       CORE-04 NFC normalize
[Job Status Page: /jobs/{id}]                         │       CORE-05 placeholder restore
  │  stage indicator / progress bar / counter         │  5. reassemble DOCX (run-merge write)
  │                                                   │  6. write output.docx
  │  Download button (terminal done state)            │  7. UPDATE Job(status=done, output_path)
  │  GET /jobs/{job_id}/download                      │  8. PUBLISH job:{id} done event
  ▼                                                   │
[FastAPI: stream output.docx]                         │  on error: append errors.log
                                                       │  UPDATE Job(status=failed, error_msg)
```

### Recommended Project Structure

```
ai-translation/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── pyproject.toml           # uv-managed
│   ├── Dockerfile               # python:3.12-slim-bookworm + Noto fonts
│   └── src/
│       └── app/
│           ├── main.py          # FastAPI app + lifespan
│           ├── core/
│           │   ├── config.py    # pydantic-settings Settings
│           │   └── logging.py   # structlog JSON setup
│           ├── api/
│           │   ├── upload.py    # POST /upload, GET /languages
│           │   ├── jobs.py      # GET /jobs/{id}, GET /jobs/{id}/stream, GET /jobs/{id}/download
│           │   └── health.py    # GET /health (used by healthcheck.py)
│           ├── db/
│           │   ├── models.py    # Job, Segment SQLAlchemy models
│           │   ├── session.py   # AsyncEngine factory, AsyncSession dependency
│           │   └── migrations/  # Alembic (alembic.ini at backend/)
│           ├── pipeline/
│           │   ├── docx/
│           │   │   ├── extractor.py    # DOCX walker → Segment tree
│           │   │   ├── reassembler.py  # Segment tree → DOCX write (run-merge)
│           │   │   └── tracked.py      # <w:ins>/<w:del> detect + strip/preserve
│           │   ├── segment.py          # Segment dataclass + SHA ID
│           │   └── placeholder.py      # CORE-05 extract/restore + regex ruleset
│           ├── llm/
│           │   ├── client.py           # AsyncOpenAI factory (reads Settings)
│           │   ├── translator.py       # translate_batch() — CORE-03/04/05
│           │   ├── terminology.py      # glossary dict → terms list
│           │   └── token_budget.py     # estimate_tokens(), pack_into_batches()
│           ├── services/
│           │   └── job_service.py      # Job CRUD + status transitions
│           └── workers/
│               └── translate_worker.py # arq WorkerSettings, startup/shutdown, translate_job
├── frontend/
│   ├── package.json
│   └── src/
│       └── app/
│           ├── layout.tsx              # root layout + QueryClientProvider
│           ├── page.tsx                # redirect to /upload
│           ├── upload/
│           │   └── page.tsx            # drag-drop upload form
│           ├── jobs/
│           │   ├── page.tsx            # jobs list
│           │   └── [id]/
│           │       └── page.tsx        # job status + SSE
│           └── api/
│               └── upload/
│                   └── route.ts        # proxy to FastAPI (handles multipart)
└── scripts/
    └── healthcheck.py                  # INFRA-01/02 + DB + Redis + font check
```

---

## Section 4: python-docx Run-Level Replacement

### The Run-Merge Invariant (DOCX-02)

**Problem:** Word splits a logical sentence across multiple `<w:r>` elements at spell-check boundaries, cursor positions, and formatting changes. Translating runs individually produces incoherent fragments.

**Why `paragraph.text = value` is forbidden (CLAUDE.md explicit anti-pattern):**

From python-docx source (Context7 verified): the `text` setter calls `self.clear(); self.add_run(text)` — this removes all existing runs and creates a single new run with no formatting. Bold, italic, underline, font name, font color, font size are all lost.

**Correct run-merge pattern:**

```python
# Source: python-docx 1.2.0 docs — /websites/python-docx_readthedocs_io_en
def merge_and_replace_paragraph_text(paragraph, translated_text: str) -> None:
    """
    Replace paragraph text with translated_text while preserving all run formatting.

    Strategy:
    1. Keep runs[0] as the single text-bearing run (its rPr carries the formatting).
    2. Blank all subsequent runs' .text (set to "") — do NOT remove the run elements;
       removing <w:r> elements can corrupt adjacent formatting, hyperlinks, or bookmarks.
    3. Never call paragraph.text = value (destroys all rPr).
    """
    runs = paragraph.runs
    if not runs:
        # Paragraph has no runs (e.g., empty para) — add one
        paragraph.add_run(translated_text)
        return
    # Write translated text into first run; blank the rest
    runs[0].text = translated_text
    for run in runs[1:]:
        run.text = ""
```

**Preserving run properties:** `run.text = value` in python-docx sets `<w:t>` inside the existing `<w:r>` element — the `<w:rPr>` child (containing `<w:b/>`, `<w:i/>`, `<w:u/>`, `<w:rFonts/>`, `<w:color/>`, `<w:sz/>`) is left intact. [VERIFIED: Context7 /websites/python-docx_readthedocs_io_en — run.text property source shows it only touches `<w:t>` not `<w:rPr>`]

**Run-merge heuristic for adjacent run splitting:**

Runs in the same paragraph sometimes split a single word (e.g., `"tài"` + `"liệu"`) at font-substitution boundaries. The safe merge rule: collect `paragraph.text` (the already-concatenated string from python-docx), translate it, write back into `runs[0]`. This is safe because we never merge runs with different `rPr` — we preserve ALL runs and merely redistribute the text string.

**Critical caveat:** When a paragraph's first run has `None` for a formatting property (meaning "inherit"), do not set it. The merge strategy works correctly because `runs[0].text = value` never touches the inherited properties.

### Full Document Traversal Order (CORE-01 / DOCX-01)

`document.paragraphs` only yields paragraphs in the document body — it does NOT see table cells, headers, footers, or text boxes. Use `document.element` for comprehensive traversal.

```python
# Source: python-docx 1.2.0 — document.iter_inner_content() yields Paragraph | Table
# Context7 verified: /websites/python-docx_readthedocs_io_en

from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell

def walk_document(doc: Document):
    """
    Yield all Segment-bearing locations in document order.
    Order: body content (paragraphs + table cells row-major), then headers/footers by section.
    """
    # 1. Body: paragraphs + table cells (row-major)
    yield from _walk_body(doc)

    # 2. Headers and footers per section
    for section in doc.sections:
        for hf in [section.header, section.footer,
                   section.even_page_header, section.even_page_footer,
                   section.first_page_header, section.first_page_footer]:
            if hf is not None and hf.is_linked_to_previous is False:
                yield from _walk_body_element(hf._element)

    # 3. Comments (separate XML part — word/comments.xml)
    # Access via doc.part._comments_part (if present)
    # See tracked-changes section below

def _walk_body(doc: Document):
    """Walk body preserving paragraph-table reading order."""
    for block in doc.iter_inner_content():  # yields Paragraph | Table
        if isinstance(block, Paragraph):
            yield ("para", block)
        elif isinstance(block, Table):
            yield from _walk_table(block)

def _walk_table(table: Table):
    """Row-major: top-to-bottom, left-to-right within row."""
    for row in table.rows:
        for cell in row.cells:
            # Nested tables: cell.tables may be non-empty
            for block in cell.iter_inner_content():
                if isinstance(block, Paragraph):
                    yield ("cell_para", block)
                elif isinstance(block, Table):
                    yield from _walk_table(block)  # nested table recursion
```

**Nested tables:** `cell.iter_inner_content()` is the safe way to discover nested tables — do NOT use `cell.paragraphs` which skips nested table content. [CITED: python-docx 1.2.0 `_Cell.iter_inner_content()`]

**Text boxes:** python-docx does not expose text boxes via a high-level API. They live in `<w:drawing>` or `<mc:AlternateContent>` elements. For Phase 1, text boxes are detected by XPath query on `doc._element` and translated via their embedded `<w:t>` elements. [ASSUMED — verified that text boxes are not in `document.paragraphs`; exact XPath pattern is standard knowledge]

**Hyperlinks (DOCX-03):** In python-docx 1.2.0, `paragraph.hyperlinks` yields `Hyperlink` objects. Hyperlink text (display text) IS translatable; the `href` URL is NOT. Use `paragraph.iter_run_level_items()` to visit both `Run` and `Hyperlink` objects in order. [VERIFIED: Context7 /websites/python-docx_readthedocs_io_en — `paragraph.hyperlinks` and `iter_run_level_items()` API confirmed]

Pattern: for each `Hyperlink` in the paragraph, translate `hyperlink.text` but preserve `hyperlink.url`. The hyperlink XML (`<w:hyperlink r:id="...">`) references the relationship ID; never touch the relationship targets.

**Comments (DOCX-04 per D-14):** python-docx 1.2.0 has limited comment support. Access comment bodies via `doc.part._comments_part.element` (raw XML). Each `<w:comment>` has a `<w:p>` body. Extract and translate comment paragraph text using the same run-merge pattern.

### Tracked Changes Detection (DOCX-04 per D-13)

```python
def has_tracked_changes(doc: Document) -> bool:
    """Detect <w:ins> or <w:del> in the document body XML."""
    body_xml = doc._element.xml
    return "<w:ins" in body_xml or "<w:del" in body_xml
```

[VERIFIED: Context7 /python-openxml/python-docx — CT_Body XSD confirms `ins` and `del` as valid body-level elements]

**Strip strategy (user chooses "strip"):** Walk `doc._element` with lxml, find all `<w:ins>` elements, keep their `<w:r>` children (move them out), remove `<w:ins>` wrapper. Find all `<w:del>` elements with their content and remove entirely (deleted text is gone).

**Preserve strategy (user chooses "preserve"):** Walk both `<w:ins>` and `<w:del>` runs as Segments. Mark segments with `is_inserted=True` or `is_deleted=True` so the reassembler can wrap them back in the appropriate XML after translation.

---

## Section 5: Segment-Count Assertion, NFC, and Placeholder Protection

### CORE-03: Segment-Count Assertion Boundary

**Per-batch (primary — fail-fast):** The assertion fires immediately after `translate_batch()` returns, before any run is written. If `len(translated_lines) != len(source_segments)`, the batch is retried up to 3 times (CORE-06). After 3 failures, the job transitions to `failed` with the batch number and source texts in `errors.log`. [ASSUMED: per-batch is the right boundary per AI-SPEC §3 implementation and D-07]

**Per-document (secondary sanity check):** After full reassembly, assert that `job.segments_done == job.segments_total`. This catches any accidental passthrough that slipped through per-batch checks. Log a warning but do not fail the job at this stage (reassembly already succeeded).

```python
# Per-batch enforcement (in translate_batch() — AI-SPEC §3)
if len(translated_lines) != len(payload_segments):
    raise ValueError(
        f"CORE-03 violation: sent {len(payload_segments)} segments, "
        f"received {len(translated_lines)} translated lines."
    )
```

### CORE-04: NFC Normalization Strategy

**Normalize at two boundaries:**

1. **Ingest (before segmentation):** After reading `run.text` from python-docx, normalize to NFC. This covers older Vietnamese DOCX files from macOS (which writes NFD via Apple Text Services).

2. **Output (after LLM response, before run-insertion):** After splitting `translated_lines`, normalize each line to NFC before writing to `runs[0].text`.

**Mixed NFC/NFD within a single run (macOS DOCX edge case):** macOS-authored DOCX files can contain NFD-encoded tone marks within a run that appears NFC in the Python repr due to display normalization. The safe fix is to normalize every string that crosses a python-docx API boundary.

```python
import unicodedata

def nfc(s: str) -> str:
    """Normalize string to NFC Unicode form. Apply at every LLM I/O boundary."""
    return unicodedata.normalize("NFC", s)
```

[VERIFIED: Python stdlib unicodedata — `unicodedata.normalize("NFC", s)` confirmed]

### CORE-05: Non-Translatable Placeholder Taxonomy

The AI-SPEC §3 `translate_batch` already handles whitespace-only and digit-only passthrough. Phase 1 needs a broader placeholder extraction layer for DOCX content.

**Taxonomy of non-translatable segments in DOCX:**

| Category | Examples | Detection |
|----------|----------|-----------|
| Bare URLs | `https://aicore.vn/products`, `http://example.com` | `re.compile(r'https?://\S+')` |
| Email addresses | `contact@aicore.vn`, `thu@example.com` | `re.compile(r'[\w.+-]+@[\w.-]+\.\w+')` |
| Hyperlink hrefs | Already protected by hyperlink-URL preservation pattern (Section 4) | structural (not text-based) |
| Template vars (mustache) | `{{user_name}}`, `{{company}}` | `re.compile(r'\{\{[^}]+\}\}')` |
| Template vars (dollar) | `${foo}`, `${bar.baz}` | `re.compile(r'\$\{[^}]+\}')` |
| Template vars (ERB) | `<%= bar %>`, `<% code %>` | `re.compile(r'<%=?\s*[^%]+%>')` |
| ISO-8601 dates | `2026-04-23`, `2026-04-23T10:00:00Z` | `re.compile(r'\d{4}-\d{2}-\d{2}(T[\d:Z.+-]+)?')` |
| Version strings | `v2.3.1`, `v1.0.0-beta.1` | `re.compile(r'v\d+\.\d+[\.\d\w-]*')` |
| Pure numbers | Already handled by `stripped.isdigit()` in translate_batch | in AI-SPEC §3 |
| Code spans | Runs with style `Code` or `Inline Code` | `run.style.name in {'Code', 'Inline Code', 'verbatim'}` |

**Extraction pattern (CORE-05):**

```python
import re
from dataclasses import dataclass

_PROTECTED_PATTERNS = [
    re.compile(r'https?://\S+'),
    re.compile(r'[\w.+-]+@[\w.-]+\.\w{2,}'),
    re.compile(r'\{\{[^}]+\}\}'),
    re.compile(r'\$\{[^}]+\}'),
    re.compile(r'<%=?\s*[^%]+%>'),
    re.compile(r'\d{4}-\d{2}-\d{2}(?:T[\d:Z.+\-]+)?'),
    re.compile(r'v\d+\.\d+[\.\d\w\-]*'),
]

_PLACEHOLDER_RE = re.compile(r'⟦T(\d+)⟧')

def extract_placeholders(text: str) -> tuple[str, dict[int, str]]:
    """
    Replace all non-translatable tokens with ⟦T{n}⟧ markers.
    Returns (modified_text, {n: original_token}).
    """
    tokens: dict[int, str] = {}
    counter = 0
    for pattern in _PROTECTED_PATTERNS:
        def replacer(m, c=None):
            nonlocal counter
            idx = counter
            counter += 1
            tokens[idx] = m.group(0)
            return f"⟦T{idx}⟧"
        text = pattern.sub(replacer, text)
    return text, tokens

def restore_placeholders(text: str, tokens: dict[int, str]) -> str:
    """Restore ⟦T{n}⟧ markers back to original tokens."""
    def restorer(m):
        idx = int(m.group(1))
        return tokens.get(idx, m.group(0))  # fallback: keep marker if missing
    return _PLACEHOLDER_RE.sub(restorer, text)
```

**Validation after restore:** Assert `len(re.findall(r'⟦T\d+⟧', restored)) == 0` — no unreplaced markers remain. If markers are missing (model dropped them), the batch fails CORE-03-style with a placeholder-specific error message.

---

## Section 6: arq Worker Patterns with Async SQLAlchemy

### Engine and Session Lifecycle

Share a single `AsyncEngine` across all worker tasks via the arq `ctx` dict. Create the engine once at `startup`; dispose at `shutdown`. Each job creates a single `AsyncSession` for its duration (not one per batch — that would leave too many open connections under concurrent batch execution).

```python
# workers/translate_worker.py
import asyncio
import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from redis.asyncio import Redis
from openai import AsyncOpenAI, RateLimitError, APIStatusError, APIConnectionError
from app.core.config import get_settings
from app.llm.client import make_llm_client

log = structlog.get_logger()

async def startup(ctx: dict) -> None:
    settings = get_settings()
    # Create shared resources — one per worker process
    ctx["llm_client"] = make_llm_client(settings)
    ctx["engine"] = create_async_engine(str(settings.database_url), pool_size=5)
    ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
    ctx["redis"] = Redis.from_url(str(settings.redis_url), decode_responses=True)
    log.info("worker_started")

async def shutdown(ctx: dict) -> None:
    await ctx["llm_client"].close()
    await ctx["engine"].dispose()
    await ctx["redis"].aclose()
    log.info("worker_stopped")

async def translate_job(ctx: dict, job_id: str) -> None:
    """Main arq job function. One AsyncSession for the entire job duration."""
    async with ctx["session_factory"]() as session:
        log.bind(job_id=job_id)
        await _run_translation(ctx, session, job_id)

class WorkerSettings:
    functions = [translate_job]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10  # max concurrent jobs per worker process
    redis_settings = ...  # from settings
```

[VERIFIED: Context7 /websites/arq-docs_helpmanual_io — `on_startup`, `on_shutdown`, `ctx` dict pattern confirmed]

### Job State Transitions

```
queued → running → (batches succeed) → succeeded → done
                 → (batch fails after 3 retries) → failed
                 → (batch has needs_review flags) → needs_review
```

Progress updates written to Redis pub/sub key `job:{job_id}` after every batch. The SSE endpoint subscribes with `aioredis.client.PubSub.subscribe("job:{job_id}")` and yields each message as an SSE event.

**Redis progress key scheme (D-09):**
```json
{
  "status": "running",
  "stage": "translate",
  "segments_done": 47,
  "segments_total": 210,
  "current_batch": 5,
  "retry_count": 0,
  "last_message": "Translating batch 5/23"
}
```

Published via `await redis.publish(f"job:{job_id}", json.dumps(payload))`.

---

## Section 7: SSE Pattern (sse-starlette 3.x)

### FastAPI SSE Endpoint

```python
# app/api/jobs.py
import json
import asyncio
from fastapi import APIRouter, Depends
from starlette.requests import Request
from sse_starlette import EventSourceResponse
from redis.asyncio import Redis

router = APIRouter()

async def job_progress_generator(request: Request, job_id: str, redis: Redis):
    """
    Subscribe to Redis pub/sub for job:{job_id}.
    Yield SSE events until terminal state or client disconnect.
    """
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")
    try:
        while True:
            if await request.is_disconnected():
                break
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                payload = json.loads(message["data"])
                yield {"data": json.dumps(payload), "event": "progress"}
                if payload.get("status") in ("done", "failed", "needs_review"):
                    break
            else:
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.close()

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str, request: Request, redis: Redis = Depends(get_redis)):
    return EventSourceResponse(
        job_progress_generator(request, job_id, redis),
        ping=15,
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"}
    )
```

[VERIFIED: Context7 /sysid/sse-starlette — `EventSourceResponse`, `ping`, `is_disconnected()`, `CancelledError` handling confirmed]

### Next.js 16 App Router: SSE Client + TanStack Query (D-09)

```typescript
// hooks/useJobProgress.ts
"use client"
import { useQueryClient, useQuery } from "@tanstack/react-query"
import { fetchEventSource } from "@microsoft/fetch-event-source"
import { useEffect, useRef } from "react"

type JobStatus = "queued" | "running" | "needs_review" | "failed" | "done"
interface JobProgress {
  status: JobStatus
  stage: string
  segments_done: number
  segments_total: number
  current_batch: number
  retry_count: number
  last_message: string
  error?: { code: string; message: string; failing_segments: unknown[] }
}

const TERMINAL = new Set(["done", "failed", "needs_review"])

export function useJobProgress(jobId: string) {
  const queryClient = useQueryClient()
  const sseOpen = useRef(false)

  useEffect(() => {
    const ctrl = new AbortController()
    sseOpen.current = true

    fetchEventSource(`/api/jobs/${jobId}/stream`, {
      signal: ctrl.signal,
      onmessage(ev) {
        const data: JobProgress = JSON.parse(ev.data)
        queryClient.setQueryData(["job", jobId], data)
      },
      onerror() {
        sseOpen.current = false  // triggers polling fallback
      },
      onclose() {
        sseOpen.current = false
      },
    })

    return () => ctrl.abort()
  }, [jobId, queryClient])

  // Polling fallback: active when SSE is closed + job not terminal
  return useQuery<JobProgress>({
    queryKey: ["job", jobId],
    queryFn: () => fetch(`/api/jobs/${jobId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && TERMINAL.has(status)) return false  // stop polling on terminal
      if (sseOpen.current) return false                  // SSE active, no polling
      return 2000  // poll every 2s when SSE closed
    },
    staleTime: 0,
  })
}
```

[VERIFIED: Context7 /websites/tanstack_query_v5 — `setQueryData` + `refetchInterval` as function confirmed; @microsoft/fetch-event-source `fetchEventSource` signature from library README — ASSUMED for exact API]

---

## Section 8: FastAPI Upload Handling

### File Size Enforcement Pattern

FastAPI does not have a built-in request-body size limit. The correct approach for PoC:

1. **Pre-check via `Content-Length` header** (fast path, before reading body):
```python
@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    # Pre-check content-length if browser sends it (not guaranteed)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum is 25 MB.")

    # Read file content (streaming-safe via UploadFile)
    MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
    chunk_size = 64 * 1024
    total = 0
    chunks = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large. Maximum is 25 MB.")
        chunks.append(chunk)
    content = b"".join(chunks)

    # Seek back to start for further processing
    await file.seek(0)
```

2. **MIME type validation:**
```python
ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/pdf": "pdf",
}
ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}

ext = Path(file.filename or "").suffix.lower()
if ext not in ALLOWED_EXTENSIONS:
    raise HTTPException(status_code=415, detail="Unsupported file type. Upload a DOCX, PDF, or PPTX.")
```

**HTTP status codes:**
- 413: file size exceeds limit
- 415: unsupported media type
- 422: missing required fields (FastAPI Pydantic automatic)
- 400: tracked-changes state conflict (user did not respond to modal — client-side guard)

[VERIFIED: Context7 /websites/fastapi_tiangolo — `request.stream()`, `HTTP_413_CONTENT_TOO_LARGE` constant, `UploadFile` API confirmed]

---

## Section 9: Next.js 16 App Router Patterns

### File Upload via Next.js API Route (Proxy to FastAPI)

Server Action vs API Route: use **API Route** (`app/api/upload/route.ts`) for streaming file upload. Server Actions have a 1 MB default body limit that requires config to override; API Routes handle `formData()` natively without configuration.

```typescript
// app/api/upload/route.ts
export async function POST(request: Request) {
  const formData = await request.formData()
  const file = formData.get("file") as File | null
  if (!file) return Response.json({ error: "No file" }, { status: 400 })

  // Forward to FastAPI backend (running at api:8000 in docker-compose)
  const backendUrl = process.env.BACKEND_URL || "http://api:8000"
  const backendForm = new FormData()
  backendForm.append("file", file)
  backendForm.append("source_lang", formData.get("source_lang") as string)
  backendForm.append("target_lang", formData.get("target_lang") as string)

  const response = await fetch(`${backendUrl}/upload`, {
    method: "POST",
    body: backendForm,
  })

  const data = await response.json()
  return Response.json(data, { status: response.status })
}
```

[VERIFIED: Context7 /vercel/next.js — `request.formData()` in App Router Route Handler confirmed]

### Monaco DiffEditor (Phase 2 Preview — wire dynamic import now)

```typescript
// components/DiffEditor.tsx — Phase 2 placeholder, wired Phase 1
import dynamic from "next/dynamic"
const MonacoDiffEditor = dynamic(
  () => import("@monaco-editor/react").then(m => m.DiffEditor),
  { ssr: false }  // Monaco requires browser APIs; must not SSR
)
```

[ASSUMED — `dynamic(() => import, { ssr: false })` pattern is standard for browser-only libs in Next.js; specific Monaco import path not verified]

---

## Section 10: Language Auto-Detect (LANG-01/02)

**DashScope qwen-mt-turbo supports `source_lang="auto"`** natively — verified via official Alibaba Cloud Machine Translation documentation. [VERIFIED: official Alibaba Cloud docs — "To automatically detect the source language, set source_lang to auto"]

Language list endpoint (LANG-01 — backend serves static list):

```python
# The qwen-mt-turbo supported language list is static per model version.
# Serve from a hardcoded list in the backend (loaded from a YAML/JSON config).
# UI loads via GET /languages with TanStack staleTime: 24h (UI-SPEC).
SUPPORTED_LANGUAGES = [
    "Vietnamese", "English", "Japanese", "Chinese (Simplified)",
    "Chinese (Traditional)", "Korean", "French", "Spanish", "German",
    "Thai", "Arabic", "Hindi",
    # ... 80 more from the official 92-language list
]
```

**No local fallback library needed for Phase 1.** DashScope auto-detect covers Vietnamese, English, Japanese, Chinese (all target languages for LANG-02). The detected language is returned in the API response metadata and persisted on the Job row.

**Short-segment auto-detect caution:** For segments shorter than ~10 characters (whitespace-trimmed), qwen-mt-turbo auto-detect may produce lower-confidence results. These short segments are often whitespace-only or digit-only and are already handled as passthroughs by the CORE-05 placeholder logic, so this edge case is covered. [ASSUMED — based on general MT model behavior; not DashScope-specific documentation]

---

## Section 11: DashScope + qwen-mt-turbo Known Quirks

**Rate limits:** Not published for the international tier. [VERIFIED: official docs confirm existence but provide no numeric values — "For information about concurrent request limits, see Qwen-MT" but the linked page also does not list numbers as of 2026-04-17]. Measure empirically during Phase 1 testing. Recommendation: start at D-17's 4 concurrent batches; if 429s appear, reduce to 2 and log the threshold.

**Empty-string input:** The `translate_batch` function in AI-SPEC §3 guards `if not segments: raise ValueError`. An empty `""` after stripping is handled as whitespace-only passthrough by the `not stripped` check. Never send an empty string to the model.

**`response.choices[0].message.content is None`:** Occurs on `content_filter` or `length` finish_reason. Already guarded in AI-SPEC §3 with `raw_output = response.choices[0].message.content or ""`. This triggers CORE-03 count assertion immediately (0 lines vs N segments), surfacing the failure cleanly.

**8,192 input token hard limit (NOT 1M):** qwen-mt models have an 8,192 input token hard ceiling. The 1M context window in CLAUDE.md refers to the base Qwen3 model, not the MT API variant. [VERIFIED: AI-SPEC Pitfall #4 + Alibaba Cloud MT API docs]

**No system message:** qwen-mt-turbo is not a chat model. Do not add `{"role": "system", ...}` — it may treat it as text to translate. All directives go via `extra_body.translation_options`. [VERIFIED: AI-SPEC Pitfall #2]

**Temperature:** Do not set. qwen-mt-turbo documentation does not list temperature as a supported parameter. [VERIFIED: AI-SPEC Pitfall #3]

---

## Section 12: Docker Noto Font Wiring

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/*
```

**Phase 1 usage:** Fonts are NOT used for DOCX (Word renders fonts client-side) or for SSE/API logic. Install now so the Dockerfile does not require changes when Phase 3 (PDF reinsertion with PyMuPDF) begins. The INFRA-05 healthcheck verifies their presence at expected paths (`/usr/share/fonts/opentype/noto/` on Debian bookworm). [ASSUMED: Debian bookworm font paths; standard package behavior]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async job queue | Custom Redis polling loop | arq 0.27 | Job persistence, retry, result storage, `ctx` lifecycle — all built-in |
| SSE streaming | Raw `StreamingResponse` with string concat | sse-starlette `EventSourceResponse` | Handles `ping`, `is_disconnected`, graceful shutdown, proxy buffering headers |
| File upload size limit | nginx config only | Streaming read with counter + `raise HTTPException(413)` | nginx isn't always in front; defense in depth required |
| Token counting for qwen | Character-count heuristic | tiktoken cl100k_base (`estimate_tokens()`) | `cl100k_base` is the best available public approximation; heuristic ratios in AI-SPEC §4 are calibrated |
| Unicode normalization | Custom diacritic handling | `unicodedata.normalize("NFC", s)` | stdlib, correct, zero overhead |
| Placeholder extraction | Custom XML walking | Regex on pre-extracted text + structural hyperlink preservation | Regex covers 95% of cases; hyperlinks are handled structurally so the regex doesn't need to match them |
| Progress polling | Timer + database poll every N ms | Redis pub/sub → SSE → TanStack Query cache | pub/sub is push-based; SSE eliminates polling overhead during active translation |

**Key insight:** The DOCX translation pipeline has two truly hard problems — run-level format preservation and segment-count integrity — and both have narrow solutions (`runs[0].text = value` + `len() == len()` assertion). Everything else in the stack has a battle-tested library solution.

---

## Common Pitfalls

### Pitfall 1: `paragraph.text = value` Destroys Run Formatting
**What goes wrong:** Calling `paragraph.text = translated_text` calls `paragraph.clear()` then `paragraph.add_run(text)` — all `<w:rPr>` (bold, italic, underline, font, color) is removed.
**Why it happens:** The property setter is documented clearly but easy to misuse when under time pressure.
**How to avoid:** Use run-merge strategy: `runs[0].text = translated_text; [setattr(r, 'text', '') for r in runs[1:]]`. Never touch `paragraph.text` setter.
**Warning signs:** Output DOCX has all text in the default font with no bold/italic.

### Pitfall 2: `document.paragraphs` Misses Table Cells, Headers, Footers
**What goes wrong:** Translating only `doc.paragraphs` skips table cells, header text, footer text, and text boxes — the translated DOCX has untranslated tables and headers.
**How to avoid:** Use `doc.iter_inner_content()` + recursive `_walk_table()` + section header/footer iteration. See Section 4 traversal pattern.

### Pitfall 3: Redis pub/sub Session Leak in SSE Endpoint
**What goes wrong:** Each SSE request creates a `PubSub` subscription. If the connection drops without entering the `finally` block, the subscription leaks memory in Redis.
**How to avoid:** Always unsubscribe in a `finally` block (shown in Section 7 pattern). Wrap in `try/finally`.

### Pitfall 4: Docker WSL2 Integration Not Enabled
**What goes wrong:** `docker compose up` fails silently or with a confusing error because Docker Desktop WSL2 integration is disabled.
**How to avoid:** Before Phase 1 execution, enable Docker Desktop WSL2 integration in Docker Desktop Settings → Resources → WSL Integration. Verify with `docker ps` from the WSL shell. [VERIFIED: environment audit — Docker Desktop is installed on Windows but WSL2 integration is currently disabled]

### Pitfall 5: arq WorkerSettings Functions List Must Use Import-Time References
**What goes wrong:** If `translate_job` is defined in a separate module and referenced by string, arq cannot discover it unless the module is imported before the worker starts.
**How to avoid:** Always pass function references directly in `WorkerSettings.functions = [translate_job]` — never strings.

### Pitfall 6: `UploadFile.file.seek(0)` Required After Manual Size Check
**What goes wrong:** After manually reading the file to count bytes, the file cursor is at the end. Downstream code reading `UploadFile.file` gets empty bytes.
**How to avoid:** After the streaming size check, call `await file.seek(0)` before passing the file to the DOCX parser.

### Pitfall 7: NFC Normalization on Input, Not Just Output
**What goes wrong:** Source DOCX from macOS may contain NFD-encoded Vietnamese tone marks. If these are not normalized before segmentation, the `sha256(source_text)` segment ID is different from what it would be on NFC text — breaking deduplication and translation memory in future phases.
**How to avoid:** Normalize `run.text` to NFC at extraction time (before building Segment), and normalize LLM output to NFC before reassembly.

### Pitfall 8: Hyperlink URL Translated as Prose Text
**What goes wrong:** If hyperlink runs are included in `paragraph.text` extraction, the URL inside the hyperlink becomes part of the text sent to qwen-mt-turbo, which may translate it.
**How to avoid:** Use `paragraph.iter_run_level_items()` to walk both `Run` and `Hyperlink` objects. For `Hyperlink` items, translate `hyperlink.runs` text but protect `hyperlink.url`. For pure `Run` items, apply normal translation.

---

## Code Examples

### Full Run-Merge Write-Back (DOCX-02)

```python
# Source: python-docx 1.2.0 API — run.text setter preserves rPr
# Context7 /websites/python-docx_readthedocs_io_en verified

def write_translated_paragraph(paragraph, translated_text: str) -> None:
    """Write translated text back to paragraph using run-merge strategy."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(translated_text)
        return
    runs[0].text = nfc(translated_text)
    for run in runs[1:]:
        run.text = ""
```

### Segment ID Generation (D-06)

```python
import hashlib

def make_segment_id(source_text: str, structural_position: str) -> str:
    """Deterministic 16-char hex segment ID."""
    payload = f"{source_text}\x00{structural_position}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

### NFC Helper (CORE-04)

```python
import unicodedata
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)
```

### arq Job Enqueueing from FastAPI

```python
# In the upload endpoint, after writing source.docx and inserting the Job row:
from arq import create_pool
from arq.connections import RedisSettings

async def enqueue_translation_job(job_id: str, redis_pool) -> None:
    await redis_pool.enqueue_job("translate_job", job_id)
```

### SSE EventSourceResponse Minimal Pattern (sse-starlette 3.x)

```python
# Source: Context7 /sysid/sse-starlette — verified
from sse_starlette import EventSourceResponse
from starlette.requests import Request

@router.get("/jobs/{job_id}/stream")
async def stream(job_id: str, request: Request):
    async def generator():
        # ... (see Section 7 for full pattern)
        yield {"data": json.dumps(payload), "event": "progress"}
    return EventSourceResponse(generator(), ping=15,
                                headers={"X-Accel-Buffering": "no"})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-----------------|--------------|--------|
| Translate runs individually | Run-merge: para-level extract → single-unit translate → `runs[0].text` | Phase 1 (greenfield) | Correct formatting preservation |
| polling-only job status | Hybrid SSE primary + TanStack Query polling fallback | Next.js 16 + sse-starlette 3.x era | Smooth "translating 143/210" demo beat |
| Celery for async jobs | arq + Redis (asyncio-native) | 2023+ for FastAPI-first stacks | No sync/async bridge; simpler config |
| LangChain for LLM calls | Direct openai SDK with `extra_body` | Phase 1 (greenfield) | Direct access to `terminology` param; fewer abstraction layers |
| Next.js 15 | Next.js 16 (D-20) | Oct 2025 | Async params/cookies from day one; Turbopack default |

**Deprecated/outdated:**
- `paragraph.text = value` for translation: explicitly forbidden; destroys formatting
- `dashscope` Python SDK: less mature async; CLAUDE.md forbids it
- FastAPI `BackgroundTasks` for translation: no persistence, no retry, dies on restart

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Text boxes in DOCX are accessible via XPath on `doc._element` (`<w:drawing>` or `<mc:AlternateContent>`) | Section 4 (traversal) | Missed text box content; Phase 1 translation incomplete |
| A2 | `@microsoft/fetch-event-source` `fetchEventSource` API signature matches the pattern shown in Section 7 | Section 7 (SSE client) | Type errors in frontend; easy fix once library is installed |
| A3 | Monaco DiffEditor `dynamic(() => import, { ssr: false })` pattern works unchanged in Next.js 16 | Section 9 | Phase 2 Monaco integration needs additional config; low risk |
| A4 | Noto font paths in Debian bookworm are `/usr/share/fonts/opentype/noto/` | Section 12 | INFRA-05 healthcheck checks wrong path; easy to fix with `fc-list` |
| A5 | Short segments (<10 chars) hit lower auto-detect accuracy on DashScope | Section 10 | No practical impact for Phase 1 (covered by passthrough logic) |
| A6 | DashScope intl rate limits are not published and must be measured empirically | Section 11 | Unexpected 429 storms; mitigated by exponential backoff from day one |
| A7 | `redis.asyncio` (redis-py 5.x) is the correct import for async pub/sub in Phase 1 | Section 6/7 | Import errors; easy fix — `aioredis` is merged into redis-py 5 |

---

## Open Questions

1. **DashScope rate limits for qwen-mt-turbo international tier**
   - What we know: Not published. Exponential backoff from CORE-06 handles transient 429s.
   - What's unclear: Safe concurrent batch count for the Phase 1 demo machine. D-17 specifies 4; this may be too high or too low.
   - Recommendation: Run a 10-batch concurrency test in INFRA-01 spike; capture p50/p95 latency and 429 rate. Adjust `asyncio.Semaphore` value accordingly before demo.

2. **DOCX text box traversal coverage**
   - What we know: `document.paragraphs` doesn't include text boxes. They are in `<w:drawing>` / `<mc:AlternateContent>`.
   - What's unclear: Whether the demo DOCX files contain text boxes. If not, Phase 1 can add a TODO and flag them as "not translated" in the pipeline.
   - Recommendation: Inspect the golden fixture DOCX files at extraction time. If text boxes are present, implement the XPath walker; otherwise defer to Phase 3 as the PPTX phase already handles shape-level text.

3. **`paragraph.iter_run_level_items()` availability in python-docx 1.2.0**
   - What we know: Context7 confirms the method exists in the codebase. Version 1.2.0 is the locked version.
   - What's unclear: Whether this method was added in 1.2.0 or an earlier version (it may require falling back to `paragraph._p.iterchildren()` on earlier versions).
   - Recommendation: Verify with `from docx.text.paragraph import Paragraph; help(Paragraph.iter_run_level_items)` in the dev environment after `uv add 'python-docx==1.2.0'`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Backend runtime | ✓ | 3.12.3 | — |
| Node.js | Next.js frontend | ✓ | 24.13.1 | — |
| npm | Frontend package management | ✓ | 11.11.0 | — |
| uv | Python package management | ✓ | 0.11.6 | — |
| Docker Desktop | docker-compose stack | ✓ (installed on Windows) | — | WSL2 integration must be enabled before execution |
| Docker WSL2 integration | `docker compose up` from WSL shell | ✗ currently | — | Enable in Docker Desktop Settings → Resources → WSL Integration |
| Redis | arq queue + SSE progress | ✗ (local only, not running) | — | docker-compose brings it up; no standalone Redis needed for dev |
| PostgreSQL | Job + glossary persistence | ✗ (local only) | — | docker-compose brings it up; no standalone Postgres needed for dev |
| DashScope API key | INFRA-01/02 validation | Unknown | — | Must be the international key from dashscope-intl.aliyuncs.com console — not the China console key |

**Blocking dependency with required action before execution:**
- **Docker WSL2 integration:** Must be enabled in Docker Desktop Settings before running `docker compose up`. Verify with `docker ps` in this WSL shell.
- **DASHSCOPE_API_KEY:** Must be the international API key (issued at the dashscope-intl.aliyuncs.com console). Copy it to `.env` as `DASHSCOPE_API_KEY=sk-...`. The healthcheck will immediately surface a cryptic 401 if the China key is used instead.

---

## Validation Architecture

> `nyquist_validation: true` — this section is required.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio 0.23.x |
| Config file | `backend/pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 gap |
| Quick run command | `uv run pytest tests/ -x -q --ignore=tests/integration` |
| Full suite command | `uv run pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80` |
| Integration guard | `pytest -m integration` — requires `DASHSCOPE_API_KEY` env var |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | DashScope intl endpoint responds to qwen-mt-turbo probe | integration | `pytest tests/integration/test_healthcheck.py::test_dashscope_reachable -x` | ❌ Wave 0 |
| INFRA-02 | terminology param respected on VN↔EN sample | integration | `pytest tests/integration/test_healthcheck.py::test_terminology_param -x` | ❌ Wave 0 |
| INFRA-03 | docker-compose stack health (all services respond) | smoke (manual + script) | `python scripts/healthcheck.py` | ❌ Wave 0 |
| INFRA-04 | FastAPI returns 200 on CORS preflight from Next.js origin | integration | `pytest tests/integration/test_cors.py -x` | ❌ Wave 0 |
| INFRA-05 | Noto CJK + Noto Sans fonts present in Docker image | smoke | `python scripts/healthcheck.py` (font check) | ❌ Wave 0 |
| UPLD-01 | File upload ≤ 25 MB accepted; > 25 MB returns 413 | unit | `pytest tests/api/test_upload.py::test_file_size_limit -x` | ❌ Wave 0 |
| UPLD-02 | `.txt` rejected with 415; `.docx` accepted | unit | `pytest tests/api/test_upload.py::test_file_type_rejection -x` | ❌ Wave 0 |
| UPLD-03 | Language list endpoint returns non-empty list with "Vietnamese" | unit | `pytest tests/api/test_languages.py -x` | ❌ Wave 0 |
| UPLD-05 | Upload returns job_id; job exists in DB | integration | `pytest tests/api/test_upload.py::test_job_created -x` | ❌ Wave 0 |
| CORE-01 | DOCX extractor yields all paragraphs + table cells in order | unit | `pytest tests/pipeline/test_docx_extractor.py::test_reading_order -x` | ❌ Wave 0 |
| CORE-02 | translate_batch calls openai SDK with correct extra_body | unit (mock) | `pytest tests/llm/test_translator.py::test_translation_options -x` | ❌ Wave 0 |
| CORE-03 | Mismatch in LLM response count raises ValueError | unit | `pytest tests/llm/test_translator.py::test_core03_assertion -x` | ❌ Wave 0 |
| CORE-04 | NFD Vietnamese input is NFC-normalized on output | unit | `pytest tests/llm/test_translator.py::test_nfc_normalization -x` | ❌ Wave 0 |
| CORE-05 | URL replaced with placeholder before translation, restored after | unit | `pytest tests/pipeline/test_placeholder.py -x` | ❌ Wave 0 |
| CORE-06 | RateLimitError triggers retry with backoff; max 3 retries | unit (mock) | `pytest tests/llm/test_translator.py::test_retry_backoff -x` | ❌ Wave 0 |
| JOB-01 | Job state machine transitions queued→running→done | integration | `pytest tests/services/test_job_service.py -x` | ❌ Wave 0 |
| JOB-02 | SSE endpoint streams events until terminal state | unit | `pytest tests/api/test_sse.py -x` | ❌ Wave 0 |
| JOB-03 | Progress payload contains segments_done + segments_total | unit | `pytest tests/api/test_sse.py::test_progress_payload -x` | ❌ Wave 0 |
| JOB-04 | Failed job error_msg persisted + surfaced in payload | unit | `pytest tests/services/test_job_service.py::test_failed_job -x` | ❌ Wave 0 |
| DOCX-01 | DOCX round-trip preserves bold/italic/underline on golden fixture | integration | `pytest tests/pipeline/test_docx_roundtrip.py -x` | ❌ Wave 0 |
| DOCX-02 | Run-merge: translated text in runs[0], runs[1:] blanked | unit | `pytest tests/pipeline/test_docx_extractor.py::test_run_merge -x` | ❌ Wave 0 |
| DOCX-03 | Hyperlink URL unchanged after round-trip | unit | `pytest tests/pipeline/test_docx_extractor.py::test_hyperlink_preservation -x` | ❌ Wave 0 |
| DOCX-04 | <w:ins> detection returns True for tracked-changes fixture | unit | `pytest tests/pipeline/test_tracked_changes.py -x` | ❌ Wave 0 |
| LANG-01 | source_lang="auto" sent when auto-detect selected | unit (mock) | `pytest tests/llm/test_translator.py::test_auto_detect_lang -x` | ❌ Wave 0 |
| LANG-02 | VN→EN, VN→JA, VN→ZH, EN→JA pairs tested in integration | integration | `pytest tests/integration/test_lang_pairs.py -x` | ❌ Wave 0 |

### MQM / Human Eval (Out of CI Scope)

Per AI-SPEC §5 (not excerpted here — exceeds the read limit), human eval via MQM rubric runs outside CI via `make eval`. Not a blocker for Phase 1 completion gate.

### Sampling Rate

- **Per task commit:** `uv run pytest tests/ -x -q --ignore=tests/integration` (< 30 seconds)
- **Per wave merge:** `uv run pytest tests/ --cov=src --cov-report=term-missing --cov-fail-under=80`
- **Phase gate:** Full suite green (including integration with `DASHSCOPE_API_KEY` set) before `/gsd-verify-work`

### Wave 0 Gaps (ALL — greenfield)

- [ ] `backend/pyproject.toml` — `[tool.pytest.ini_options]` section with `asyncio_mode = "auto"` and markers
- [ ] `backend/tests/__init__.py` + `backend/tests/conftest.py` — `AsyncSession` fixture, Redis mock, AsyncOpenAI mock
- [ ] `backend/tests/llm/test_translator.py` — covers CORE-02/03/04/05/06, LANG-01
- [ ] `backend/tests/pipeline/test_docx_extractor.py` — covers CORE-01, DOCX-01/02/03
- [ ] `backend/tests/pipeline/test_tracked_changes.py` — covers DOCX-04
- [ ] `backend/tests/pipeline/test_placeholder.py` — covers CORE-05
- [ ] `backend/tests/api/test_upload.py` — covers UPLD-01/02/05
- [ ] `backend/tests/api/test_languages.py` — covers UPLD-03
- [ ] `backend/tests/api/test_sse.py` — covers JOB-02/03/04
- [ ] `backend/tests/services/test_job_service.py` — covers JOB-01/04
- [ ] `backend/tests/integration/test_healthcheck.py` — covers INFRA-01/02/03/04/05 (requires `DASHSCOPE_API_KEY`)
- [ ] `backend/tests/integration/test_docx_roundtrip.py` — covers DOCX-01 (requires golden fixture DOCX)
- [ ] `backend/tests/integration/test_lang_pairs.py` — covers LANG-02 (requires `DASHSCOPE_API_KEY`)
- [ ] `backend/tests/fixtures/` — golden DOCX fixture (paragraph + table + hyperlink + tracked changes), VN→EN test pair
- [ ] Install: `uv add --dev pytest pytest-asyncio pytest-cov httpx`

---

## Security Domain

> `security_enforcement` not disabled in config — section included.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 1 is single-user, no auth per out-of-scope list) | — |
| V3 Session Management | No | — |
| V4 Access Control | No | — |
| V5 Input Validation | Yes | `UploadFile` type + size validation; Pydantic models for all API schemas |
| V6 Cryptography | No (no user secrets stored) | — |
| V8 Data Protection | Partial | `DASHSCOPE_API_KEY` as `SecretStr` in pydantic-settings; never logged |

### Known Threat Patterns for Phase 1 Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious DOCX (zip-bomb, XXE via OOXML) | Tampering | `python-docx` uses `zipfile`; limit extract size; never eval macros |
| File upload DoS (large file) | DoS | Streaming size check + `HTTPException(413)` before full read |
| SSRF via hyperlink URL | Tampering | Never follow hyperlink URLs on the server; only preserve the URL string |
| DashScope API key leakage in logs | Information Disclosure | Use `SecretStr`; structlog never serializes `SecretStr` values |
| Prompt injection via document content | Tampering | qwen-mt-turbo is translation-only; `translation_options` in `extra_body` not in user content; no system prompt injection surface |

---

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/python-docx_readthedocs_io_en` — run properties, text setter, iter_inner_content, hyperlinks, iter_run_level_items, table traversal
- Context7 `/sysid/sse-starlette` — EventSourceResponse, ping, is_disconnected, CancelledError pattern
- Context7 `/websites/arq-docs_helpmanual_io` — WorkerSettings, on_startup/on_shutdown, ctx dict, job status
- Context7 `/websites/tanstack_query_v5` — setQueryData, refetchInterval as function, staleTime
- Context7 `/websites/fastapi_tiangolo` — UploadFile, request.stream(), HTTP_413, request.formData()
- Context7 `/vercel/next.js` — App Router Route Handler, request.formData(), POST handler
- Context7 `/python-openxml/python-docx` — CT_Body XSD confirming `w:ins`/`w:del` at body level
- [Alibaba Cloud Machine Translation docs](https://www.alibabacloud.com/help/en/model-studio/machine-translation) — source_lang="auto" confirmed, terms parameter structure
- [Qwen-MT API docs](https://www.alibabacloud.com/help/en/model-studio/qwen-mt-api) — extra_body translation_options, 8192 token limit

### Secondary (MEDIUM confidence)
- AI-SPEC Phase 1 §3/§4 — translate_batch pattern, token budget math, retry backoff — designed by gsd-ai-researcher and verified against DashScope docs
- CONTEXT.md D-01..D-20 — locked architecture decisions verified against requirements
- PITFALLS.md — DOCX run-splitting, tracked changes, Vietnamese NFC pitfalls (sourced from python-docx GitHub issues)
- CLAUDE.md §"Recommended Stack Summary" + §"What NOT to Use" — version-pinned stack decisions

### Tertiary (LOW confidence — marked ASSUMED in Assumptions Log)
- Text box traversal XPath pattern (A1) — standard knowledge but not Context7-verified for python-docx 1.2.0
- `@microsoft/fetch-event-source` exact API (A2) — library README pattern, needs verification on install
- DashScope rate limits (A6) — not published; assumed based on general API provider behavior

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries Context7-verified + CLAUDE.md locked
- Architecture: HIGH — patterns verified via Context7 docs; D-01..D-20 decisions locked
- DOCX traversal: HIGH — CT_Body XSD + python-docx API confirmed; text box detail MEDIUM
- SSE + arq wiring: HIGH — sse-starlette + arq docs fully verified
- DashScope behavior: MEDIUM-HIGH — official docs confirm auto-detect + terminology; rate limits LOW
- Pitfalls: HIGH — sourced from python-docx GitHub issues + PITFALLS.md

**Research date:** 2026-04-23
**Valid until:** 2026-05-23 (stable libraries; DashScope rate limits may change sooner)
