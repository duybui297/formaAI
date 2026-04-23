---
phase: 01-foundation-docx-pipeline
plan: "06"
type: execute
wave: 3
depends_on:
  - "02"
  - "04"
  - "05"
files_modified:
  - backend/src/app/main.py
  - backend/src/app/api/__init__.py
  - backend/src/app/api/health.py
  - backend/src/app/api/upload.py
  - backend/src/app/api/jobs.py
  - backend/src/app/api/languages.py
  - backend/src/app/api/dependencies.py
  - backend/tests/api/__init__.py
  - backend/tests/api/test_upload.py
  - backend/tests/api/test_sse.py
  - backend/tests/api/test_languages.py
autonomous: true
requirements:
  - INFRA-03
  - INFRA-04
  - UPLD-01
  - UPLD-02
  - UPLD-03
  - UPLD-05
  - JOB-01
  - JOB-02
  - JOB-03
  - JOB-04
  - LANG-01

must_haves:
  truths:
    - "POST /upload validates file size ≤25MB, extension in {.docx,.pptx,.pdf}, returns job_id"
    - "POST /upload rejects oversized files with 413, unsupported types with 415"
    - "GET /jobs/{id}/stream opens SSE event stream from Redis pub/sub with ping=15"
    - "GET /jobs/{id} returns job status JSON including segments_done, segments_total"
    - "GET /jobs/{id}/download streams the output file for done jobs"
    - "GET /languages returns static qwen-mt-turbo language list"
    - "CORS is configured to allow Next.js dev origin (localhost:3000)"
    - "FastAPI lifespan creates/disposes DB engine and Redis pool"
  artifacts:
    - path: "backend/src/app/main.py"
      provides: "FastAPI app with lifespan, CORS middleware, all routers mounted"
    - path: "backend/src/app/api/upload.py"
      provides: "POST /upload with size guard, MIME check, tracked-changes probe, arq enqueue"
    - path: "backend/src/app/api/jobs.py"
      provides: "GET /jobs, GET /jobs/{id}, GET /jobs/{id}/stream (SSE), GET /jobs/{id}/download"
    - path: "backend/src/app/api/languages.py"
      provides: "GET /languages returning qwen-mt-turbo supported language list"
  key_links:
    - from: "backend/src/app/api/jobs.py stream_job_progress"
      to: "redis.pubsub().subscribe('job:{id}')"
      via: "SSE generator (RESEARCH.md §7)"
      pattern: "EventSourceResponse"
    - from: "backend/src/app/api/upload.py"
      to: "redis_pool.enqueue_job('translate_job', job_id)"
      via: "arq queue enqueue after job created"
    - from: "backend/src/app/main.py lifespan"
      to: "DB engine + Redis pool"
      via: "async context manager startup/shutdown"
---

<objective>
Implement the FastAPI backend: app entry point with lifespan, CORS, upload endpoint (with size/type validation, tracked-changes probe, arq enqueue), jobs endpoints (status, SSE progress stream, download), languages endpoint, and shared dependencies.

Purpose: Exposes the pipeline over HTTP so the Next.js frontend can upload files and poll job status.
Output: FastAPI app fully wired. Unit tests for upload validation and SSE behavior.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md
@.planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md

<interfaces>
<!-- Key patterns from RESEARCH.md §7 (SSE), §8 (upload), §10 (languages) -->

SSE endpoint (RESEARCH.md §7 exact pattern):
```python
async def job_progress_generator(request, job_id, redis):
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"job:{job_id}")
    try:
        while True:
            if await request.is_disconnected(): break
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                payload = json.loads(message["data"])
                yield {"data": json.dumps(payload), "event": "progress"}
                if payload.get("status") in ("done", "failed", "needs_review"): break
            else:
                await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(f"job:{job_id}")
        await pubsub.close()

return EventSourceResponse(generator(), ping=15, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})
```

