<!-- GSD:project-start source:PROJECT.md -->
## Project

**AI Translation PoC**

A web-based AI document translation PoC that takes office documents (DOCX, PDF, PPTX) in any language pair and returns translated versions that preserve the original format as closely as the format allows. Built as an internal demo for the **AICore** team (an AI-native startup) to evaluate whether Qwen-class LLMs plus layout-aware processing can beat commodity document translation tools (Azure Translator, DeepL, Google Docs translate) on quality, terminology control, and UX.

**Core Value:** **Translate documents with format fidelity that makes the translated output usable as-is** — without forcing reviewers to re-create layouts. Everything else (UX polish, glossary features, multi-format scope) is secondary to this.

### Constraints

- **Timeline**: 2–3 weeks from kickoff to demo — drives aggressive scoping and "hero format first" prioritization.
- **Tech stack (model)**: `qwen-mt-turbo` on Alibaba DashScope (international endpoint), accessed via the `openai` Python SDK against the OpenAI-compatible base URL. Glossary uses the native `terminology` API parameter.
- **Tech stack (backend)**: Python / FastAPI assumed — matches Thu's existing production stack and keeps cognitive overhead low. Async patterns for long-running translation jobs.
- **Tech stack (frontend)**: Next.js (React) assumed — matches ICOM-P3 frontend; fastest path to a demo-quality UI.
- **Audience**: Internal AICore team. No external users, no data-residency contract — but Qwen API routes through Alibaba Cloud; flag if AICore has concerns about that.
- **Deployment**: Internal web app (docker-compose or single VM) is sufficient for the PoC demo.
- **Quality bar**: "Readable + high fidelity + pixel-perfect" was the user's stated aspiration — the realistic per-format bars are documented in `## Context` above. We will not promise pixel-perfect on scanned PDFs.
- **Languages**: Multi-lingual — pair is user-selected per job, not hardcoded. Vietnamese, English, Japanese, Chinese must all work well given AICore's target market.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## 1. Qwen Model Selection
### Verified DashScope Catalog (2026-04-17)
| Model ID | Context Window | Input (Intl) | Output (Intl) | Recommended Use |
|----------|---------------|-------------|--------------|-----------------|
| `qwen-mt-turbo` | 1M tokens | $0.16/1M | $0.49/1M | PRIMARY — purpose-built for translation |
| `qwen-mt-plus` | 1M tokens | $2.46/1M | $7.37/1M | FALLBACK — highest quality for critical docs |
| `qwen3.5-plus` (alias: `qwen-plus-latest`) | 1M tokens | $0.40/1M | $2.40/1M | FALLBACK if MT models unavailable |
| `qwen3-max` | 262K tokens | $1.20/1M | $6.00/1M | Never use for bulk translation — cost prohibitive |
### Recommendation
## 2. DashScope SDK vs OpenAI-Compatible Endpoint
### Recommendation: OpenAI-compatible endpoint + `openai` Python SDK
- The `openai` SDK is already in Thu's stack (ICOM-P3 on Azure OpenAI). Zero new SDK to learn.
- The `dashscope` Python SDK has a separate async API surface that is less mature than `openai`'s native async support.
- The compatible endpoint supports `extra_body` for qwen-mt-turbo's `terminology` parameter, enabling native glossary injection.
- Easier to swap to Azure OpenAI or AWS Bedrock in a future PoC iteration.
## 3. OOXML Processing
### DOCX: python-docx 1.2.0
### PPTX: python-pptx 1.0.2
## 4. Native PDF Translation
### Recommendation: PyMuPDF 1.26.x (primary) + pdf2docx 0.5.x (round-trip alternative)
- **Font mismatch** — Original embedded fonts are not re-usable. Must bundle substitute fonts (see Section 10). For CJK/VN, embed Noto Sans CJK or similar.
- **Text expansion overflow** — `page.insert_textbox()` returns negative if text overflows the rect. Must detect and either shrink font or flag for review.
- **Complex scripts** — For right-to-left languages (Arabic, Hebrew), use `page.insert_htmlbox()` instead of `page.insert_textbox()` to preserve shaping. Vietnamese is LTR so `insert_textbox` works.
- **Multi-column layouts** — Block extraction order may not match reading order. Use `sort=True` in `get_text()` for reading-order sorting.
| Tool | Layout fidelity | Speed | CJK/VN font | Round-trip |
|------|---------------|-------|-------------|-----------|
| PyMuPDF | HIGH (direct) | Very fast | Requires bundled fonts | No |
| pdfplumber | MEDIUM (extraction only, no write) | Medium | N/A | N/A |
| pdf2docx | MEDIUM | Slow | Inherited from LibreOffice | Yes |
| pypdfium2 | HIGH (extraction) | Very fast | No write API | No |
## 5. OCR for Scanned PDFs
### Recommendation: PaddleOCR 3.x (PP-OCRv5) as default; Azure Document Intelligence as cloud alternative
- Supports 106 languages including Vietnamese, Japanese, Chinese (Simplified + Traditional), English in a single model.
- PP-OCRv5 (PaddleOCR 3.0, released 2025) achieves +13 percentage points over PP-OCRv4 on complex doc benchmarks; +30% improvement for multilingual text recognition vs PP-OCRv3.
- Self-hostable, zero per-page cost, GPU-accelerated inference available.
- The PP-StructureV3 pipeline handles layout analysis (reading order, tables, figures) — critical for producing usable OCR output.
- Vietnamese: Covered by the `latin` or `ch` model (PaddleOCR treats VN as Latin-script). PP-OCRv5 includes VN in its multilingual pack.
- Japanese/Chinese: Native support in `ch` model (covers CJK). PP-OCRv5 shows 13+ point improvement for Japanese detection vs v4.
- Mixed-language docs: Use `ch` model which handles CJK + Latin mixed content.
- Read model supports VN, JA, ZH, EN with high accuracy on real-world scanned docs.
- $1.50/1000 pages for standard Read (free tier: 500 pages/month).
- Returns JSON with bounding boxes, reading order, table structure — easier to post-process.
- Data routed through Azure: acceptable for internal AICore PoC; flag if AICore has data residency concerns.
| OCR Engine | VN quality | JA/ZH quality | Self-host | Cost | Ease | Verdict |
|-----------|-----------|--------------|---------|------|------|---------|
| PaddleOCR PP-OCRv5 | HIGH | HIGH | Yes | Free | Medium | **Recommended default** |
| Azure Document Intelligence | HIGH | HIGH | No | $1.50/1K pp | Easy | Cloud fallback |
| Tesseract 5 + pytesseract | MEDIUM | MEDIUM (JA poor) | Yes | Free | Easy | Not recommended for JA |
| Google Document AI | HIGH | HIGH | No | $1.50/1K pp | Easy | Alternative to Azure |
| Alibaba OCR (DashScope) | HIGH (CN-biased) | HIGH | No | Varies | Medium | DashScope ecosystem bonus |
## 6. Glossary / Terminology Injection
### Recommendation: Native qwen-mt-turbo `terminology` parameter + prompt-level fallback
## 7. FastAPI + Next.js for Long-Running Jobs
### File Upload Handling
### Background Job Queue: arq 0.26.x + Redis
- Thu's stack is already async-first (FastAPI, asyncio, async SQLAlchemy). arq workers run in the same asyncio event loop — no sync/async bridge needed.
- arq is significantly lighter than Celery: no separate Beat process, no broker config complexity, single Redis dependency already in Thu's existing stack.
- arq v0.27 supports job result retrieval and status polling natively via `job.result()` and `job.status()`.
- Celery's async support (via `celery[async]`) is bolted on and less clean.
# worker.py
### Job Status: SSE (Server-Sent Events)
- SSE is simpler than WebSockets (one-directional push, no upgrade dance).
- FastAPI 0.135+ has native SSE support via `EventSourceResponse` (no external lib needed).
- The client uses `@microsoft/fetch-event-source` (npm) since native `EventSource` does not support custom headers.
- Pattern: client connects to `/jobs/{job_id}/stream` on upload, SSE endpoint polls Redis/DB every 1s and pushes `{status, progress_pct, message}` events until terminal state.
### Side-by-Side Review UI
- For the PoC, render translated text as plain text in the diff panel (not the formatted document). Full WYSIWYG document diff is out of PoC scope.
- Allow inline edits in the right pane before export.
- `@monaco-editor/react` works with Next.js without any webpack config — load with `dynamic(() => import(...), { ssr: false })` since Monaco requires browser APIs.
- `react-diff-viewer` — simpler but text-only, no editing capability.
- iframe-based document preview — requires WASM PDF renderer (complex for PoC).
## 8. File Storage
### Recommendation: Local filesystem for Phase 1; MinIO (Docker) for Phase 2+
## 9. Database
### Recommendation: PostgreSQL 16 + SQLAlchemy 2.0 async + asyncpg + Alembic
- arq uses Redis for job queue, but job metadata (status, file paths, glossaries, language pairs, timestamps, output paths) needs a relational DB.
- SQLite has write serialization — only one writer at a time. With concurrent translation jobs each updating status, this becomes a bottleneck.
- Thu already runs PostgreSQL in both production projects (scala-i-ask, ICOM-P3) — no new operational knowledge needed.
- Docker Compose makes local PostgreSQL trivial to run.
- asyncpg is the fastest async PostgreSQL driver in Python (binary protocol).
- `SQLAlchemy 2.0` + `asyncpg` driver (`postgresql+asyncpg://`)
- `SQLModel` 0.0.21+ (SQLAlchemy 2.0 + Pydantic v2 integration) — appropriate if Thu wants Pydantic models to double as ORM models
- Alternatively, raw SQLAlchemy 2.0 async with separate Pydantic schemas (clearer separation)
- `Alembic` for migrations
- `jobs` table: id, status, source_lang, target_lang, input_path, output_path, created_at, updated_at, error_msg
- `glossaries` table: id, name, terms (JSONB), created_at
- `job_glossaries` join table
## 10. Font Handling for CJK + Vietnamese PDFs
### Recommendation: Bundle Noto fonts; use PyMuPDF font embedding
| Font | Coverage | Size | Source |
|------|---------|------|--------|
| `NotoSansCJK-Regular.ttc` | Japanese, Chinese (SC/TC), Korean | ~48MB | noto-cjk GitHub |
| `NotoSans-Regular.ttf` | Vietnamese + Latin | ~500KB | Google Fonts / noto-fonts |
| `NotoSerif-Regular.ttf` | Serif variant for body text | ~500KB | Google Fonts |
# Register bundled font for text insertion
- `NotoSansCJK-Regular.ttc` is ~48MB — increases Docker image size. Accept this for correctness.
- Font metrics differ from original PDF fonts — line heights and character widths will not match exactly. This is unavoidable without the original font license.
- For scanned PDFs (OCR output), use a clean Noto Sans layout — the original font is unknowable anyway.
## Recommended Stack Summary
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 | Runtime | Latest stable; asyncio improvements |
| FastAPI | 0.115+ | API framework | Already in Thu's stack; native async |
| Next.js | 15 (App Router) | Frontend | Already in Thu's stack (ICOM-P3) |
| PostgreSQL | 16 | Job + glossary DB | Already in Thu's stack; JSONB for terms |
| Redis | 7 | arq queue broker | Already in Thu's stack |
| Docker Compose | 2.x | Local orchestration | Single-machine PoC deployment |
### AI / Translation
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `qwen-mt-turbo` (DashScope) | — | Primary translation engine | Translation-specialized, 92 languages, cheapest Qwen tier |
| `qwen-mt-plus` (DashScope) | — | High-quality fallback | Same as turbo but higher quality tier |
| openai SDK | 1.x | DashScope client | OpenAI-compatible endpoint; Thu already uses it |
### Document Processing
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| python-docx | 1.2.0 | DOCX read/write | Run-level text replacement |
| python-pptx | 1.0.2 | PPTX read/write | Shape/table/notes traversal |
| PyMuPDF (pymupdf) | 1.26.x | PDF extraction + reinsertion | Redact-and-reinsert pattern |
| pdf2docx | 0.5.8 | Complex PDF → DOCX round-trip | Fallback for column-heavy layouts |
| PaddleOCR | 3.x (PP-OCRv5) | Scanned PDF OCR | Best OSS multilingual quality |
### Backend Infrastructure
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| arq | 0.27.0 | Async job queue | Maintenance mode but stable; asyncio-native |
| SQLAlchemy | 2.0.x | Async ORM | With asyncpg driver |
| asyncpg | 0.30.x | PostgreSQL async driver | Fastest binary-protocol driver |
| Alembic | 1.x | DB migrations | Standard with SQLAlchemy |
| sse-starlette | 3.3.4 | SSE job status streaming | Or FastAPI 0.135+ built-in |
| pydantic-settings | 2.x | Config from env | SecretStr for API keys |
| uv | — | Package management | Per Thu's global preference |
### Frontend
| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| @monaco-editor/react | 4.x | Side-by-side diff + edit UI | DiffEditor component; CJK-safe |
| @microsoft/fetch-event-source | 2.x | SSE client with auth headers | EventSource substitute |
| TanStack Query | 5.x | Server state management | Job status polling + SSE |
### Fonts (Docker image)
| Asset | Purpose | Install |
|-------|---------|---------|
| fonts-noto-cjk | JA/ZH PDF text insertion | `apt-get install fonts-noto-cjk` |
| fonts-noto | VN/Latin PDF text insertion | `apt-get install fonts-noto` |
## Alternatives Considered
| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| `qwen-mt-turbo` | `qwen3.5-plus` | qwen-mt-turbo is specialized for translation; cheaper; native terminology API |
| openai SDK + compatible endpoint | `dashscope` SDK | openai SDK already in Thu's stack; richer ecosystem |
| PaddleOCR PP-OCRv5 | Tesseract 5 | Tesseract's Japanese model is materially weaker; no native layout analysis |
| arq + Redis | Celery + Redis | Celery's async support is a bolt-on; arq is asyncio-native |
| arq + Redis | FastAPI BackgroundTasks | BackgroundTasks has no persistence, no status polling, no retry |
| PostgreSQL | SQLite | SQLite write serialization bottlenecks concurrent job updates |
| PyMuPDF (direct reinsertion) | pdfplumber | pdfplumber has no text write API; extraction only |
| Local FS → MinIO | AWS S3 | Adds cloud cost + IAM config for an internal PoC |
| Monaco DiffEditor | react-diff-viewer | react-diff-viewer is read-only; Monaco enables inline editing before export |
| LibreOffice headless | docx2pdf (Windows COM) | COM automation requires Windows; LibreOffice works on Linux Docker |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `qwen3-max` for bulk translation | $6/1M output tokens — 10x the cost of qwen-mt-turbo for inferior translation quality | `qwen-mt-turbo` |
| `qwen-turbo` (old) | Explicitly deprecated by Alibaba; migrate to `qwen-flash` per docs | `qwen-mt-turbo` or `qwen3.5-flash` |
| `paragraph.text = value` in python-docx | Destroys all run-level formatting (bold, italic, font, color) | Overwrite `run.text` with translated value in first run, blank remaining runs |
| Tesseract for Japanese | Weak JA model; no layout analysis | PaddleOCR PP-OCRv5 |
| FastAPI `BackgroundTasks` for translation jobs | No persistence, no status API, dies on restart | arq + Redis |
| `dashscope` SDK | Less mature async, breaks OpenAI ecosystem tooling | openai SDK with compatible base_url |
| `pdf2docx` as primary path | Abandoned by Artifex; community-maintained; 2-step fidelity loss | PyMuPDF direct reinsertion |
| ReportLab for CJK PDF generation | Poor CJK support; requires manual glyph registration | PyMuPDF with bundled Noto fonts |
| Embedding fonts from original PDF | Legally and technically not allowed; fonts are DRM-protected | Bundle Noto Sans CJK as substitute |
## Installation (uv)
# Backend core
# Translation + LLM
# Document processing
# Async infrastructure
# Job status streaming
# Frontend (in /frontend)
# Fonts (Dockerfile)
# RUN apt-get install -y fonts-noto-cjk fonts-noto && fc-cache -f
## Version Compatibility Notes
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| python-docx 1.2.0 | python 3.8–3.13 | No breaking change from 1.1.x |
| python-pptx 1.0.2 | python 3.8–3.13 | 1.0.x has breaking changes from 0.6.x — don't downgrade |
| PyMuPDF 1.26.x | python 3.10–3.14 | Requires `PyMuPDFb` wheel (auto-installed by pip) |
| arq 0.27.0 | python 3.9–3.11 officially | 3.12 works in practice; verify before pinning |
| SQLAlchemy 2.0 | asyncpg 0.29+ | Use `postgresql+asyncpg://` DSN |
| PaddleOCR 3.x | paddlepaddle 3.0+ | Must match paddle version exactly |
| openai 1.x | python 3.8+ | DashScope compatible mode confirmed |
## Sources
- Alibaba Cloud Model Studio — Live model catalog: https://www.alibabacloud.com/help/en/model-studio/models
- Alibaba Cloud DashScope billing: https://www.alibabacloud.com/help/en/model-studio/billing-for-model-studio
- Alibaba Cloud OpenAI compatibility docs: https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope
- Qwen-MT official blog: https://qwenlm.github.io/blog/qwen-mt/
- PyMuPDF official docs (Context7 verified): https://pymupdf.readthedocs.io/en/latest/
- python-docx 1.2.0 docs (Context7 verified): https://python-docx.readthedocs.io/
- python-pptx 1.0.2 docs (Context7 verified): https://python-pptx.readthedocs.io/
- PaddleOCR PP-OCRv5 technical report: https://arxiv.org/abs/2507.05595
- arq PyPI: https://pypi.org/project/arq/
- sse-starlette PyPI: https://pypi.org/project/sse-starlette/
- FastAPI SSE docs: https://fastapi.tiangolo.com/tutorial/server-sent-events/
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
