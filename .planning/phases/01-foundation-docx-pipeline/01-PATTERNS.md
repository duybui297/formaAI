# Phase 1: Foundation + DOCX Pipeline — Pattern Map

**Mapped:** 2026-04-23
**Files analyzed:** 52 new files (backend) + 15 new files (frontend) = 67 total
**Analogs found:** 0 exact codebase matches (greenfield) / 67 total
**Pattern source:** All patterns sourced from 01-AI-SPEC.md, 01-RESEARCH.md, and CLAUDE.md in-project specs since no src/ tree exists yet.

---

## Greenfield Note

This is a greenfield project — no `src/` tree exists. Every analog reference below points to a concrete code excerpt inside `01-AI-SPEC.md` or `01-RESEARCH.md` by section name and topic, which ARE the canonical patterns. The column "Match Quality" reflects how complete and verified the pattern excerpt is.

---

## File Classification

### Backend (Python / FastAPI)

| New File | Role | Data Flow | Pattern Source | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/pyproject.toml` | config | — | CLAUDE.md §"Installation (uv)" + AI-SPEC §3 uv commands | config-template |
| `backend/Dockerfile` | config/infra | — | RESEARCH.md §12 Dockerfile fragment | exact |
| `docker-compose.yml` | config/infra | — | CONTEXT.md D-03 topology; align with Thu's ICOM-P3 compose pattern | reference |
| `.env.example` | config | — | CONTEXT.md D-04 file layout + Security section | reference |
| `backend/src/app/main.py` | config/app-entry | request-response | RESEARCH.md §7 lifespan snippet | exact |
| `backend/src/app/core/config.py` | config | — | AI-SPEC §4 `make_llm_client(settings: Settings)` + CLAUDE.md pydantic-settings | exact |
| `backend/src/app/core/logging.py` | utility | — | CONTEXT.md D-19 structlog JSON + job_id binding | reference |
| `backend/src/app/core/telemetry.py` | utility | — | AI-SPEC §5 Arize Phoenix setup excerpt | exact |
| `backend/src/app/db/models.py` | model | CRUD | CONTEXT.md D-04 jobs/glossaries schema description | reference |
| `backend/src/app/db/session.py` | config | — | RESEARCH.md §6 `create_async_engine` + `async_sessionmaker` startup snippet | exact |
| `backend/src/app/db/migrations/` | migration | — | Alembic standard; align with Thu's scala-i-ask migration patterns | reference |
| `backend/src/app/llm/client.py` | utility | — | AI-SPEC §4 `make_llm_client` excerpt | exact |
| `backend/src/app/llm/translator.py` | service | request-response | AI-SPEC §3 `translate_batch` full excerpt | exact |
| `backend/src/app/llm/terminology.py` | utility/transform | transform | AI-SPEC §3 `translation_options["terms"]` pattern + §4b.3 table | exact |
| `backend/src/app/llm/token_budget.py` | utility | batch | AI-SPEC §4 `estimate_tokens` + `pack_into_batches` excerpt | exact |
| `backend/src/app/llm/schemas.py` | schema | — | AI-SPEC §4b.1 `TranslateBatchRequest/Response` + `assert_segment_count` | exact |
| `backend/src/app/pipeline/segment.py` | model | — | CONTEXT.md D-05/D-06 Segment tree + SHA ID; RESEARCH.md code examples §"Segment ID Generation" | exact |
| `backend/src/app/pipeline/placeholder.py` | utility | transform | RESEARCH.md §5 `extract_placeholders` / `restore_placeholders` full excerpt | exact |
| `backend/src/app/pipeline/docx/extractor.py` | service | file-I/O | RESEARCH.md §4 `walk_document` + `_walk_body` + `_walk_table` full excerpt | exact |
| `backend/src/app/pipeline/docx/reassembler.py` | service | file-I/O | RESEARCH.md §4 run-merge pattern + `write_translated_paragraph` excerpt | exact |
| `backend/src/app/pipeline/docx/tracked.py` | utility | file-I/O | RESEARCH.md §4 `has_tracked_changes` + strip/preserve strategy | exact |
| `backend/src/app/services/job_service.py` | service | CRUD | RESEARCH.md §6 job state machine + transitions | exact |
| `backend/src/app/workers/translate_worker.py` | worker | event-driven | RESEARCH.md §6 full `startup/shutdown/translate_job/WorkerSettings` excerpt | exact |
| `backend/src/app/api/upload.py` | controller | request-response | RESEARCH.md §8 streaming size check + MIME validation | exact |
| `backend/src/app/api/jobs.py` | controller | request-response + SSE | RESEARCH.md §7 `stream_job_progress` + `EventSourceResponse` | exact |
| `backend/src/app/api/health.py` | controller | request-response | Standard FastAPI health endpoint pattern | reference |
| `scripts/healthcheck.py` | utility/script | — | CONTEXT.md D-18 checklist items; RESEARCH.md §11 quirks | reference |
| `Makefile` | config | — | AI-SPEC §5 `test-unit` / `test-integration` / `eval` targets | exact |

### Backend Tests

| New File | Role | Data Flow | Pattern Source | Match Quality |
|----------|------|-----------|----------------|---------------|
| `backend/tests/conftest.py` | test | — | RESEARCH.md §Validation Wave 0 Gaps: `AsyncSession` fixture, Redis mock, AsyncOpenAI mock | reference |
| `backend/tests/llm/test_translator.py` | test | — | RESEARCH.md §Validation test map: CORE-02/03/04/05/06, LANG-01 | exact |
| `backend/tests/pipeline/test_docx_extractor.py` | test | — | RESEARCH.md §Validation test map: CORE-01, DOCX-01/02/03 | exact |
| `backend/tests/pipeline/test_tracked_changes.py` | test | — | RESEARCH.md §Validation test map: DOCX-04 | exact |
| `backend/tests/pipeline/test_placeholder.py` | test | — | RESEARCH.md §Validation test map: CORE-05 | exact |
| `backend/tests/api/test_upload.py` | test | — | RESEARCH.md §Validation test map: UPLD-01/02/05 | exact |
| `backend/tests/api/test_languages.py` | test | — | RESEARCH.md §Validation test map: UPLD-03 | exact |
| `backend/tests/api/test_sse.py` | test | — | RESEARCH.md §Validation test map: JOB-02/03/04 | exact |
| `backend/tests/services/test_job_service.py` | test | — | RESEARCH.md §Validation test map: JOB-01/04 | exact |
| `backend/tests/integration/test_healthcheck.py` | test | — | RESEARCH.md §Validation test map: INFRA-01..05 | exact |
| `backend/tests/integration/test_docx_roundtrip.py` | test | — | RESEARCH.md §Validation test map: DOCX-01 | exact |
| `backend/tests/integration/test_lang_pairs.py` | test | — | RESEARCH.md §Validation test map: LANG-02 | exact |

### Frontend (Next.js 16 App Router)

| New File | Role | Data Flow | Pattern Source | Match Quality |
|----------|------|-----------|----------------|---------------|
| `frontend/package.json` | config | — | RESEARCH.md §Standard Stack install commands | exact |
| `frontend/next.config.mjs` | config | — | CONTEXT.md D-20 (Turbopack default, no webpack config) | reference |
| `frontend/src/app/layout.tsx` | component | — | RESEARCH.md §9 App Router; QueryClientProvider wrap | reference |
| `frontend/src/app/page.tsx` | component | request-response | Standard redirect to /upload | reference |
| `frontend/src/app/upload/page.tsx` | component | request-response | UI-SPEC drop zone + RESEARCH.md §9 formData pattern | exact |
| `frontend/src/app/jobs/[id]/page.tsx` | component | SSE + request-response | RESEARCH.md §7 `useJobProgress` hook + UI-SPEC status page | exact |
| `frontend/src/app/api/upload/route.ts` | controller | request-response | RESEARCH.md §9 `POST route.ts` full excerpt | exact |
| `frontend/src/hooks/useJobProgress.ts` | hook | SSE + polling | RESEARCH.md §7 `useJobProgress` full TypeScript excerpt | exact |
| `frontend/src/components/UploadForm.tsx` | component | request-response | UI-SPEC upload form contract + shadcn Dialog/Button | reference |
| `frontend/src/components/LanguageSelect.tsx` | component | request-response | UI-SPEC language picker + shadcn Select | reference |
| `frontend/src/components/ProgressBar.tsx` | component | SSE-driven | UI-SPEC progress bar (indigo-500 fill, 8px height) + shadcn Progress | reference |
| `frontend/src/lib/types.ts` | utility | — | RESEARCH.md §7 `JobProgress` interface | exact |

---

## Pattern Assignments

### `backend/src/app/llm/client.py` (utility, singleton factory)

**Pattern Source:** AI-SPEC §4 "Core Pattern" — `make_llm_client`

**Imports + core pattern** (AI-SPEC §4, lines starting at "# app/llm/client.py"):
```python
import os
from openai import AsyncOpenAI
from app.core.config import Settings

