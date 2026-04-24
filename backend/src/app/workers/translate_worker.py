"""
arq translation worker: startup/shutdown lifecycle + translate_job entry point.

Orchestrates: parse → batch-pack → translate (4-concurrent via Semaphore) → reassemble.

Key design decisions:
- CORE-06: retry wrapper retries RateLimitError/APIStatusError(5xx)/APIConnectionError
  up to _MAX_RETRIES=3 with exponential backoff 2s/4s/8s. 4xx errors fail immediately.
- D-17: asyncio.Semaphore(settings.worker_concurrency) caps per-job DashScope concurrency.
- D-10: progress published to Redis pub/sub `job:{job_id}` after every batch.
- D-11: errors.log written on failure for durable developer debugging.
- D-13: strip_tracked_changes() called before extraction when job.tracked_changes_action=="strip".
- WorkerSettings.functions must reference translate_job directly (RESEARCH.md Pitfall #5).
"""
from __future__ import annotations

import asyncio
import json
import os

import structlog
from arq.connections import RedisSettings
from docx import Document
from openai import APIConnectionError, APIStatusError, RateLimitError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.logging import bind_job_id, clear_job_id, configure_logging
from app.db.models import JobStage
from app.llm.client import make_llm_client
from app.llm.token_budget import SegmentTooLargeError, pack_into_batches
from app.llm.translator import translate_batch
from app.pipeline.docx.extractor import extract_segments
from app.pipeline.docx.reassembler import reassemble_docx
from app.pipeline.docx.tracked import strip_tracked_changes
from app.services.job_service import (
    append_error_log,
    get_job,
    transition_to_done,
    transition_to_failed,
    transition_to_running,
    update_job_progress,
)

log = structlog.get_logger()

# CORE-06: retry configuration (AI-SPEC §4)
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0  # sleep = 2.0 ** attempt → 2s, 4s, 8s


# ---------------------------------------------------------------------------
# arq worker lifecycle (RESEARCH.md §6)
# ---------------------------------------------------------------------------


async def startup(ctx: dict) -> None:
    """
    arq on_startup hook. Creates all shared resources and stores in ctx.

    Resources created:
    - llm_client: AsyncOpenAI pointed at DashScope intl (max_retries=0, CORE-06 owns retry)
    - engine: SQLAlchemy async engine with connection pool
    - session_factory: async_sessionmaker for per-job sessions
    - redis: Redis async client for pub/sub progress publishing (D-10)
    """
    configure_logging()
    settings = get_settings()
    ctx["settings"] = settings
    ctx["llm_client"] = make_llm_client(settings)
    ctx["engine"] = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=5,
        pool_pre_ping=True,
    )
    ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
    ctx["redis"] = Redis.from_url(settings.redis_url, decode_responses=True)
    log.info("worker_started")


async def shutdown(ctx: dict) -> None:
    """
    arq on_shutdown hook. Closes all shared resources cleanly.
    """
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
    """
    CORE-06: translate_batch with exponential-backoff retry.

    Retries on:
    - RateLimitError (429): always retry up to _MAX_RETRIES
    - APIStatusError with status_code >= 500: server error, retry
    - APIConnectionError: network issue, retry

    Does NOT retry:
    - APIStatusError with status_code 4xx (except 429): bad request, fail immediately

    Backoff: 2^(attempt+1) seconds → 2s, 4s, 8s (hard cap at 8s for 3 retries).
    """
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
            log.warning(
                "rate_limit_retry",
                job_id=job_id,
                batch=batch_id,
                attempt=attempt + 1,
                wait_s=wait,
            )
            await asyncio.sleep(wait)
        except APIStatusError as exc:
            if exc.status_code < 500:
                # 4xx (non-429): bad request — fail immediately, no retry
                raise
            last_exc = exc
            wait = _BACKOFF_BASE ** (attempt + 1)
            log.warning(
                "server_error_retry",
                job_id=job_id,
                batch=batch_id,
                status=exc.status_code,
                attempt=attempt + 1,
                wait_s=wait,
            )
            await asyncio.sleep(wait)
        except APIConnectionError as exc:
            last_exc = exc
            wait = _BACKOFF_BASE ** (attempt + 1)
            log.warning(
                "connection_retry",
                job_id=job_id,
                batch=batch_id,
                attempt=attempt + 1,
                wait_s=wait,
            )
            await asyncio.sleep(wait)

    raise RuntimeError(
        f"All {_MAX_RETRIES} retries exhausted for job={job_id} batch={batch_id}"
    ) from last_exc


