---
phase: 01-foundation-docx-pipeline
plan: "06a"
type: execute
wave: 3
depends_on:
  - "05"
files_modified:
  - backend/src/app/main.py
  - backend/src/app/api/__init__.py
  - backend/src/app/api/dependencies.py
  - backend/src/app/api/middleware/__init__.py
  - backend/src/app/api/middleware/cors.py
  - backend/src/app/api/routes/__init__.py
  - backend/src/app/api/routes/health.py
  - backend/src/app/api/routes/upload.py
  - backend/src/app/api/routes/languages.py
  - backend/src/app/api/routes/glossaries.py
  - backend/tests/api/__init__.py
  - backend/tests/api/test_upload.py
  - backend/tests/api/test_languages.py
autonomous: true
requirements:
  - INFRA-03
  - INFRA-04
  - UPLD-01
  - UPLD-02
  - UPLD-03
  - UPLD-04
  - UPLD-05
  - LANG-01

# NOTE — UPLD-04 (glossary picker UI): deferred to Phase 2 per D-15.
# The terminology=[...] plumbing is wired in Plan 03 (INFRA-02 coverage).
# This plan wires GET /glossaries endpoint as a stub so the frontend can
# query available glossaries once the glossary CRUD UI ships in Phase 2.
# No glossary picker appears in the Phase 1 upload form.

must_haves:
  truths:
    - "POST /upload validates file size ≤25MB, extension in {.docx,.pptx,.pdf}, returns job_id"
    - "POST /upload rejects oversized files with 413, unsupported types with 415"
    - "GET /languages returns {languages: [{code, name, qwen_code}]} with auto, vi, en, ja, zh"
    - "CORS is configured to allow Next.js dev origin (localhost:3000)"
    - "FastAPI lifespan creates/disposes DB engine, Redis pool, and arq pool on startup/shutdown"
    - "arq pool is shared on app.state — no per-request pool creation"
    - "GET /glossaries returns empty list stub for Phase 2 compatibility"
  artifacts:
    - path: "backend/src/app/main.py"
      provides: "FastAPI app with lifespan (engine + redis + arq_pool), CORS middleware, all routers mounted"
    - path: "backend/src/app/api/routes/upload.py"
      provides: "POST /upload with size guard, MIME check, tracked-changes probe, arq enqueue via app.state.arq_pool"
      exports: ["router"]
    - path: "backend/src/app/api/routes/languages.py"
      provides: "GET /languages returning {languages: [{code, name, qwen_code}]} list"
      exports: ["router", "SUPPORTED_LANGUAGES"]
    - path: "backend/src/app/api/routes/glossaries.py"
      provides: "GET /glossaries stub (Phase 2 placeholder)"
      exports: ["router"]
    - path: "backend/src/app/api/dependencies.py"
      provides: "get_redis(), get_arq_pool() FastAPI dependencies from app.state"
      exports: ["get_redis", "get_arq_pool"]
  key_links:
    - from: "backend/src/app/api/routes/upload.py"
      to: "app.state.arq_pool.enqueue_job('translate_job', job_id)"
      via: "get_arq_pool() dependency injected into route handler"
    - from: "backend/src/app/main.py lifespan"
      to: "DB engine + Redis client + arq pool"
      via: "async context manager startup/shutdown"
    - from: "backend/src/app/api/routes/languages.py"
      to: "SUPPORTED_LANGUAGES list[dict[str, str]]"
      via: "GET /languages response; code used for qwen source_lang/target_lang"
---

<objective>
Implement the FastAPI core: app entry point with lifespan, CORS, upload endpoint (size/type validation,
tracked-changes probe, arq enqueue via shared pool), languages endpoint (dict-based SUPPORTED_LANGUAGES),
glossaries stub, and shared dependencies.

NOTE — UPLD-04 (glossary picker UI): deferred to Phase 2 per D-15. The terminology plumbing
(INFRA-02) is covered in Plan 03. This plan wires a GET /glossaries stub so Phase 2 has a working
endpoint to build the picker against.