def make_llm_client(settings: Settings) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key.get_secret_value(),
        base_url=str(settings.dashscope_base_url),
        max_retries=0,   # CORE-06 retry is in the worker, not the SDK
        timeout=60.0,
    )
```

**Key constraints:**
- `max_retries=0` always — SDK-level retry is disabled; CORE-06 in worker owns retry logic
- `base_url` must point at `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` (not China endpoint)
- Client is created ONCE at worker startup and stored in `ctx["llm_client"]` — never per-call
- Sync `OpenAI` client is only for scripts/healthchecks — never use inside arq or FastAPI handlers

---

### `backend/src/app/llm/translator.py` (service, request-response)

**Pattern Source:** AI-SPEC §3 `translate_batch` full excerpt + §4b.1 Pydantic schemas

**Imports pattern** (AI-SPEC §3):
```python
import unicodedata
import asyncio
from typing import Sequence
from openai import AsyncOpenAI, RateLimitError, APIStatusError
```

**Core pattern — `translate_batch`** (AI-SPEC §3, full function):
```python
async def translate_batch(
    client: AsyncOpenAI,
    segments: Sequence[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None = None,
    model: str = "qwen-mt-turbo",
) -> list[str]:
    # CORE-04: NFC-normalise input
    nfc = lambda s: unicodedata.normalize("NFC", s)
    normalised = [nfc(seg) for seg in segments]

    # CORE-05: whitespace-only/digit-only passthrough stubs
    passthrough_indices: set[int] = set()
    payload_segments: list[str] = []
    for i, seg in enumerate(normalised):
        stripped = seg.strip()
        if not stripped or stripped.isdigit():
            passthrough_indices.add(i)
            payload_segments.append(f"⟦T{i}⟧")
        else:
            payload_segments.append(seg)

    user_content = "\n".join(payload_segments)

    translation_options: dict = {"source_lang": source_lang, "target_lang": target_lang}
    if glossary:
        translation_options["terms"] = [
            {"source": src, "target": tgt} for src, tgt in glossary.items()
        ]

    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": user_content}],
        extra_body={"translation_options": translation_options},
        # Do NOT pass temperature — qwen-mt-turbo does not support it
    )

    raw_output = response.choices[0].message.content or ""
    translated_lines = raw_output.split("\n")

    # CORE-03: segment count assertion
    if len(translated_lines) != len(payload_segments):
        raise ValueError(
            f"CORE-03 violation: sent {len(payload_segments)} segments, "
            f"received {len(translated_lines)} translated lines."
        )

    result: list[str] = []
    for i, (orig, translated) in enumerate(zip(normalised, translated_lines)):
        if i in passthrough_indices:
            result.append(orig)
        else:
            result.append(nfc(translated))   # CORE-04: NFC output

    return result
