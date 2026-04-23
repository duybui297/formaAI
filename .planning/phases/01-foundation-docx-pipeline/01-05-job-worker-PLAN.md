---
phase: 01-foundation-docx-pipeline
plan: "05"
type: execute
wave: 3
depends_on:
  - "02"
  - "03"
  - "04"
files_modified:
  - backend/src/app/services/__init__.py
  - backend/src/app/services/job_service.py
  - backend/src/app/workers/__init__.py
  - backend/src/app/workers/translate_worker.py
  - backend/tests/services/__init__.py
  - backend/tests/services/test_job_service.py
autonomous: true
requirements:
  - CORE-02
  - CORE-03
  - CORE-06
  - JOB-01
  - JOB-02
  - JOB-03
  - JOB-04
  - DOCX-03
  - DOCX-04
  - LANG-01

must_haves:
  truths:
    - "translate_job orchestrates: parse → batch-pack → translate (4-concurrent via Semaphore) → reassemble → mark done"
    - "CORE-06 retry wrapper retries on RateLimitError/5xx/ConnectionError, max 3 times, exponential backoff 2s/4s/8s"
    - "Worker publishes Redis pub/sub progress events after every batch (D-09/D-10 payload shape)"
    - "Failed jobs have error_msg set and per-job errors.log written"
    - "WorkerSettings references translate_job directly (not by string) per arq requirement"
    - "startup/shutdown lifecycle creates/closes llm_client, engine, redis"
  artifacts:
    - path: "backend/src/app/services/job_service.py"
      provides: "create_job(), update_job_status(), get_job() service functions"
      exports: ["create_job", "update_job_status", "get_job", "transition_to_running", "transition_to_done", "transition_to_failed"]
    - path: "backend/src/app/workers/translate_worker.py"
      provides: "translate_job arq function + WorkerSettings + startup/shutdown + CORE-06 retry"
      exports: ["WorkerSettings", "translate_job", "startup", "shutdown"]
  key_links:
    - from: "backend/src/app/workers/translate_worker.py translate_job"
      to: "redis.publish('job:{job_id}', json.dumps(payload))"
      via: "D-09/D-10 progress payload"
      pattern: "PUBLISH job:"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/pipeline/docx/extractor.py extract_segments"
      via: "parse stage"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/pipeline/docx/reassembler.py reassemble_docx"
      via: "reassemble stage"
    - from: "backend/src/app/workers/translate_worker.py"
      to: "backend/src/app/llm/translator.py translate_batch"
      via: "translate stage (via translate_batch_with_retry)"
---

<objective>
Implement job service (CRUD + state machine) and the arq translation worker (startup/shutdown lifecycle, CORE-06 retry, asyncio.Semaphore(4) concurrency, Redis progress publishing, error log writing). This plan wires the LLM core to the DOCX pipeline.

Purpose: This is the end-to-end orchestrator. After this plan, a DOCX job can be enqueued and translated.
Output: job_service.py + translate_worker.py fully implemented. Unit tests for job state transitions.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md
@.planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md
@.planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md

<interfaces>
<!-- Exact code patterns from RESEARCH.md §6 and AI-SPEC §4 -->

Worker lifecycle (RESEARCH.md §6):
```python
async def startup(ctx: dict) -> None:
    settings = get_settings()
    ctx["llm_client"] = make_llm_client(settings)
    ctx["engine"] = create_async_engine(str(settings.database_url.get_secret_value()), pool_size=5)
    ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
    ctx["redis"] = Redis.from_url(str(settings.redis_url), decode_responses=True)
    log.info("worker_started")

async def shutdown(ctx: dict) -> None:
    await ctx["llm_client"].close()
    await ctx["engine"].dispose()
    await ctx["redis"].aclose()

class WorkerSettings:
    functions = [translate_job]   # MUST be direct reference, not string (RESEARCH.md Pitfall #5)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
```

CORE-06 retry pattern (AI-SPEC §4):
```python
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0   # sleep = 2**attempt → 2s, 4s, 8s

async def translate_batch_with_retry(ctx, segments, source_lang, target_lang, glossary, job_id, batch_id):
    for attempt in range(_MAX_RETRIES):
        try:
            return await translate_batch(client=ctx["llm_client"], ...)
        except RateLimitError: await asyncio.sleep(_BACKOFF_BASE ** (attempt+1))
        except APIStatusError as exc:
            if exc.status_code < 500: raise   # 4xx except 429 not retried
            await asyncio.sleep(_BACKOFF_BASE ** (attempt+1))
        except APIConnectionError: await asyncio.sleep(_BACKOFF_BASE ** (attempt+1))
    raise RuntimeError(f"All {_MAX_RETRIES} retries exhausted")
```