Upload validation (RESEARCH.md §8):
```python
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}

# 1. Pre-check Content-Length header
# 2. Stream file bytes counting total; raise 413 if exceeded
# 3. await file.seek(0) after reading (Pitfall #6)
# 4. Check extension → 415 if not in ALLOWED_EXTENSIONS
```

arq enqueueing pattern (RESEARCH.md code examples):
```python
from arq import create_pool
from arq.connections import RedisSettings

async def enqueue_translation_job(job_id: str, redis_pool) -> None:
    await redis_pool.enqueue_job("translate_job", job_id)
```

CORS: allow origins = ["http://localhost:3000"] for Next.js dev origin.

lifespan pattern (FastAPI 0.115+ lifespan context manager):
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: create engine + redis pool
    yield
    # shutdown: dispose engine + close redis
```

INFRA-05: Noto fonts installed in Docker image (already done in Plan 01); no API endpoint needed.
Phase 1 scope: upload supports DOCX only for translation (UPLD-02 — reject PPTX/PDF in Phase 1 with clear message "PPTX and PDF support coming soon").
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Upload Endpoint + Languages Endpoint + App Entry Point</name>
  <files>
    backend/src/app/main.py
    backend/src/app/api/__init__.py
    backend/src/app/api/health.py
    backend/src/app/api/upload.py
    backend/src/app/api/languages.py
    backend/src/app/api/dependencies.py
    backend/tests/api/__init__.py
    backend/tests/api/test_upload.py
    backend/tests/api/test_languages.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 8: upload handling, Section 10: language list)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-13 tracked-changes modal, D-15 Phase 1 DOCX-only translation)
    .planning/phases/01-foundation-docx-pipeline/01-UI-SPEC.md (Upload page component inventory: error copy, format detection)
    backend/src/app/db/session.py (get_session dependency)
    backend/src/app/services/job_service.py (create_job signature)
    backend/src/app/pipeline/docx/tracked.py (has_tracked_changes signature)
  </read_first>
  <action>
Create `backend/src/app/api/__init__.py` (empty).
Create `backend/tests/api/__init__.py` (empty).

Create `backend/src/app/api/dependencies.py`:
```python
from __future__ import annotations
from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """FastAPI dependency: returns the shared Redis client from app state."""
    return request.app.state.redis
```

Create `backend/src/app/api/health.py`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

Create `backend/src/app/api/languages.py` (LANG-01: static list served from backend):
```python
from fastapi import APIRouter

router = APIRouter()

# qwen-mt-turbo supported languages — static per model version (LANG-01)
# Full 92-language list; priority languages first (LANG-02 + UI-SPEC grouped)
SUPPORTED_LANGUAGES = [
    # Priority (UI-SPEC: shown under "Recommended" group)
    "Vietnamese", "English", "Japanese", "Chinese (Simplified)", "Chinese (Traditional)",
    # Full list (alphabetical after priority)
    "Afrikaans", "Albanian", "Amharic", "Arabic", "Azerbaijani", "Basque", "Belarusian",
    "Bengali", "Bosnian", "Bulgarian", "Catalan", "Croatian", "Czech", "Danish", "Dutch",
    "Esperanto", "Estonian", "Finnish", "French", "Galician", "Georgian", "German",
    "Greek", "Gujarati", "Haitian Creole", "Hebrew", "Hindi", "Hungarian", "Icelandic",
    "Indonesian", "Irish", "Italian", "Kannada", "Korean", "Kurdish", "Latvian",
    "Lithuanian", "Macedonian", "Malay", "Malayalam", "Maltese", "Marathi", "Mongolian",
    "Nepali", "Norwegian", "Persian", "Polish", "Portuguese", "Punjabi", "Romanian",
    "Russian", "Serbian", "Sinhala", "Slovak", "Slovenian", "Somali", "Spanish",
    "Swahili", "Swedish", "Tamil", "Telugu", "Thai", "Turkish", "Ukrainian", "Urdu",
    "Uzbek", "Welsh", "Xhosa", "Yoruba", "Zulu",
]