Purpose: Exposes the pipeline over HTTP so the Next.js frontend can upload files and receive job IDs.
Output: FastAPI app core wired. Upload + languages + health endpoints tested.
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
<!-- Upload validation (RESEARCH.md §8) -->
```python
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB
ALLOWED_EXTENSIONS = {".docx", ".pptx", ".pdf"}
# Phase 1: only DOCX translatable end-to-end
PHASE1_SUPPORTED_FORMATS = {".docx"}
```

<!-- arq pool: shared on app.state (W11 fix — no per-request pool creation) -->
```python
# In lifespan:
app.state.arq_pool = await arq.create_pool(RedisSettings.from_dsn(settings.redis_url))
# In dependencies.py:
def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool
# In upload.py:
arq_pool: ArqRedis = Depends(get_arq_pool)
await arq_pool.enqueue_job("translate_job", job.id)
```

<!-- SUPPORTED_LANGUAGES — dict shape (B5 fix — list[dict] not list[str]) -->
<!-- This shape allows frontend LanguageSelect to use code as form value and name as display -->
<!-- qwen_code maps to the language name qwen-mt-turbo expects in source_lang/target_lang -->
```python
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    {"code": "auto", "name": "Auto-detect", "qwen_code": "auto"},
    {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"},
    {"code": "en", "name": "English", "qwen_code": "English"},
    {"code": "ja", "name": "Japanese", "qwen_code": "Japanese"},
    {"code": "zh", "name": "Chinese (Simplified)", "qwen_code": "Chinese (Simplified)"},
    {"code": "zh-tw", "name": "Chinese (Traditional)", "qwen_code": "Chinese (Traditional)"},
    # ... full list (alphabetical after priority)
]
```

<!-- GET /languages response schema -->
```json
{
  "languages": [{"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"}, ...],
  "auto_detect_option": "auto"
}
```

<!-- Upload endpoint: validates source_lang/target_lang as codes (not display names) -->
<!-- e.g. source_lang="auto", target_lang="vi" -->

<!-- CORS: allow origins = ["http://localhost:3000"] for Next.js dev origin -->

<!-- lifespan pattern (FastAPI 0.115+ lifespan context manager) -->
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.engine = create_async_engine(settings.database_url.get_secret_value(), pool_size=5)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.arq_pool = await arq.create_pool(RedisSettings.from_dsn(settings.redis_url))
    yield
    await app.state.arq_pool.close()
    await app.state.redis.aclose()
    await app.state.engine.dispose()
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: App Entry Point + CORS + Dependencies + Health</name>
  <files>
    backend/src/app/main.py
    backend/src/app/api/__init__.py
    backend/src/app/api/middleware/__init__.py
    backend/src/app/api/middleware/cors.py
    backend/src/app/api/routes/__init__.py
    backend/src/app/api/routes/health.py
    backend/src/app/api/dependencies.py
    backend/tests/api/__init__.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 7: SSE, Section 8: upload)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-03 docker-compose, D-18 healthcheck)
    backend/src/app/core/config.py (Settings fields)
  </read_first>
  <action>
Create `backend/src/app/api/__init__.py` (empty).
Create `backend/src/app/api/middleware/__init__.py` (empty).
Create `backend/src/app/api/routes/__init__.py` (empty).
Create `backend/tests/api/__init__.py` (empty).

Create `backend/src/app/api/dependencies.py`:
```python
from __future__ import annotations
from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """FastAPI dependency: returns the shared Redis client from app state."""
    return request.app.state.redis


def get_arq_pool(request: Request):
    """FastAPI dependency: returns the shared arq pool from app state (W11 — no per-request pool)."""
    return request.app.state.arq_pool
```

Create `backend/src/app/api/middleware/cors.py` (extracted CORS config for clarity):
```python
from __future__ import annotations
from fastapi.middleware.cors import CORSMiddleware


def add_cors_middleware(app) -> None:
    """Add CORS middleware allowing Next.js dev origin (INFRA-04)."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
```