Concurrency pattern (AI-SPEC §4b.2):
```python
sem = asyncio.Semaphore(4)   # D-17: cap 4 concurrent DashScope calls
async def translate_all_batches(ctx, batches, ...):
    async def _call(batch_id, batch):
        async with sem:
            return await translate_batch_with_retry(ctx, segments=batch, ...)
    return list(await asyncio.gather(*[_call(i, b) for i, b in enumerate(batches)]))
```

Progress event shape (D-10):
```json
{"status": "running", "stage": "translate",
 "segments_done": 47, "segments_total": 210,
 "current_batch": 5, "retry_count": 0,
 "last_message": "Translating batch 5/23"}
```
Published via: await redis.publish(f"job:{job_id}", json.dumps(payload))

Job status transitions (RESEARCH.md §6):
  queued → running → done
              ↓
           failed (after 3 retries exhausted)
              ↓
         needs_review (if segment-level review flags set)

Error log (D-04, D-11): append errors to .data/jobs/{job_id}/errors.log
File paths: .data/jobs/{job_id}/source.{ext}, output.{ext}
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Job Service (CRUD + State Machine)</name>
  <files>
    backend/src/app/services/__init__.py
    backend/src/app/services/job_service.py
    backend/tests/services/__init__.py
    backend/tests/services/test_job_service.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 6: job state machine)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-04 file layout, D-10 payload shape)
    backend/src/app/db/models.py (Job model, JobStatus, JobStage enums)
    backend/tests/conftest.py (db_session fixture)
  </read_first>
  <behavior>
    - test_create_job_inserts_row: create_job(...) → job in DB with status=queued
    - test_transition_to_running_updates_status: job is queued → after transition status=running, stage=parse
    - test_transition_to_done_sets_output_path: transition_to_done(job_id, output_path) → job.output_path set, status=done
    - test_transition_to_failed_sets_error_msg: transition_to_failed(job_id, "error") → job.error_msg set, status=failed
    - test_get_job_returns_none_for_unknown_id: get_job("nonexistent") → None
    - test_update_progress_increments_segments_done: update_job_progress(job_id, done=5, total=10) → job.segments_done=5
  </behavior>
  <action>
Create `backend/src/app/services/__init__.py` (empty).
Create `backend/tests/services/__init__.py` (empty).

Create `backend/src/app/services/job_service.py`:
```python
from __future__ import annotations
import os
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Job, Segment, JobStatus, JobStage


async def create_job(
    session: AsyncSession,
    source_lang: str,
    target_lang: str,
    input_format: str,
    input_path: str,
    original_filename: str,
    has_tracked_changes: bool = False,
    tracked_changes_action: str | None = None,
) -> Job:
    """Create a new Job row with status=queued."""
    job = Job(
        source_lang=source_lang,
        target_lang=target_lang,
        input_format=input_format,
        input_path=input_path,
        original_filename=original_filename,
        has_tracked_changes=has_tracked_changes,
        tracked_changes_action=tracked_changes_action,
        status=JobStatus.queued,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def get_job(session: AsyncSession, job_id: str) -> Job | None:
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def transition_to_running(session: AsyncSession, job_id: str) -> None:
    job = await get_job(session, job_id)
    if job:
        job.status = JobStatus.running
        job.stage = JobStage.parse
        await session.commit()


async def update_job_progress(
    session: AsyncSession,
    job_id: str,
    segments_done: int,
    segments_total: int,
    current_batch: int,
    retry_count: int,
    stage: JobStage = JobStage.translate,
) -> None:
    """Update job progress columns without changing status."""
    job = await get_job(session, job_id)
    if job:
        job.segments_done = segments_done
        job.segments_total = segments_total
        job.retry_count = retry_count
        job.stage = stage
        await session.commit()


async def transition_to_done(
    session: AsyncSession,
    job_id: str,
    output_path: str,
    detected_lang: str | None = None,
) -> None:
    job = await get_job(session, job_id)
    if job:
        job.status = JobStatus.done
        job.stage = JobStage.done
        job.output_path = output_path
        if detected_lang:
            job.detected_lang = detected_lang
        await session.commit()


async def transition_to_failed(
    session: AsyncSession,
    job_id: str,
    error_msg: str,
) -> None:
    job = await get_job(session, job_id)
    if job:
        job.status = JobStatus.failed
        job.stage = JobStage.failed
        job.error_msg = error_msg
        await session.commit()


def append_error_log(data_dir: str, job_id: str, message: str) -> None:
    """D-11: Append error to per-job errors.log (durable, not in DB)."""
    log_path = os.path.join(data_dir, "jobs", job_id, "errors.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{datetime.utcnow().isoformat()} {message}\n")
```
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      uv run pytest tests/services/test_job_service.py -v --no-header 2>&amp;1 | tail -5
    </automated>
  </verify>
  <done>
    All job service tests pass.
    create_job inserts row with status=queued.
    transition_to_done, transition_to_failed, transition_to_running update correct columns.
    get_job returns None for unknown IDs.
    append_error_log creates file at .data/jobs/{job_id}/errors.log.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: arq Translation Worker (translate_worker.py)</name>
  <files>
    backend/src/app/workers/__init__.py
    backend/src/app/workers/translate_worker.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 4: core pattern translate_worker startup/shutdown, CORE-06 retry wrapper, asyncio.gather concurrency)
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (translate_worker.py section)
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-04 file layout, D-09 SSE payload, D-10 progress shape, D-17 concurrency)
    backend/src/app/services/job_service.py (transition functions)
    backend/src/app/pipeline/docx/extractor.py (extract_segments signature)
    backend/src/app/pipeline/docx/reassembler.py (reassemble_docx signature)
    backend/src/app/llm/token_budget.py (pack_into_batches signature)
  </read_first>
  <action>