```

**Critical pitfalls to avoid:**
- NEVER add a system message (`{"role": "system", ...}`) — qwen-mt-turbo treats it as text to translate
- NEVER pass `temperature=` — not supported, may cause rejection
- NEVER use streaming — CORE-03 count assertion requires the full response
- `response.choices[0].message.content` can be `None` — always guard with `or ""`

---

### `backend/src/app/llm/token_budget.py` (utility, batch)

**Pattern Source:** AI-SPEC §4 "Context Window Strategy" excerpt

**Core pattern** (AI-SPEC §4):
```python
import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str) -> int:
    return len(_ENC.encode(text))

def pack_into_batches(
    segments: list[str],
    budget_tokens: int = 3000,
) -> list[list[str]]:
    batches: list[list[str]] = []
    current_batch: list[str] = []
    current_tokens: int = 0

    for seg in segments:
        seg_tokens = estimate_tokens(seg)
        if current_batch and (current_tokens + seg_tokens > budget_tokens):
            batches.append(current_batch)
            current_batch = [seg]
            current_tokens = seg_tokens
        else:
            current_batch.append(seg)
            current_tokens += seg_tokens

    if current_batch:
        batches.append(current_batch)

    return batches
```

**Edge case (D-08):** If `estimate_tokens(seg) > 7000`, raise `SegmentTooLargeError` with segment_id and token count. Never sentence-split.

---

### `backend/src/app/llm/schemas.py` (schema)

**Pattern Source:** AI-SPEC §4b.1 "Structured Outputs with Pydantic"

**Core pattern** (AI-SPEC §4b.1):
```python
from __future__ import annotations
from pydantic import BaseModel, Field, model_validator