Create `backend/src/app/api/routes/health.py`:
```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}
```

Create `backend/src/app/main.py` with lifespan + CORS + routers:
```python
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
import arq
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.api.middleware.cors import add_cors_middleware
from app.api.routes import health, upload, languages, glossaries

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
    # W11: arq pool created ONCE at startup — injected via get_arq_pool() dependency
    app.state.arq_pool = await arq.create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    yield
    await app.state.arq_pool.close()
    await app.state.redis.aclose()
    await app.state.engine.dispose()


app = FastAPI(title="AI Translation", version="0.1.0", lifespan=lifespan)
add_cors_middleware(app)

app.include_router(health.router)
app.include_router(upload.router)
app.include_router(languages.router)
app.include_router(glossaries.router)
```
  </action>
  <verify>
    <automated>
      grep -q "app.state.arq_pool" backend/src/app/main.py &amp;&amp;
      grep -q "get_arq_pool" backend/src/app/api/dependencies.py &amp;&amp;
      grep -q "CORSMiddleware" backend/src/app/api/middleware/cors.py &amp;&amp;
      grep -q "localhost:3000" backend/src/app/api/middleware/cors.py &amp;&amp;
      grep -q "asynccontextmanager" backend/src/app/main.py
    </automated>
  </verify>
  <done>
    main.py lifespan creates engine + redis + arq_pool at startup; disposes all three on shutdown.
    arq pool stored on app.state — no per-request pool creation (W11 fixed).
    get_arq_pool() dependency reads from app.state.
    CORS allows localhost:3000 only (INFRA-04).
    GET /health returns {"status": "ok"}.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Upload Endpoint + Languages Endpoint + Glossaries Stub</name>
  <files>
    backend/src/app/api/routes/upload.py
    backend/src/app/api/routes/languages.py
    backend/src/app/api/routes/glossaries.py
    backend/tests/api/test_upload.py
    backend/tests/api/test_languages.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 8: upload size guard, MIME check)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-13 tracked-changes modal, D-15 Phase 1 DOCX-only, D-16 auto-detect)
    backend/src/app/api/dependencies.py (get_session, get_arq_pool)
    backend/src/app/services/job_service.py (create_job signature)
    backend/src/app/pipeline/docx/tracked.py (has_tracked_changes signature)
  </read_first>
  <action>