Create `backend/src/app/workers/__init__.py` (empty).

Create `backend/src/app/workers/translate_worker.py`:

```python
from __future__ import annotations
import asyncio
import json
import os
import structlog
from pathlib import Path
from openai import RateLimitError, APIStatusError, APIConnectionError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import configure_logging, bind_job_id, clear_job_id
from app.db.models import JobStage
from app.llm.client import make_llm_client
from app.llm.translator import translate_batch
from app.llm.token_budget import pack_into_batches, SegmentTooLargeError
from app.pipeline.docx.extractor import extract_segments
from app.pipeline.docx.reassembler import reassemble_docx
from app.pipeline.docx.tracked import has_tracked_changes, strip_tracked_changes
from app.services.job_service import (
    get_job, transition_to_running, transition_to_done,
    transition_to_failed, update_job_progress, append_error_log
)

log = structlog.get_logger()

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0   # sleep = 2.0 ** attempt → 2s, 4s, 8s (AI-SPEC §4)


# ---------------------------------------------------------------------------
# arq worker lifecycle (RESEARCH.md §6 exact pattern)
# ---------------------------------------------------------------------------
async def startup(ctx: dict) -> None:
    configure_logging()
    settings = get_settings()
    ctx["settings"] = settings
    ctx["llm_client"] = make_llm_client(settings)
    ctx["engine"] = create_async_engine(
        settings.database_url.get_secret_value(), pool_size=5
    )
    ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
    ctx["redis"] = Redis.from_url(settings.redis_url, decode_responses=True)
    log.info("worker_started")


async def shutdown(ctx: dict) -> None:
    await ctx["llm_client"].close()
    await ctx["engine"].dispose()
    await ctx["redis"].aclose()
    log.info("worker_stopped")


# ---------------------------------------------------------------------------
# CORE-06: retry wrapper (AI-SPEC §4 exact pattern)
# ---------------------------------------------------------------------------
async def translate_batch_with_retry(
    ctx: dict,
    segments: list[str],
    source_lang: str,
    target_lang: str,
    glossary: dict[str, str] | None,
    job_id: str,
    batch_id: int,
) -> list[str]:
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            return await translate_batch(
                client=ctx["llm_client"],
                segments=segments,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary=glossary,
            )
        except RateLimitError as exc:
            last_exc = exc
            wait = _BACKOFF_BASE ** (attempt + 1)
            log.warning("rate_limit_retry", job_id=job_id, batch=batch_id,
                        attempt=attempt + 1, wait_s=wait)
            await asyncio.sleep(wait)
        except APIStatusError as exc:
            if exc.status_code < 500:
                raise   # 4xx (not 429) — fail immediately
            last_exc = exc
            wait = _BACKOFF_BASE ** (attempt + 1)
            log.warning("server_error_retry", job_id=job_id, batch=batch_id,
                        status=exc.status_code, attempt=attempt + 1, wait_s=wait)
            await asyncio.sleep(wait)
        except APIConnectionError as exc:
            last_exc = exc
            wait = _BACKOFF_BASE ** (attempt + 1)
            log.warning("connection_retry", job_id=job_id, batch=batch_id,
                        attempt=attempt + 1, wait_s=wait)
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"All {_MAX_RETRIES} retries exhausted for job={job_id} batch={batch_id}"
    ) from last_exc


async def _publish_progress(
    redis: Redis,
    job_id: str,
    status: str,
    stage: str,
    segments_done: int,
    segments_total: int,
    current_batch: int,
    retry_count: int,
    last_message: str,
    error: dict | None = None,
) -> None:
    """Publish D-10 payload to Redis pub/sub for SSE streaming."""
    payload: dict = {
        "status": status,
        "stage": stage,
        "segments_done": segments_done,
        "segments_total": segments_total,
        "current_batch": current_batch,
        "retry_count": retry_count,
        "last_message": last_message,
    }
    if error:
        payload["error"] = error
    await redis.publish(f"job:{job_id}", json.dumps(payload))


# ---------------------------------------------------------------------------
# Main job function (arq entry point)
# ---------------------------------------------------------------------------
async def translate_job(ctx: dict, job_id: str) -> None:
    """
    arq job function. Orchestrates: parse → batch → translate → reassemble.
    D-17: asyncio.Semaphore(4) caps concurrent DashScope calls per job.
    """
    settings = ctx["settings"]
    redis = ctx["redis"]

    bind_job_id(job_id)
    try:
        async with ctx["session_factory"]() as session:
            await _run_translation(ctx, session, job_id, settings, redis)
    except Exception as exc:
        log.exception("translate_job_fatal", job_id=job_id, error=str(exc))
    finally:
        clear_job_id()


async def _run_translation(ctx, session, job_id, settings, redis):
    from docx import Document

    data_dir = settings.data_dir
    job = await get_job(session, job_id)
    if not job:
        log.error("job_not_found", job_id=job_id)
        return

    await transition_to_running(session, job_id)
    await _publish_progress(redis, job_id, "running", "parse", 0, 0, 0, 0, "Parsing document...")

    try:
        # -- PARSE STAGE --
        doc = Document(job.input_path)

        # D-13: handle tracked changes if action is set
        if job.has_tracked_changes and job.tracked_changes_action == "strip":
            doc = strip_tracked_changes(doc)

        segments = extract_segments(doc, job_id)
        if not segments:
            await transition_to_done(session, job_id, output_path="")
            await _publish_progress(redis, job_id, "done", "done", 0, 0, 0, 0, "No translatable content found")
            return

        segments_total = len(segments)
        await update_job_progress(session, job_id, 0, segments_total, 0, 0, JobStage.translate)
        await _publish_progress(redis, job_id, "running", "translate", 0, segments_total, 0, 0,
                                 f"Starting translation of {segments_total} segments...")

        # -- BATCH PACK --
        source_texts = [seg.source_text for seg in segments]
        batches = pack_into_batches(
            source_texts,
            budget_tokens=settings.token_budget,
            segment_ids=[seg.id for seg in segments],
        )

        # -- TRANSLATE STAGE (asyncio.Semaphore(4) per D-17) --
        sem = asyncio.Semaphore(settings.worker_concurrency)
        translated_map: dict[str, str] = {}  # segment_id → translated_text
        segments_done = 0
        total_retry_count = 0
        seg_offset = 0

        async def _translate_one_batch(batch_id: int, batch_texts: list[str], batch_segs):
            nonlocal segments_done, total_retry_count
            async with sem:
                results = await translate_batch_with_retry(
                    ctx=ctx,
                    segments=batch_texts,
                    source_lang=job.source_lang,
                    target_lang=job.target_lang,
                    glossary=None,  # Phase 1: no glossary (D-15)
                    job_id=job_id,
                    batch_id=batch_id,
                )
                for seg, text in zip(batch_segs, results):
                    translated_map[seg.id] = text
                segments_done += len(batch_texts)
                await update_job_progress(
                    session, job_id, segments_done, segments_total,
                    batch_id, total_retry_count, JobStage.translate
                )
                await _publish_progress(
                    redis, job_id, "running", "translate",
                    segments_done, segments_total, batch_id, total_retry_count,
                    f"Translating batch {batch_id + 1}/{len(batches)}"
                )

        # Map batches back to segments
        batch_seg_groups = []
        offset = 0
        for batch in batches:
            batch_seg_groups.append(segments[offset:offset + len(batch)])
            offset += len(batch)

        await asyncio.gather(*[
            _translate_one_batch(i, batch, batch_segs)
            for i, (batch, batch_segs) in enumerate(zip(batches, batch_seg_groups))
        ])

        # -- REASSEMBLE STAGE --
        await _publish_progress(redis, job_id, "running", "reassemble",
                                  segments_done, segments_total, len(batches), 0, "Reassembling document...")
        doc = reassemble_docx(doc, segments, translated_map)

        output_path = os.path.join(data_dir, "jobs", job_id, "output.docx")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)

        await transition_to_done(session, job_id, output_path=output_path)
        await _publish_progress(redis, job_id, "done", "done",
                                  segments_total, segments_total, len(batches), 0, "Translation complete")

    except SegmentTooLargeError as exc:
        msg = str(exc)
        append_error_log(data_dir, job_id, msg)
        await transition_to_failed(session, job_id, error_msg=msg)
        await _publish_progress(redis, job_id, "failed", "failed", 0, 0, 0, 0, msg,
                                  error={"code": "SEGMENT_TOO_LARGE", "message": msg, "failing_segments": []})

    except Exception as exc:
        msg = f"Translation failed: {exc}"
        append_error_log(data_dir, job_id, msg)
        await transition_to_failed(session, job_id, error_msg=msg)
        await _publish_progress(redis, job_id, "failed", "failed", 0, 0, 0, 0, msg,
                                  error={"code": "TRANSLATION_ERROR", "message": msg, "failing_segments": []})
        raise


class WorkerSettings:
    # MUST be direct reference, not string (RESEARCH.md Pitfall #5)
    functions = [translate_job]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
```
  </action>
  <verify>
    <automated>
      grep -q "class WorkerSettings" backend/src/app/workers/translate_worker.py &amp;&amp;
      grep -q "functions = \[translate_job\]" backend/src/app/workers/translate_worker.py &amp;&amp;
      grep -q "Semaphore" backend/src/app/workers/translate_worker.py &amp;&amp;
      grep -q "CORE-06\|_MAX_RETRIES" backend/src/app/workers/translate_worker.py &amp;&amp;
      grep -q "PUBLISH\|redis.publish" backend/src/app/workers/translate_worker.py &amp;&amp;
      grep -q "errors.log" backend/src/app/workers/translate_worker.py
    </automated>
  </verify>
  <done>
    WorkerSettings has functions=[translate_job] (direct reference, not string).
    translate_job calls extract_segments → pack_into_batches → asyncio.gather with Semaphore(settings.worker_concurrency).
    translate_batch_with_retry retries RateLimitError/5xx/ConnectionError up to _MAX_RETRIES=3 with 2s/4s/8s backoff.
    Progress published to Redis pub/sub `job:{job_id}` after every batch with D-10 payload shape.
    Failed jobs write to errors.log and call transition_to_failed with human-readable error_msg.
    startup() creates llm_client + engine + session_factory + redis; shutdown() closes all.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| job_id parameter → file system | job_id is UUID; used in path construction; must not allow traversal |