class TranslateBatchRequest(BaseModel, frozen=True):
    segments: list[str] = Field(..., min_length=1)
    source_lang: str
    target_lang: str
    glossary: dict[str, str] | None = None
    model: str = "qwen-mt-turbo"

class TranslateBatchResponse(BaseModel, frozen=True):
    segments: list[str]
    usage: TokenUsage

    @model_validator(mode="after")
    def _validate_non_empty(self) -> "TranslateBatchResponse":
        if not self.segments:
            raise ValueError("TranslateBatchResponse.segments must be non-empty")
        return self

def assert_segment_count(request: TranslateBatchRequest, response: TranslateBatchResponse) -> None:
    if len(response.segments) != len(request.segments):
        raise ValueError(
            f"CORE-03 segment count mismatch: "
            f"expected={len(request.segments)}, got={len(response.segments)}"
        )
```

---

### `backend/src/app/workers/translate_worker.py` (worker, event-driven)

**Pattern Source:** RESEARCH.md §6 full worker excerpt + AI-SPEC §4 retry wrapper + §4b.2 `asyncio.gather` pattern

**Lifecycle pattern** (RESEARCH.md §6):
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from redis.asyncio import Redis
from app.llm.client import make_llm_client
from app.core.config import get_settings
import structlog

log = structlog.get_logger()

async def startup(ctx: dict) -> None:
    settings = get_settings()
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
    async with ctx["session_factory"]() as session:
        log.bind(job_id=job_id)
        await _run_translation(ctx, session, job_id)

class WorkerSettings:
    functions = [translate_job]   # MUST be direct references, not strings (Pitfall #5)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
```

**CORE-06 retry wrapper** (AI-SPEC §4):
```python
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0   # sleep = base ** attempt → 2s, 4s, 8s

async def translate_batch_with_retry(ctx, segments, source_lang, target_lang, glossary, job_id, batch_id):
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return await translate_batch(client=ctx["llm_client"], ...)
        except RateLimitError as exc:
            last_exc = exc
            await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
        except APIStatusError as exc:
            if exc.status_code < 500:
                raise   # 4xx except 429 — do not retry
            last_exc = exc
            await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
        except APIConnectionError as exc:
            last_exc = exc
            await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
    raise RuntimeError(f"All {_MAX_RETRIES} retries exhausted") from last_exc
```

**Concurrent batch execution** (AI-SPEC §4b.2):
```python
sem = asyncio.Semaphore(4)   # D-17: cap 4 concurrent DashScope calls per job

async def translate_all_batches(ctx, batches, source_lang, target_lang, glossary, job_id):
    async def _call(batch_id, batch):
        async with sem:
            return await translate_batch_with_retry(ctx=ctx, segments=batch, ...)
    return list(await asyncio.gather(*[_call(i, b) for i, b in enumerate(batches)]))
```

**Progress publish** (RESEARCH.md §6):
```python
import json
payload = {
    "status": "running", "stage": "translate",
    "segments_done": 47, "segments_total": 210,
    "current_batch": 5, "retry_count": 0,
    "last_message": "Translating batch 5/23"
}
await redis.publish(f"job:{job_id}", json.dumps(payload))
```

---

### `backend/src/app/pipeline/docx/extractor.py` (service, file-I/O)

**Pattern Source:** RESEARCH.md §4 "Full Document Traversal Order"

**Core traversal pattern** (RESEARCH.md §4):
```python
from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table, _Cell

def walk_document(doc: Document):
    # 1. Body paragraphs + table cells (row-major)
    yield from _walk_body(doc)
    # 2. Headers and footers per section
    for section in doc.sections:
        for hf in [section.header, section.footer,
                   section.even_page_header, section.even_page_footer,
                   section.first_page_header, section.first_page_footer]:
            if hf is not None and hf.is_linked_to_previous is False:
                yield from _walk_body_element(hf._element)
    # 3. Comments — via doc.part._comments_part.element if present

def _walk_body(doc: Document):
    for block in doc.iter_inner_content():  # yields Paragraph | Table
        if isinstance(block, Paragraph):
            yield ("para", block)
        elif isinstance(block, Table):
            yield from _walk_table(block)

def _walk_table(table: Table):
    for row in table.rows:
        for cell in row.cells:
            for block in cell.iter_inner_content():  # NOT cell.paragraphs — misses nested tables
                if isinstance(block, Paragraph):
                    yield ("cell_para", block)
                elif isinstance(block, Table):
                    yield from _walk_table(block)
```