# ---------------------------------------------------------------------------
# Progress publishing (D-10 payload shape)
# ---------------------------------------------------------------------------


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
    """
    Publish D-10 progress payload to Redis pub/sub channel `job:{job_id}`.

    The SSE endpoint in the API service subscribes and forwards these events
    to the frontend via EventSourceResponse (D-09).
    """
    payload: dict = {
        "status": status,
        "stage": stage,
        "segments_done": segments_done,
        "segments_total": segments_total,
        "current_batch": current_batch,
        "retry_count": retry_count,
        "last_message": last_message,
    }
    if error is not None:
        payload["error"] = error
    await redis.publish(f"job:{job_id}", json.dumps(payload))


# ---------------------------------------------------------------------------
# Main job function (arq entry point)
# ---------------------------------------------------------------------------


async def translate_job(ctx: dict, job_id: str) -> None:
    """
    arq task function. Called by arq when a translation job is dequeued.

    Orchestrates the full pipeline:
      1. Parse: load DOCX, optionally strip tracked changes (D-13), extract segments
      2. Batch: pack segments into token-budgeted batches (D-07)
      3. Translate: concurrent batch translation with CORE-06 retry (D-17)
      4. Reassemble: write translations back into DOCX, save output file (D-04)

    Progress is published to Redis after every batch (D-10).
    Failures write errors.log and mark job failed (D-11).
    """
    bind_job_id(job_id)
    try:
        async with ctx["session_factory"]() as session:
            await _run_translation(ctx, session, job_id)
    except Exception as exc:
        # Outer catch: session setup failure or unhandled exception from _run_translation
        # _run_translation already handles its own failures and logs them;
        # this is a safety net for infrastructure errors.
        log.exception("translate_job_fatal", job_id=job_id, error=str(exc))
    finally:
        clear_job_id()