@router.get("/languages")
async def get_languages():
    """
    LANG-01: Return qwen-mt-turbo supported languages.
    Client caches for 24h (staleTime: 24h in TanStack Query per UI-SPEC).
    """
    return {
        "languages": SUPPORTED_LANGUAGES,
        "auto_detect_option": "auto",
    }
```

Create `backend/src/app/api/upload.py` (RESEARCH.md §8 size guard + MIME check):
```python
from __future__ import annotations
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.api.dependencies import get_redis
from app.services.job_service import create_job, append_error_log

router = APIRouter()

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB (UPLD-01)
ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}  # UPLD-02
# Phase 1: only DOCX supports end-to-end translation (D-15)
PHASE1_SUPPORTED_FORMATS = {".docx"}


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    source_lang: str = Form(...),
    target_lang: str = Form(...),
    tracked_changes_action: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    UPLD-01/02/03/05: Upload file, validate, create job, enqueue.
    Returns: {job_id, has_tracked_changes}
    """
    # Pre-check Content-Length (fast path — not guaranteed by all clients)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large — maximum is 25 MB.")

    # Extension check
    filename = file.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a DOCX, PDF, or PPTX."
        )

    # Phase 1: only DOCX translatable end-to-end (PPTX/PDF come in Phase 3)
    if ext not in PHASE1_SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"{ext.upper().lstrip('.')} translation is not yet supported. DOCX is available now; PPTX and PDF are coming in the next release."
        )

    # Streaming size check (defense in depth — reads body counting bytes)
    chunk_size = 64 * 1024
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large — maximum is 25 MB.")
        chunks.append(chunk)
    content = b"".join(chunks)
    await file.seek(0)  # Pitfall #6: reset cursor after manual read

    # Save source file per D-04 layout
    settings = request.app.state.settings
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(settings.data_dir, "jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    input_path = os.path.join(job_dir, f"source{ext}")
    with open(input_path, "wb") as f:
        f.write(content)

    # DOCX-04 / D-13: probe for tracked changes
    from_docx_has_tracked = False
    if ext == ".docx":
        from docx import Document
        from app.pipeline.docx.tracked import has_tracked_changes
        try:
            doc = Document(input_path)
            from_docx_has_tracked = has_tracked_changes(doc)
        except Exception:
            pass  # Malformed DOCX — let worker handle it

    # Create Job row
    job = await create_job(
        session=session,
        source_lang=source_lang,
        target_lang=target_lang,
        input_format=ext.lstrip("."),
        input_path=input_path,
        original_filename=filename,
        has_tracked_changes=from_docx_has_tracked,
        tracked_changes_action=tracked_changes_action,
    )

    # Enqueue arq job
    from arq import create_pool
    from arq.connections import RedisSettings
    redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await redis_pool.enqueue_job("translate_job", job.id)
    await redis_pool.close()

    return {
        "job_id": job.id,
        "has_tracked_changes": from_docx_has_tracked,
    }
```

Create `backend/src/app/main.py` with lifespan + CORS + routers:
```python
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.api import health, upload, jobs, languages

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: create shared resources on startup, dispose on shutdown."""
    app.state.settings = settings
    app.state.engine = create_async_engine(
        settings.database_url.get_secret_value(), pool_size=5
    )
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    yield
    await app.state.engine.dispose()
    await app.state.redis.aclose()


app = FastAPI(title="AI Translation", version="0.1.0", lifespan=lifespan)