**Segment ID generation** (RESEARCH.md code examples):
```python
import hashlib

def make_segment_id(source_text: str, structural_position: str) -> str:
    payload = f"{source_text}\x00{structural_position}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

**Pitfalls to avoid:**
- `document.paragraphs` misses table cells, headers, footers (Pitfall #2)
- For hyperlinks: use `paragraph.iter_run_level_items()`, translate `hyperlink.runs` text but preserve `hyperlink.url` (Pitfall #8)
- NFC-normalize `run.text` at extraction time, before building Segment (Pitfall #7)

---

### `backend/src/app/pipeline/docx/reassembler.py` (service, file-I/O)

**Pattern Source:** RESEARCH.md §4 "Run-Merge Invariant" + code examples

**Core run-merge pattern** (RESEARCH.md §4 + code examples):
```python
import unicodedata

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def write_translated_paragraph(paragraph, translated_text: str) -> None:
    """
    DOCX-02: run-merge write-back. NEVER use paragraph.text = value.
    """
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(translated_text)
        return
    runs[0].text = nfc(translated_text)    # only touches <w:t>, preserves <w:rPr>
    for run in runs[1:]:
        run.text = ""                       # blank but do NOT remove the <w:r> element
```

**Why this pattern is mandatory (CLAUDE.md explicit anti-pattern):**
`paragraph.text = value` calls `paragraph.clear()` then `paragraph.add_run(text)` — ALL bold, italic, underline, font, color attributes are destroyed. The run-merge strategy writes only to `<w:t>` inside the existing `<w:r>` elements, leaving `<w:rPr>` intact.

---

### `backend/src/app/pipeline/docx/tracked.py` (utility, file-I/O)

**Pattern Source:** RESEARCH.md §4 "Tracked Changes Detection"

**Core pattern** (RESEARCH.md §4):
```python
from docx import Document

def has_tracked_changes(doc: Document) -> bool:
    """Detect <w:ins> or <w:del> in the document body XML."""
    body_xml = doc._element.xml
    return "<w:ins" in body_xml or "<w:del" in body_xml
```

**Strip strategy:** Walk `doc._element` with lxml; find `<w:ins>` elements, move their `<w:r>` children out, remove the `<w:ins>` wrapper; find `<w:del>` elements and remove entirely.

**Preserve strategy (D-14 for comments):** Walk both `<w:ins>` and `<w:del>` runs as Segments. Mark with `is_inserted=True` / `is_deleted=True` so the reassembler can wrap them back after translation.

**User choice modal (D-13):** Detect on upload, return `has_tracked_changes: bool` in upload response. Frontend shows Dialog with strip/preserve/cancel choices before `POST /jobs` is called.

---

### `backend/src/app/pipeline/placeholder.py` (utility, transform)

**Pattern Source:** RESEARCH.md §5 "CORE-05: Non-Translatable Placeholder Taxonomy"

**Core pattern** (RESEARCH.md §5):
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
    def restorer(m):
        idx = int(m.group(1))
        return tokens.get(idx, m.group(0))
    return _PLACEHOLDER_RE.sub(restorer, text)
```

**Validation after restore:** Assert `len(re.findall(r'⟦T\d+⟧', restored)) == 0` — no unreplaced markers remain.

---

### `backend/src/app/api/jobs.py` (controller, SSE + request-response)

**Pattern Source:** RESEARCH.md §7 "FastAPI SSE Endpoint"

**SSE endpoint pattern** (RESEARCH.md §7):
```python
import json
import asyncio
from fastapi import APIRouter, Depends
from starlette.requests import Request
from sse_starlette import EventSourceResponse
from redis.asyncio import Redis

router = APIRouter()

async def job_progress_generator(request: Request, job_id: str, redis: Redis):
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
    finally:                                # ALWAYS unsubscribe (Pitfall #3)
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

**Pitfall to avoid:** Do NOT omit the `finally` block — subscriptions must always be released or Redis leaks memory (Pitfall #3).

---

### `backend/src/app/api/upload.py` (controller, request-response)

**Pattern Source:** RESEARCH.md §8 "File Size Enforcement Pattern"

**Core pattern** (RESEARCH.md §8):
```python
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException, Request

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}