Create `backend/src/app/api/routes/languages.py` (B5 fix — list[dict] shape):
```python
from fastapi import APIRouter

router = APIRouter()

# qwen-mt-turbo supported languages (B5: dict shape for code-based selection)
# code: used as form value in frontend and as key in upload validation
# name: display label in LanguageSelect dropdown
# qwen_code: value sent to qwen-mt-turbo source_lang/target_lang params
SUPPORTED_LANGUAGES: list[dict[str, str]] = [
    # "auto" is source-only — not valid as target_lang
    {"code": "auto", "name": "Auto-detect", "qwen_code": "auto"},
    # Priority languages (UI-SPEC Recommended group)
    {"code": "vi", "name": "Vietnamese", "qwen_code": "Vietnamese"},
    {"code": "en", "name": "English", "qwen_code": "English"},
    {"code": "ja", "name": "Japanese", "qwen_code": "Japanese"},
    {"code": "zh", "name": "Chinese (Simplified)", "qwen_code": "Chinese (Simplified)"},
    {"code": "zh-tw", "name": "Chinese (Traditional)", "qwen_code": "Chinese (Traditional)"},
    # Full list (alphabetical)
    {"code": "af", "name": "Afrikaans", "qwen_code": "Afrikaans"},
    {"code": "sq", "name": "Albanian", "qwen_code": "Albanian"},
    {"code": "am", "name": "Amharic", "qwen_code": "Amharic"},
    {"code": "ar", "name": "Arabic", "qwen_code": "Arabic"},
    {"code": "az", "name": "Azerbaijani", "qwen_code": "Azerbaijani"},
    {"code": "eu", "name": "Basque", "qwen_code": "Basque"},
    {"code": "be", "name": "Belarusian", "qwen_code": "Belarusian"},
    {"code": "bn", "name": "Bengali", "qwen_code": "Bengali"},
    {"code": "bs", "name": "Bosnian", "qwen_code": "Bosnian"},
    {"code": "bg", "name": "Bulgarian", "qwen_code": "Bulgarian"},
    {"code": "ca", "name": "Catalan", "qwen_code": "Catalan"},
    {"code": "hr", "name": "Croatian", "qwen_code": "Croatian"},
    {"code": "cs", "name": "Czech", "qwen_code": "Czech"},
    {"code": "da", "name": "Danish", "qwen_code": "Danish"},
    {"code": "nl", "name": "Dutch", "qwen_code": "Dutch"},
    {"code": "eo", "name": "Esperanto", "qwen_code": "Esperanto"},
    {"code": "et", "name": "Estonian", "qwen_code": "Estonian"},
    {"code": "fi", "name": "Finnish", "qwen_code": "Finnish"},
    {"code": "fr", "name": "French", "qwen_code": "French"},
    {"code": "gl", "name": "Galician", "qwen_code": "Galician"},
    {"code": "ka", "name": "Georgian", "qwen_code": "Georgian"},
    {"code": "de", "name": "German", "qwen_code": "German"},
    {"code": "el", "name": "Greek", "qwen_code": "Greek"},
    {"code": "gu", "name": "Gujarati", "qwen_code": "Gujarati"},
    {"code": "ht", "name": "Haitian Creole", "qwen_code": "Haitian Creole"},
    {"code": "he", "name": "Hebrew", "qwen_code": "Hebrew"},
    {"code": "hi", "name": "Hindi", "qwen_code": "Hindi"},
    {"code": "hu", "name": "Hungarian", "qwen_code": "Hungarian"},
    {"code": "is", "name": "Icelandic", "qwen_code": "Icelandic"},
    {"code": "id", "name": "Indonesian", "qwen_code": "Indonesian"},
    {"code": "ga", "name": "Irish", "qwen_code": "Irish"},
    {"code": "it", "name": "Italian", "qwen_code": "Italian"},
    {"code": "kn", "name": "Kannada", "qwen_code": "Kannada"},
    {"code": "ko", "name": "Korean", "qwen_code": "Korean"},
    {"code": "ku", "name": "Kurdish", "qwen_code": "Kurdish"},
    {"code": "lv", "name": "Latvian", "qwen_code": "Latvian"},
    {"code": "lt", "name": "Lithuanian", "qwen_code": "Lithuanian"},
    {"code": "mk", "name": "Macedonian", "qwen_code": "Macedonian"},
    {"code": "ms", "name": "Malay", "qwen_code": "Malay"},
    {"code": "ml", "name": "Malayalam", "qwen_code": "Malayalam"},
    {"code": "mt", "name": "Maltese", "qwen_code": "Maltese"},
    {"code": "mr", "name": "Marathi", "qwen_code": "Marathi"},
    {"code": "mn", "name": "Mongolian", "qwen_code": "Mongolian"},
    {"code": "ne", "name": "Nepali", "qwen_code": "Nepali"},
    {"code": "no", "name": "Norwegian", "qwen_code": "Norwegian"},
    {"code": "fa", "name": "Persian", "qwen_code": "Persian"},
    {"code": "pl", "name": "Polish", "qwen_code": "Polish"},
    {"code": "pt", "name": "Portuguese", "qwen_code": "Portuguese"},
    {"code": "pa", "name": "Punjabi", "qwen_code": "Punjabi"},
    {"code": "ro", "name": "Romanian", "qwen_code": "Romanian"},
    {"code": "ru", "name": "Russian", "qwen_code": "Russian"},
    {"code": "sr", "name": "Serbian", "qwen_code": "Serbian"},
    {"code": "si", "name": "Sinhala", "qwen_code": "Sinhala"},
    {"code": "sk", "name": "Slovak", "qwen_code": "Slovak"},
    {"code": "sl", "name": "Slovenian", "qwen_code": "Slovenian"},
    {"code": "so", "name": "Somali", "qwen_code": "Somali"},
    {"code": "es", "name": "Spanish", "qwen_code": "Spanish"},
    {"code": "sw", "name": "Swahili", "qwen_code": "Swahili"},
    {"code": "sv", "name": "Swedish", "qwen_code": "Swedish"},
    {"code": "ta", "name": "Tamil", "qwen_code": "Tamil"},
    {"code": "te", "name": "Telugu", "qwen_code": "Telugu"},
    {"code": "th", "name": "Thai", "qwen_code": "Thai"},
    {"code": "tr", "name": "Turkish", "qwen_code": "Turkish"},
    {"code": "uk", "name": "Ukrainian", "qwen_code": "Ukrainian"},
    {"code": "ur", "name": "Urdu", "qwen_code": "Urdu"},
    {"code": "uz", "name": "Uzbek", "qwen_code": "Uzbek"},
    {"code": "cy", "name": "Welsh", "qwen_code": "Welsh"},
    {"code": "xh", "name": "Xhosa", "qwen_code": "Xhosa"},
    {"code": "yo", "name": "Yoruba", "qwen_code": "Yoruba"},
    {"code": "zu", "name": "Zulu", "qwen_code": "Zulu"},
]

# Valid codes for upload validation (excludes "auto" for target_lang)
_VALID_CODES = {lang["code"] for lang in SUPPORTED_LANGUAGES}
_VALID_TARGET_CODES = _VALID_CODES - {"auto"}


@router.get("/languages")
async def get_languages():
    """
    LANG-01: Return qwen-mt-turbo supported languages as code+name+qwen_code dicts.
    Client caches for 24h (staleTime: 24h in TanStack Query per UI-SPEC).
    """
    return {
        "languages": SUPPORTED_LANGUAGES,
        "auto_detect_option": "auto",
    }
```

