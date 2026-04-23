---
phase: 01-foundation-docx-pipeline
plan: "06b"
type: execute
wave: 3
depends_on:
  - "05"
  - "06a"
files_modified:
  - backend/src/app/api/routes/jobs.py
  - backend/src/app/api/routes/sse.py
  - backend/tests/api/test_sse.py
  - backend/tests/api/test_jobs.py
autonomous: true
requirements:
  - JOB-01
  - JOB-02
  - JOB-03
  - JOB-04

must_haves:
  truths:
    - "GET /jobs/{id}/stream opens SSE event stream from Redis pub/sub with ping=15"
    - "SSE generator unsubscribes from pub/sub in finally block (prevents Pitfall #3 memory leak)"
    - "SSE stream closes on terminal status (done/failed/needs_review) or client disconnect"
    - "GET /jobs/{id} returns job status JSON including segments_done, segments_total, error_msg"
    - "GET /jobs returns last 50 jobs newest-first"
    - "GET /jobs/{id}/download streams the output file for done/needs_review jobs"
    - "GET /jobs/{id}/download returns 409 for non-terminal jobs"
  artifacts:
    - path: "backend/src/app/api/routes/jobs.py"
      provides: "GET /jobs, GET /jobs/{id}, GET /jobs/{id}/download"
      exports: ["router"]
    - path: "backend/src/app/api/routes/sse.py"
      provides: "GET /jobs/{id}/stream — EventSourceResponse with Redis pub/sub"
      exports: ["router"]
  key_links:
    - from: "backend/src/app/api/routes/sse.py stream_job_progress"
      to: "redis.pubsub().subscribe('job:{id}')"
      via: "SSE generator (RESEARCH.md §7)"
      pattern: "EventSourceResponse"
    - from: "backend/src/app/api/routes/sse.py"
      to: "finally: pubsub.unsubscribe + pubsub.aclose()"
      via: "Pitfall #3 pub/sub leak prevention"
      pattern: "finally"
---

<objective>
Implement the jobs API routes: job status (GET /jobs, GET /jobs/{id}), SSE progress stream
(GET /jobs/{id}/stream), and file download (GET /jobs/{id}/download).

Purpose: Frontend job status page and jobs list page consume these endpoints for real-time feedback
and file retrieval.
Output: jobs.py + sse.py fully wired. Unit tests for SSE behavior and job status responses.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- SSE endpoint (RESEARCH.md §7 exact pattern) -->
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
        await pubsub.aclose()

return EventSourceResponse(generator(), ping=15, headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"})
```

<!-- Job response shape (D-10) -->
<!-- Must include: id, status, stage, source_lang, target_lang, detected_lang, input_format,
     original_filename, segments_done, segments_total, retry_count, error_msg,
     has_tracked_changes, created_at, updated_at -->

<!-- Download: FileResponse with content-disposition filename="translated_{original_filename}" -->
<!-- Only available for status in ("done", "needs_review") -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Jobs Status + Download + SSE Stream Endpoints</name>
  <files>
    backend/src/app/api/routes/jobs.py
    backend/src/app/api/routes/sse.py
    backend/tests/api/test_sse.py
    backend/tests/api/test_jobs.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 7: SSE endpoint full pattern, Pitfall #3 pub/sub leak)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-09 SSE transport, D-10 payload shape, D-11 error surface)
    backend/src/app/services/job_service.py (get_job signature)
    backend/src/app/db/models.py (Job fields for response serialization)
    backend/src/app/api/dependencies.py (get_redis)
  </read_first>
  <action>
Create `backend/src/app/api/routes/jobs.py`:
```python
from __future__ import annotations
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.job_service import get_job

router = APIRouter()


def _job_to_dict(job) -> dict:
    """Serialize Job model to D-10 response dict."""
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
    """JOB-01: Return last 50 jobs, newest first (Jobs List Page)."""
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
    if not os.path.exists(job.output_path):
        raise HTTPException(status_code=404, detail="Output file has been deleted")

    download_name = f"translated_{job.original_filename}"
    return FileResponse(
        path=job.output_path,
        filename=download_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
```

Create `backend/src/app/api/routes/sse.py`:
```python
from __future__ import annotations
import json
import asyncio
from fastapi import APIRouter, Depends
from starlette.requests import Request
from sse_starlette import EventSourceResponse

from app.api.dependencies import get_redis

router = APIRouter()


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
```

Also update `backend/src/app/main.py` to import and include `sse.router`:
```python
from app.api.routes import health, upload, languages, glossaries, jobs, sse
# ...
app.include_router(jobs.router)
app.include_router(sse.router)
```

Write `backend/tests/api/test_sse.py` testing:
- SSE generator yields {"event": "progress", "data": ...} for published Redis message
- SSE generator stops on terminal status (done/failed)

Write `backend/tests/api/test_jobs.py` testing:
- GET /jobs/{id} returns 404 for unknown job_id
- GET /jobs/{id}/download returns 409 when job not done
  </action>
  <verify>
    <automated>
      grep -q "EventSourceResponse" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "ping=15" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "unsubscribe" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "finally" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "is_disconnected" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "X-Accel-Buffering" backend/src/app/api/routes/sse.py &amp;&amp;
      grep -q "status_code=409" backend/src/app/api/routes/jobs.py
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
| job_id in URL → file system | Client-provided job_id used in DB lookup; output_path from DB not from URL |
| SSE connection → Redis pub/sub | Each SSE connection opens a Redis pub/sub subscription |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-06b-01 | Elevation of Privilege | GET /jobs/{id}/download output_path | mitigate | output_path stored in DB by server; not user-supplied; os.path.exists check before FileResponse |
| T-06b-02 | Denial of Service | SSE pub/sub leak on abrupt disconnect | mitigate | finally block in generator always unsubscribes; CancelledError caught |
| T-06b-03 | Information Disclosure | error_msg in GET /jobs/{id} | accept | Internal PoC; error messages informational, no stack traces in API response |
| T-06b-04 | Denial of Service | Unlimited SSE connections per job_id | accept | Internal PoC; no rate limiting in Phase 1 |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/api/test_sse.py tests/api/test_jobs.py -v` — all pass
2. `grep -q "ping=15" backend/src/app/api/routes/sse.py` — passes
3. `grep -q "unsubscribe" backend/src/app/api/routes/sse.py` — passes (Pitfall #3 fixed)
4. `grep -q "status_code=409" backend/src/app/api/routes/jobs.py` — passes
5. After docker compose up: `curl http://localhost:8000/jobs` → `{"jobs": [...]}`
</verification>

<success_criteria>
- GET /jobs/{id}/stream returns EventSourceResponse with ping=15; unsubscribes in finally block
- GET /jobs/{id}/download returns FileResponse; 409 for non-terminal jobs
- GET /jobs returns list of jobs newest-first (limit 50)
- SSE stream closes on terminal status in payload
- No per-request Redis pub/sub leaks
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-06b-SUMMARY.md`
</output>