| worker → DashScope | Retry loop bounded at 3 attempts; cannot hold worker slot indefinitely |
| arq job queue → worker | Job IDs come from Redis queue; validated against DB before processing |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-01 | Elevation of Privilege | data_dir + job_id path construction | mitigate | job_id is a UUID (uuid4); os.path.join(data_dir, "jobs", job_id, ...) — UUID cannot contain ".." traversal |
| T-05-02 | Denial of Service | CORE-06 retry loop | mitigate | _MAX_RETRIES=3 hard cap; exponential backoff bounded at 8s; arq max_jobs=10 caps concurrent workers |
| T-05-03 | Tampering | translate_batch result before write-back | mitigate | CORE-03 assertion in translate_batch raises before any reassembly occurs |
| T-05-04 | Denial of Service | asyncio.gather with all batches failing simultaneously | mitigate | Each batch retries independently; exception propagates to _run_translation catch block → job fails gracefully |
</threat_model>

<verification>
After all tasks complete:
1. `cd backend && uv run pytest tests/services/test_job_service.py -v` — all tests pass
2. `grep -q "functions = \[translate_job\]" backend/src/app/workers/translate_worker.py` — passes
3. `grep -q "asyncio.Semaphore" backend/src/app/workers/translate_worker.py` — passes
4. `grep -q "_MAX_RETRIES = 3" backend/src/app/workers/translate_worker.py` — passes
5. `grep -q "redis.publish" backend/src/app/workers/translate_worker.py` — passes
</verification>

<success_criteria>
- WorkerSettings.functions = [translate_job] (direct reference)
- translate_job calls extract_segments → pack_into_batches → asyncio.Semaphore(4) → translate_batch_with_retry → reassemble_docx
- CORE-06 retry: RateLimitError/APIStatusError(5xx)/APIConnectionError retried 3x with 2s/4s/8s backoff; 4xx fails immediately
- Redis publishes D-10 payload after every batch
- Failed jobs write errors.log and set job.error_msg
- job_service functions handle all state transitions: queued → running → done/failed
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-05-SUMMARY.md`
</output>