# CORS: allow Next.js dev origin (INFRA-04)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(jobs.router)
app.include_router(languages.router)
```

Write test_upload.py testing size/type validation using httpx ASGITransport (no real file IO needed — mock create_job).
Write test_languages.py testing GET /languages returns the list with "Vietnamese" in it.
  </action>
  <verify>
    <automated>
      grep -q "MAX_UPLOAD_BYTES = 25" backend/src/app/api/upload.py &amp;&amp;
      grep -q "status_code=413" backend/src/app/api/upload.py &amp;&amp;
      grep -q "status_code=415" backend/src/app/api/upload.py &amp;&amp;
      grep -q "await file.seek(0)" backend/src/app/api/upload.py &amp;&amp;
      grep -q "CORSMiddleware" backend/src/app/main.py &amp;&amp;
      grep -q "lifespan" backend/src/app/main.py &amp;&amp;
      grep -q "Vietnamese" backend/src/app/api/languages.py
    </automated>
  </verify>
  <done>
    POST /upload rejects files > 25MB with 413, unsupported extensions with 415, PPTX/PDF in Phase 1 with 422.
    Successful upload creates job row, writes source file to .data/jobs/{job_id}/source.docx, enqueues translate_job.
    has_tracked_changes probe runs for DOCX files; result returned in response.
    await file.seek(0) called after manual stream read.
    GET /languages returns SUPPORTED_LANGUAGES list with "Vietnamese" first.
    main.py has CORS allowing localhost:3000 and lifespan creating engine + redis.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Jobs Endpoints + SSE Stream</name>
  <files>
    backend/src/app/api/jobs.py
    backend/tests/api/test_sse.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 7: SSE endpoint full pattern, RESEARCH.md Pitfall #3 pub/sub leak)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-09 SSE transport, D-10 payload shape, D-11 error surface)
    backend/src/app/services/job_service.py (get_job signature)
    backend/src/app/db/models.py (Job fields for response serialization)
  </read_first>
  <action>
Create `backend/src/app/api/jobs.py`:
```python
from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.requests import Request
from sse_starlette import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.api.dependencies import get_redis
from app.services.job_service import get_job

router = APIRouter()


def _job_to_dict(job) -> dict:
    """Serialize Job model to response dict."""
    return {
        "id": job.id,
        "status": job.status.value,
        "stage": job.stage.value if job.stage else None,
        "source_lang": job.source_lang,
        "target_lang": job.target_lang,
        "detected_lang": job.detected_lang,
        "input_format": job.input_format,
        "original_filename": job.original_filename,
        "segments_done": job.segments_done,
        "segments_total": job.segments_total,
        "retry_count": job.retry_count,
        "error_msg": job.error_msg,
        "has_tracked_changes": job.has_tracked_changes,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }


@router.get("/jobs")
async def list_jobs(session: AsyncSession = Depends(get_session)):
    """Return last 50 jobs, newest first (Jobs List Page)."""
    from sqlalchemy import select, desc
    from app.db.models import Job
    result = await session.execute(
        select(Job).order_by(desc(Job.created_at)).limit(50)
    )
    return {"jobs": [_job_to_dict(j) for j in result.scalars().all()]}


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str, session: AsyncSession = Depends(get_session)):
    """JOB-01/04: Return job status and progress."""
    job = await get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    request: Request,
    redis=Depends(get_redis),
):
    """
    JOB-02/03: SSE stream of job progress events.
    Primary transport per D-09. Polling fallback in frontend.
    Pitfall #3: always unsubscribe in finally block to prevent pub/sub leak.
    """
    async def job_progress_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"job:{job_id}")
        try:
            while True:
                if await request.is_disconnected():
                    break
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
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
            # Pitfall #3: always unsubscribe to prevent memory leak
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.aclose()

    return EventSourceResponse(
        job_progress_generator(),
        ping=15,
        headers={
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
            "Cache-Control": "no-store",
        },
    )