async def _run_translation(ctx: dict, session, job_id: str) -> None:
    """
    Inner orchestration function. Separated from translate_job for testability.

    The session is owned by the caller (translate_job).
    """
    settings = ctx["settings"]
    redis = ctx["redis"]
    data_dir = settings.data_dir

    # Load job from DB
    job = await get_job(session, job_id)
    if job is None:
        log.error("job_not_found", job_id=job_id)
        return

    # JOB-02: queued → running
    await transition_to_running(session, job_id)
    await _publish_progress(
        redis, job_id, "running", "parse", 0, 0, 0, 0, "Parsing document..."
    )

    try:
        # ----------------------------------------------------------------
        # STAGE 1: Parse
        # ----------------------------------------------------------------
        doc = Document(job.input_path)

        # D-13: strip tracked changes before extraction if user chose strip
        if job.has_tracked_changes and job.tracked_changes_action == "strip":
            doc = strip_tracked_changes(doc)

        segments = extract_segments(doc, job_id)

        if not segments:
            # Empty document — mark done with empty output path
            await transition_to_done(session, job_id, output_path="")
            await _publish_progress(
                redis, job_id, "done", "done", 0, 0, 0, 0,
                "No translatable content found"
            )
            return

        segments_total = len(segments)

        # ----------------------------------------------------------------
        # STAGE 2: Batch pack (D-07)
        # ----------------------------------------------------------------
        batches = pack_into_batches(segments, budget_tokens=settings.token_budget)

        await update_job_progress(
            session, job_id, 0, segments_total, 0, 0, JobStage.translate
        )
        await _publish_progress(
            redis, job_id, "running", "translate", 0, segments_total, 0, 0,
            f"Starting translation of {segments_total} segments in {len(batches)} batches..."
        )

        # ----------------------------------------------------------------
        # STAGE 3: Translate — asyncio.Semaphore(worker_concurrency) per D-17
        # ----------------------------------------------------------------
        sem = asyncio.Semaphore(settings.worker_concurrency)
        translated_map: dict[str, str] = {}  # segment_id → translated_text
        segments_done = 0

        # Map each batch back to its source Segment objects
        batch_seg_groups: list[list] = []
        offset = 0
        for batch in batches:
            batch_seg_groups.append(segments[offset : offset + len(batch)])
            offset += len(batch)

        async def _translate_one_batch(
            batch_id: int, batch_texts: list[str], batch_segs: list
        ) -> None:
            nonlocal segments_done
            async with sem:
                results = await translate_batch_with_retry(
                    ctx=ctx,
                    segments=batch_texts,
                    source_lang=job.source_lang,
                    target_lang=job.target_lang,
                    glossary=None,  # Phase 1: no glossary (D-15 deferred to Phase 2)
                    job_id=job_id,
                    batch_id=batch_id,
                )
                for seg, translated in zip(batch_segs, results):
                    translated_map[seg.id] = translated
                segments_done += len(batch_texts)

                await update_job_progress(
                    session, job_id,
                    segments_done, segments_total,
                    batch_id, 0, JobStage.translate
                )
                await _publish_progress(
                    redis, job_id, "running", "translate",
                    segments_done, segments_total,
                    batch_id, 0,
                    f"Translating batch {batch_id + 1}/{len(batches)}"
                )

        await asyncio.gather(*[
            _translate_one_batch(i, [seg.source_text for seg in batch_segs], batch_segs)
            for i, batch_segs in enumerate(batch_seg_groups)
        ])

        # ----------------------------------------------------------------
        # STAGE 4: Reassemble + save output (D-04)
        # ----------------------------------------------------------------
        await _publish_progress(
            redis, job_id, "running", "reassemble",
            segments_done, segments_total, len(batches), 0,
            "Reassembling document..."
        )

        doc = reassemble_docx(doc, segments, translated_map)

        output_path = os.path.join(data_dir, "jobs", job_id, "output.docx")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc.save(output_path)

        # JOB-03: running → done
        await transition_to_done(session, job_id, output_path=output_path)
        await _publish_progress(
            redis, job_id, "done", "done",
            segments_total, segments_total, len(batches), 0,
            "Translation complete"
        )
        log.info(
            "translate_job_done", job_id=job_id, output_path=output_path,
            segments=segments_total, batches=len(batches)
        )

    except SegmentTooLargeError as exc:
        # D-08: oversized segment — fail gracefully with clear error
        msg = str(exc)
        append_error_log(data_dir, job_id, msg)
        await transition_to_failed(session, job_id, error_msg=msg)
        await _publish_progress(
            redis, job_id, "failed", "failed", 0, 0, 0, 0, msg,
            error={
                "code": "SEGMENT_TOO_LARGE",
                "message": msg,
                "failing_segments": [
                    {"id": exc.segment_id, "source_text": exc.source_text_excerpt, "batch_id": 0}
                ],
            }
        )
        log.error(
            "segment_too_large", job_id=job_id,
            segment_id=exc.segment_id, token_count=exc.token_count
        )

    except Exception as exc:
        # Unexpected failure: write error log, mark job failed, publish failed status
        msg = f"Translation failed: {exc}"
        append_error_log(data_dir, job_id, msg)
        await transition_to_failed(session, job_id, error_msg=msg)
        await _publish_progress(
            redis, job_id, "failed", "failed", 0, 0, 0, 0, msg,
            error={
                "code": "TRANSLATION_ERROR",
                "message": msg,
                "failing_segments": [],
            }
        )
        log.exception("translate_job_failed", job_id=job_id, error=str(exc))
        raise  # re-raise so arq marks the job as failed in its own queue


class WorkerSettings:
    """
    arq WorkerSettings.

    functions MUST reference translate_job directly (not by string).
    RESEARCH.md Pitfall #5: string references cause silent "function not found" failures.
    """

    functions = [translate_job]  # direct reference — NEVER use string
    on_startup = startup
    on_shutdown = shutdown
    # max_jobs=1: DashScope intl free tier has a tight QPS cap — running multiple
    # translate_job coroutines concurrently collapses into 429 storms that never
    # drain. One job at a time is the only reliable mode for large documents on
    # the free tier. Bump on paid tier.
    max_jobs = 1
    # Resolve Redis from Settings so worker connects to docker-compose `redis` host,
    # not arq's default localhost (which fails inside containers).
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