Create `backend/src/app/api/routes/glossaries.py` (Phase 2 stub — UPLD-04 deferred per D-15):
```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/glossaries")
async def list_glossaries():
    """
    UPLD-04 stub: Glossary CRUD and picker UI are deferred to Phase 2 (D-15).
    Returns empty list so Phase 2 frontend can build the picker against a working endpoint.
    """
    return {"glossaries": []}
```

Create `backend/src/app/api/routes/upload.py` (W11 fixed — uses get_arq_pool dependency):
```python
from __future__ import annotations
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, File, Form, UploadFile, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.api.dependencies import get_arq_pool
from app.services.job_service import create_job
from app.api.routes.languages import _VALID_TARGET_CODES

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
    arq_pool=Depends(get_arq_pool),
):
    """
    UPLD-01/02/03/05: Upload file, validate, create job, enqueue.
    source_lang / target_lang accept language codes (e.g. 'vi', 'en', 'auto').
    Returns: {job_id, has_tracked_changes}
    """
    # Pre-check Content-Length (fast path)
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

    # Phase 1: only DOCX translatable end-to-end
    if ext not in PHASE1_SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=422,
            detail=f"{ext.upper().lstrip('.')} translation is not yet supported. DOCX is available now; PPTX and PDF are coming in the next release."
        )

    # Validate language codes
    if target_lang not in _VALID_TARGET_CODES:
        raise HTTPException(status_code=422, detail=f"Unsupported target language: {target_lang!r}")

    # Streaming size check (defense in depth)
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
        job_id=job_id,
        source_lang=source_lang,
        target_lang=target_lang,
        input_format=ext.lstrip("."),
        input_path=input_path,
        original_filename=filename,
        has_tracked_changes=from_docx_has_tracked,
        tracked_changes_action=tracked_changes_action,
    )

    # Enqueue arq job via shared pool (W11: no per-request pool creation)
    await arq_pool.enqueue_job("translate_job", job.id)

    return {
        "job_id": job.id,
        "has_tracked_changes": from_docx_has_tracked,
    }
```