@router.post("/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    # Pre-check Content-Length if available
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum is 25 MB.")

    # Streaming read with size guard
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

    await file.seek(0)   # CRITICAL: reset cursor after manual size check (Pitfall #6)

    # MIME type validation
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type.")
```

**HTTP status codes to use:**
- 413: file too large
- 415: unsupported type
- 422: missing fields (FastAPI auto)
- 400: tracked-changes modal state conflict

**Pitfall to avoid:** After streaming size check, MUST call `await file.seek(0)` before passing to DOCX parser (Pitfall #6).

---

### `frontend/src/hooks/useJobProgress.ts` (hook, SSE + polling)

**Pattern Source:** RESEARCH.md §7 "Next.js 16 App Router: SSE Client + TanStack Query"

**Full hook pattern** (RESEARCH.md §7):
```typescript
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
      onerror() { sseOpen.current = false },
      onclose() { sseOpen.current = false },
    })

    return () => ctrl.abort()
  }, [jobId, queryClient])

  return useQuery<JobProgress>({
    queryKey: ["job", jobId],
    queryFn: () => fetch(`/api/jobs/${jobId}`).then(r => r.json()),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status && TERMINAL.has(status)) return false  // stop on terminal
      if (sseOpen.current) return false                  // SSE active, no polling
      return 2000                                        // poll when SSE closed
    },
    staleTime: 0,
  })
}
```

---

### `frontend/src/app/api/upload/route.ts` (controller, request-response)

**Pattern Source:** RESEARCH.md §9 "File Upload via Next.js API Route"

**Core pattern** (RESEARCH.md §9):
```typescript
export async function POST(request: Request) {
  const formData = await request.formData()
  const file = formData.get("file") as File | null
  if (!file) return Response.json({ error: "No file" }, { status: 400 })

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

**Why API Route not Server Action:** Server Actions have a 1 MB default body limit; API Route handles `formData()` natively without configuration override.

---

### `backend/Dockerfile` (config/infra)

**Pattern Source:** RESEARCH.md §12 "Docker Noto Font Wiring"

**Core pattern** (RESEARCH.md §12):
```dockerfile
FROM python:3.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/*
```

**Notes:**
- Fonts are installed for Phase 3 PDF reinsertion (PyMuPDF); DOCX does not need them server-side
- INFRA-05 healthcheck verifies presence at `/usr/share/fonts/opentype/noto/` (bookworm path — Assumption A4)
- Align with Thu's ICOM-P3 Dockerfile for the uv-based package install and non-root user pattern

---

### `backend/src/app/core/config.py` (config)

**Pattern Source:** CLAUDE.md §"Security Essentials" + AI-SPEC §4 client factory showing settings usage

**Core pattern:**
```python
from pydantic import SecretStr, AnyHttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    dashscope_api_key: SecretStr   # never logged; get_secret_value() only in client.py
    dashscope_base_url: AnyHttpUrl = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    database_url: str
    redis_url: str
    token_budget: int = 3000       # D-07: tune empirically within 2-4K range

    model_config = {"env_file": ".env"}

from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**Key constraint:** `DASHSCOPE_API_KEY` must use `SecretStr` so structlog never serializes the raw value. `get_secret_value()` is called only inside `make_llm_client`.

---

### `backend/src/app/core/telemetry.py` (utility)

**Pattern Source:** AI-SPEC §5 "Setup" + §7 "Instrumentation" — Arize Phoenix

**Core pattern** (AI-SPEC §5):
```python
import phoenix as px
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.openai import OpenAIInstrumentor

def setup_telemetry() -> None:
    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    OpenAIInstrumentor().instrument()   # auto-instruments all AsyncOpenAI calls
```

**Call sites:**
1. arq worker `startup()` hook — before `make_llm_client`
2. FastAPI `lifespan()` context manager — at app startup

---

### `backend/src/app/db/session.py` (config)

**Pattern Source:** RESEARCH.md §6 "Engine and Session Lifecycle"

**Core pattern** (RESEARCH.md §6):
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Called in worker startup; stored in ctx
engine = create_async_engine(str(settings.database_url), pool_size=5)
session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Usage in worker:
async with session_factory() as session:
    # one session per job, not per batch
```

**Key constraint:** One `AsyncSession` per job duration, not per batch — avoids connection pool exhaustion under concurrent batch execution.

---

### `Makefile` (config)

**Pattern Source:** AI-SPEC §5 Makefile targets

**Core pattern** (AI-SPEC §5):
```makefile
.PHONY: test test-unit test-integration eval

test-unit:
	uv run pytest backend/tests/ -m "not integration" \
	  --cov=backend/src/app \
	  --cov-report=term-missing \
	  --cov-fail-under=80 \
	  -v

test-integration:
	uv run pytest backend/tests/ -m integration \
	  --cov=backend/src/app \
	  -v

test: test-unit test-integration
```

---

## Shared Patterns

### NFC Normalization (CORE-04)
**Source:** RESEARCH.md §5 + AI-SPEC §3
**Apply to:** `extractor.py` (at `run.text` extraction), `translator.py` (at LLM output), `reassembler.py` (before write-back)

```python
import unicodedata

def nfc(s: str) -> str:
    """Apply at every LLM I/O boundary and at DOCX extraction."""
    return unicodedata.normalize("NFC", s)
```

**Two mandatory call sites:** (1) `run.text` extraction in extractor, (2) every string returned from `translate_batch` before writing to runs.

---

### structlog JSON Logging (D-19)
**Source:** CONTEXT.md D-19 + CLAUDE.md §"Python Coding Style" (no `print()`)
**Apply to:** All backend modules — worker, services, API routes

```python
import structlog

log = structlog.get_logger()

# Bind job_id as context var inside the worker so every log line carries it
log = log.bind(job_id=job_id)

# Use pattern strings, not f-strings, for log messages
log.info("batch_translated", batch_id=5, segments=47, job_id=job_id)
log.warning("rate_limit_retry", attempt=1, wait_s=2.0)
log.error("job_failed", error_class="Core03ViolationError")
```

---

### pydantic-settings Config (Thu's existing stack)
**Source:** CLAUDE.md §"Security Essentials" + AI-SPEC §4 client factory
**Apply to:** `config.py`, any module that needs env vars

- Use `SecretStr` for API keys — structlog never serializes `SecretStr` values
- Use `@lru_cache` on `get_settings()` — singleton, not re-parsed per call
- Import `Settings` from `app.core.config` everywhere — never read `os.environ` directly in app code

---

### FastAPI Dependency Injection Pattern
**Source:** CLAUDE.md §"FastAPI Rules" + RESEARCH.md §6 session lifecycle
**Apply to:** All API routes (`upload.py`, `jobs.py`, `health.py`)

```python
from fastapi import Depends
from app.core.config import get_settings, Settings
from app.db.session import get_session  # yields AsyncSession

# Route handler — never instantiate in route body
@router.post("/upload")
async def upload(file: UploadFile, session: AsyncSession = Depends(get_session)):
    ...
```

---

### Error Handling — API Layer
**Source:** CLAUDE.md §"FastAPI Rules" + RESEARCH.md §8 status codes
**Apply to:** `upload.py`, `jobs.py`

- Use `HTTPException` for all error responses — never bare `raise` or return error dicts
- HTTP codes: 201 for job creation, 413 for oversized file, 415 for wrong type, 422 for validation, 500 for unhandled exceptions
- Never expose `str(e)` in HTTP responses — log full traceback server-side; return generic message in response body
- DashScope 401 requires a specific actionable message (AI-SPEC §6 guardrail): "Ensure DASHSCOPE_API_KEY is the international key from dashscope-intl.aliyuncs.com"

---

### Immutability — Pydantic Frozen Models
**Source:** CLAUDE.md §"Python Coding Style" + AI-SPEC §4b.1 schema examples
**Apply to:** All Pydantic schema models in `llm/schemas.py`, `pipeline/segment.py`

```python
class Segment(BaseModel, frozen=True):
    id: str
    source_text: str
    structural_position: str
    seq_in_job: int
    is_comment: bool = False
```

---

### async-first Rule
**Source:** CLAUDE.md §"Python Anti-Patterns" + AI-SPEC §4b.2
**Apply to:** All backend service/worker code

- NEVER use `requests`, `time.sleep`, sync ORM in `async def` — use `httpx.AsyncClient`, `asyncio.sleep`, async SQLAlchemy
- NEVER call `asyncio.run()` inside an arq worker or FastAPI handler — always `await` directly
- Sync `OpenAI` client: for scripts (`healthcheck.py`, `smoke_dashscope.py`) and pytest unit tests only

---

## Files With No Codebase Analog (Use Reference Patterns Only)

| File | Role | Pattern Source | Notes |
|------|------|----------------|-------|
| `docker-compose.yml` | config/infra | CONTEXT.md D-03 topology | Align with Thu's ICOM-P3 compose pattern; D-03 specifies all 5 services + pgdata volume |
| `.env.example` | config | CONTEXT.md D-04 + security section | List all env vars from `Settings`; mark `DASHSCOPE_API_KEY` with comment about intl key requirement |
| `backend/src/app/db/models.py` | model | CONTEXT.md D-04 schema + REQUIREMENTS.md JOB/GLOS | `jobs` table: id, status, source_lang, target_lang, input_path, output_path, created_at, updated_at, error_msg, segments_done, segments_total, total_tokens_in, total_tokens_out |
| `backend/src/app/db/migrations/` | migration | Alembic standard | Run `alembic init` at `backend/`; `alembic.ini` points at `backend/src/app/db/migrations/` |
| `frontend/next.config.mjs` | config | D-20: Turbopack default | No webpack config needed; set `BACKEND_URL` env var for server-side fetch |
| `frontend/src/app/layout.tsx` | component | Next.js 16 root layout | Wrap with `QueryClientProvider`; load Inter via `next/font/google` |
| `scripts/healthcheck.py` | script | CONTEXT.md D-18 checklist | Check: DashScope intl probe, terminology param, Postgres, Redis, Noto fonts at `/usr/share/fonts/opentype/noto/` |
| `backend/tests/fixtures/` | test data | AI-SPEC §5 reference dataset | 3 golden DOCX files (simple, table-heavy, complex); create alongside implementation |

---

## Critical Anti-Patterns (Apply to All Files)

These are explicitly forbidden per CLAUDE.md §"What NOT to Use" and RESEARCH.md pitfalls:

| Anti-Pattern | Files at Risk | Why Forbidden | Correct Alternative |
|-------------|---------------|---------------|---------------------|
| `paragraph.text = translated_text` | `reassembler.py`, any docx-writing code | Calls `paragraph.clear()` — destroys all bold/italic/underline/font/color | `runs[0].text = value; [r.text="" for r in runs[1:]]` |
| `document.paragraphs` for full traversal | `extractor.py` | Misses table cells, headers, footers, text boxes | `doc.iter_inner_content()` + `_walk_table()` + section header/footer loop |
| System message in qwen-mt-turbo calls | `translator.py` | Treated as text to translate; directives go via `extra_body` only | Put all directives in `translation_options` |
| `temperature=` in qwen-mt-turbo calls | `translator.py` | Not supported; may cause rejection | Do not set — omit entirely |
| `dashscope` Python SDK | Any LLM code | Less mature async, breaks OpenAI ecosystem tooling | openai SDK with `base_url=dashscope-intl.aliyuncs.com` |
| `FastAPI BackgroundTasks` for translation | `upload.py` | No persistence, no retry, dies on restart | arq `enqueue_job()` |
| `asyncio.run()` inside arq/FastAPI | `translate_worker.py`, routes | Crashes: event loop already running | `await` directly |
| SSE without `finally` unsubscribe | `jobs.py` | Redis pub/sub subscription leaks | Always `try/finally: await pubsub.unsubscribe()` |
| `await file.seek(0)` omitted after size check | `upload.py` | File cursor at EOF; downstream reads empty bytes | Call `await file.seek(0)` after streaming size check |
| Worker `functions = ["translate_job"]` (string) | `translate_worker.py` | arq cannot discover function unless module imported | Pass direct reference: `functions = [translate_job]` |

---

## Metadata

**Pattern extraction date:** 2026-04-23
**Analog search scope:** Greenfield project — no codebase src/ tree to scan. All patterns extracted from in-project planning artifacts.
**Files scanned:** `01-AI-SPEC.md`, `01-RESEARCH.md`, `01-CONTEXT.md`, `01-UI-SPEC.md`, `REQUIREMENTS.md`, `CLAUDE.md`
**Thu's prior stacks referenced:**
- ICOM-P3 (FastAPI + Azure OpenAI + Next.js): `AsyncOpenAI` client shape, async SQLAlchemy, pydantic-settings, Dockerfile base
- scala-i-ask (FastAPI + Redis + Postgres): arq queue topology, Redis pub/sub, Alembic migrations
- Both stacks: `uv` for deps, ruff + pyright on PostToolUse, structlog JSON, Pydantic v2 frozen models as DTOs