@router.get("/jobs/{job_id}/download")
async def download_translated_file(
    job_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Stream the translated output file for completed jobs."""
    job = await get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status.value not in ("done", "needs_review"):
        raise HTTPException(status_code=409, detail="Job is not yet complete")
    if not job.output_path:
        raise HTTPException(status_code=404, detail="Output file not found")

    import os
    if not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Output file has been deleted")

    # Return file with original filename (prefixed "translated_")
    download_name = f"translated_{job.original_filename}"
    return FileResponse(
        path=job.output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
```

Write test_sse.py testing:
- SSE generator yields {"event": "progress", "data": ...} for published Redis message
- SSE generator stops on terminal status (done/failed)
- GET /jobs/{id} returns 404 for unknown job_id
- GET /jobs/{id}/download returns 409 when job not done
  </action>
  <verify>
    <automated>
      grep -q "EventSourceResponse" backend/src/app/api/jobs.py &amp;&amp;
      grep -q "ping=15" backend/src/app/api/jobs.py &amp;&amp;
      grep -q "unsubscribe" backend/src/app/api/jobs.py &amp;&amp;
      grep -q "finally" backend/src/app/api/jobs.py &amp;&amp;
      grep -q "is_disconnected" backend/src/app/api/jobs.py &amp;&amp;
      grep -q "X-Accel-Buffering" backend/src/app/api/jobs.py
    </automated>
  </verify>
  <done>
    GET /jobs/{id} returns job dict with status, stage, segments_done, segments_total, error_msg.
    GET /jobs/{id}/stream returns EventSourceResponse with ping=15 and X-Accel-Buffering: no header.
    SSE generator unsubscribes from pub/sub in finally block (prevents Pitfall #3 memory leak).
    GET /jobs/{id}/download returns FileResponse for done/needs_review jobs; 409 for incomplete.
    SSE stream closes on terminal status in payload.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → POST /upload | Untrusted file content + form parameters |
| job_id in URL → file system | Client-provided job_id used in path resolution |
| SSE connection → Redis | Each SSE connection opens a Redis pub/sub subscription |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06-01 | Tampering | POST /upload file content | mitigate | Extension checked; size guarded; file saved to server-controlled path with server-generated job_id |
| T-06-02 | Elevation of Privilege | GET /jobs/{id}/download path | mitigate | output_path stored in DB by server; not user-supplied; os.path.exists check before FileResponse |
| T-06-03 | Denial of Service | SSE pub/sub leak on abrupt disconnect | mitigate | finally block in generator always unsubscribes; CancelledError caught |
| T-06-04 | Information Disclosure | error_msg in GET /jobs/{id} | accept | Internal PoC; no auth; error messages go to logs and are shown in UI per D-11 (no traceback) |
| T-06-05 | Spoofing | CORS allows localhost:3000 only | mitigate | Not "*"; credentials not allowed; restricted to dev origin for PoC |
| T-06-06 | Denial of Service | Unlimited SSE connections per job_id | accept | Internal PoC; no rate limiting in Phase 1; v2 concern |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/api/ -v` — all tests pass
2. `grep -q "ping=15" backend/src/app/api/jobs.py` — passes
3. `grep -q "MAX_UPLOAD_BYTES = 25" backend/src/app/api/upload.py` — passes
4. `grep -q "unsubscribe" backend/src/app/api/jobs.py` — passes (Pitfall #3 fixed)
5. `grep -q "localhost:3000" backend/src/app/main.py` — passes (CORS)
6. After docker compose up: `curl http://localhost:8000/health` → `{"status":"ok"}`
7. After docker compose up: `curl http://localhost:8000/languages` → JSON with "Vietnamese"
</verification>

<success_criteria>
- POST /upload returns 413 for files > 25MB, 415 for unsupported types, 422 for PPTX/PDF in Phase 1
- POST /upload creates Job row + writes source file + enqueues translate_job
- GET /jobs/{id}/stream returns EventSourceResponse with ping=15; unsubscribes in finally block
- GET /jobs/{id}/download returns FileResponse; 409 for non-terminal jobs
- GET /languages returns list containing "Vietnamese", "English", "Japanese", "Chinese (Simplified)"
- CORS allows http://localhost:3000 only
- lifespan creates engine + redis; disposes on shutdown
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-06-SUMMARY.md`
</output>