Write `backend/tests/api/test_upload.py` testing size/type validation using httpx ASGITransport.
Write `backend/tests/api/test_languages.py` testing GET /languages returns dict list with "vi" code.
  </action>
  <verify>
    <automated>
      grep -q "MAX_UPLOAD_BYTES = 25" backend/src/app/api/routes/upload.py &amp;&amp;
      grep -q "status_code=413" backend/src/app/api/routes/upload.py &amp;&amp;
      grep -q "status_code=415" backend/src/app/api/routes/upload.py &amp;&amp;
      grep -q "get_arq_pool" backend/src/app/api/routes/upload.py &amp;&amp;
      grep -q "arq_pool.enqueue_job" backend/src/app/api/routes/upload.py &amp;&amp;
      grep -q "qwen_code" backend/src/app/api/routes/languages.py &amp;&amp;
      grep -q '"code": "vi"' backend/src/app/api/routes/languages.py &amp;&amp;
      grep -q '"code": "auto"' backend/src/app/api/routes/languages.py
    </automated>
  </verify>
  <done>
    POST /upload rejects files > 25MB with 413, unsupported extensions with 415, PPTX/PDF with 422.
    POST /upload uses get_arq_pool() dependency — no per-request arq pool creation (W11).
    SUPPORTED_LANGUAGES is list[dict] with code/name/qwen_code keys (B5 fix).
    GET /languages returns {"languages": [{code, name, qwen_code}], "auto_detect_option": "auto"}.
    GET /glossaries returns {"glossaries": []} stub (UPLD-04 deferred to Phase 2 per D-15).
    main.py lifespan creates arq_pool once at startup and closes on shutdown.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| client → POST /upload | Untrusted file content + form parameters (language codes) |
| job_id generation → file system | Server-generated UUID used in path construction |
| arq pool → Redis | Single shared pool; Redis auth controlled by settings.redis_url |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06a-01 | Tampering | POST /upload file content | mitigate | Extension checked; size guarded; path constructed server-side from data_dir + UUID |
| T-06a-02 | Denial of Service | per-request arq pool creation | mitigate | W11 fix: single pool on app.state; no per-request pool creation |
| T-06a-03 | Tampering | source_lang / target_lang codes | mitigate | target_lang validated against _VALID_TARGET_CODES; source_lang "auto" is valid passthrough |
| T-06a-04 | Spoofing | CORS allows localhost:3000 only | mitigate | Not "*"; credentials not allowed; restricted to dev origin for PoC |
| T-06a-05 | Information Disclosure | error_msg in HTTP responses | accept | Internal PoC; HTTPException detail strings are informational, not sensitive |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/api/test_upload.py tests/api/test_languages.py -v` — all pass
2. `grep -q "app.state.arq_pool" backend/src/app/main.py` — passes (W11 verified)
3. `grep -q '"code": "vi"' backend/src/app/api/routes/languages.py` — passes (B5 verified)
4. `grep -q "get_arq_pool" backend/src/app/api/routes/upload.py` — passes (W11 verified)
5. After docker compose up: `curl http://localhost:8000/health` → `{"status":"ok"}`
6. After docker compose up: `curl http://localhost:8000/languages | jq '.languages[0]'` → `{"code": "auto", ...}`
</verification>

<success_criteria>
- POST /upload returns 413 for files > 25MB, 415 for unsupported types, 422 for PPTX/PDF in Phase 1
- arq enqueue uses app.state.arq_pool — no per-request pool creation
- SUPPORTED_LANGUAGES is list[dict] with code/name/qwen_code fields
- GET /languages response shape: {languages: [{code, name, qwen_code}], auto_detect_option: "auto"}
- target_lang validated against code-based set
- GET /glossaries returns {"glossaries": []} stub
- CORS allows http://localhost:3000 only; lifespan creates engine + redis + arq_pool
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-06a-SUMMARY.md`
</output>
