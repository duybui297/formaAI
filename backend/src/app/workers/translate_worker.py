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
- D-03 Phase 3: match/case dispatch routes pptx/pdf through their respective pipelines.
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

from sqlalchemy import update as sa_update
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.logging import bind_job_id, clear_job_id, configure_logging
from app.db.models import (  # Gap 1: ORM model for DB persistence
    FlagSeverity,
    FlagType,
    JobStage,
    JobStatus,
    Segment as SegmentORM,
    SegmentFlag,
)
from app.llm.client import make_llm_client
from app.llm.token_budget import SegmentTooLargeError, pack_into_batches
from app.llm.translator import translate_batch
from app.pipeline.docx.extractor import extract_run_segments, extract_segments
from app.pipeline.docx.reassembler import reassemble_docx, reassemble_docx_runs
from app.pipeline.docx.tracked import strip_tracked_changes
from app.services.glossary_service import load_glossary_terms_for_job, run_post_check
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
        # Disable asyncpg prepared-statement cache so post-migration DDL
        # doesn't poison cached plans (InvalidCachedStatementError).
        connect_args={"statement_cache_size": 0},
    )
    ctx["session_factory"] = async_sessionmaker(ctx["engine"], expire_on_commit=False)
    ctx["redis"] = Redis.from_url(settings.redis_url, decode_responses=True)

    # D-04-05: PPStructureV3 singleton for scanned_pdf jobs (D-04-15 model bake)
    # Import inside startup() to avoid module-level crash when paddleocr is absent (T-04-12)
    try:
        from paddleocr import PPStructureV3  # noqa: PLC0415
        ctx["ocr_pipeline"] = PPStructureV3(
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_seal_recognition=False,
            use_chart_recognition=False,
        )
        log.info("ppstructurev3_initialized")
    except ImportError:
        ctx["ocr_pipeline"] = None
        log.warning("paddleocr_not_available", msg="Scanned PDF jobs will fail at runtime")

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
    stage_progress: dict | None = None,
    low_confidence_pages: list[int] | None = None,
) -> None:
    """
    Publish D-10 progress payload to Redis pub/sub channel `job:{job_id}`.

    The SSE endpoint in the API service subscribes and forwards these events
    to the frontend via EventSourceResponse (D-09).

    D-04-x SSE: stage_progress adds {stage, current, total} substructure.
    D-04-02: low_confidence_pages lists page numbers with mean conf < 0.7.
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
    if stage_progress is not None:
        payload["stage_progress"] = stage_progress
    if low_confidence_pages is not None:
        payload["low_confidence_pages"] = low_confidence_pages
    await redis.publish(f"job:{job_id}", json.dumps(payload))


# ---------------------------------------------------------------------------
# Main job function (arq entry point)
# ---------------------------------------------------------------------------


async def translate_job(ctx: dict, job_id: str) -> None:
    """
    arq task function. Called by arq when a translation job is dequeued.

    Orchestrates the full pipeline:
      1. Parse: dispatch by format (docx/pptx/pdf), extract segments
      2. Batch: pack segments into token-budgeted batches (D-07)
      3. Translate: concurrent batch translation with CORE-06 retry (D-17)
      4. Reassemble: write translations back, save output file (D-04)

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
        # STAGE 1: Parse — dispatch by format (D-03 Phase 3 extension)
        # ----------------------------------------------------------------
        match job.input_format:
            case "docx":
                _doc = Document(job.input_path)
                # D-13: strip tracked changes before extraction if user chose strip
                if job.has_tracked_changes and job.tracked_changes_action == "strip":
                    _doc = strip_tracked_changes(_doc)
                segments = extract_run_segments(_doc, job_id)
                _format_ctx: dict = {"type": "docx", "doc": _doc}

            case "pptx":
                from pptx import Presentation as PPTXPresentation  # noqa: PLC0415
                from app.pipeline.pptx.extractor import extract_pptx_segments  # noqa: PLC0415
                _prs = PPTXPresentation(job.input_path)
                segments = extract_pptx_segments(_prs, job_id)
                log.info(
                    "pptx_extracted",
                    job_id=job_id,
                    slide_count=len(_prs.slides),
                    segment_count=len(segments),
                )
                _format_ctx = {"type": "pptx", "prs": _prs}

            case "pdf":
                import pymupdf  # noqa: PLC0415
                from app.pipeline.pdf.extractor import extract_pdf_segments  # noqa: PLC0415
                _pdf_doc = pymupdf.open(job.input_path)
                segments = extract_pdf_segments(_pdf_doc, job_id)
                log.info(
                    "pdf_extracted",
                    job_id=job_id,
                    page_count=len(_pdf_doc),
                    segment_count=len(segments),
                )
                _format_ctx = {"type": "pdf", "doc": _pdf_doc}

            case "scanned_pdf":
                import pymupdf  # noqa: PLC0415
                from app.pipeline.scanned_pdf.extractor import extract_scanned_pdf_segments  # noqa: PLC0415

                _pdf_doc = pymupdf.open(job.input_path)
                _pages_dir = os.path.join(settings.data_dir, "jobs", job_id, "pages")
                os.makedirs(_pages_dir, exist_ok=True)
                _ocr_pipeline = ctx.get("ocr_pipeline")
                if _ocr_pipeline is None:
                    raise RuntimeError(
                        "PaddleOCR pipeline not initialized. Is paddleocr installed?"
                    )

                _total_pages = len(_pdf_doc)
                _ocr_segments: list | None = None
                _low_conf_pages: list[int] = []

                for _attempt in range(3):  # OCR_MAX_RETRIES = 2 (D-04-30): 3 attempts total
                    try:
                        await _publish_progress(
                            redis, job_id, "running", JobStage.ocr,
                            0, _total_pages, 0, _attempt, "OCR starting",
                            stage_progress={"stage": "ocr", "current": 0, "total": _total_pages},
                        )
                        _ocr_segments, _low_conf_pages = await extract_scanned_pdf_segments(
                            _pdf_doc, job_id, _pages_dir, _ocr_pipeline,
                            dpi=settings.ocr_page_dpi,
                        )
                        break
                    except Exception as exc:
                        if _attempt == 2:
                            raise
                        _wait = 2.0 ** (_attempt + 1)
                        log.warning(
                            "ocr_stage_retry",
                            job_id=job_id,
                            attempt=_attempt + 1,
                            wait_s=_wait,
                            error=str(exc),
                        )
                        await asyncio.sleep(_wait)

                segments = _ocr_segments or []
                _format_ctx = {
                    "type": "scanned_pdf",
                    "doc": _pdf_doc,
                    "pages_dir": _pages_dir,
                    "low_conf_pages": _low_conf_pages,
                    "total_pages": _total_pages,
                }

            case _:
                raise ValueError(f"Unsupported format: {job.input_format!r}")

        if not segments:
            # Empty document — mark done with empty output path
            await transition_to_done(session, job_id, output_path="")
            await _publish_progress(
                redis, job_id, "done", "done", 0, 0, 0, 0,
                "No translatable content found"
            )
            return

        segments_total = len(segments)

        # GLOS-03: load glossary terms ONCE before translate loop
        # Returns {source_term: target_term} dict or None if no glossary attached
        glossary: dict[str, str] | None = await load_glossary_terms_for_job(
            session, job.glossary_id
        )
        if glossary:
            log.info("glossary_loaded", job_id=job_id, term_count=len(glossary))

        # ----------------------------------------------------------------
        # STAGE 2: Batch pack (D-07)
        # Phase 03.2: Split segments by kind before batch packing.
        # math_passthrough segments skip the LLM entirely — identity translation.
        # table_cell and text segments flow through pack_into_batches as before.
        # ----------------------------------------------------------------
        _translatable = [s for s in segments if getattr(s, "kind", "text") != "math_passthrough"]
        # Passthrough segments are "translated" by identity — count them as
        # already-done so the FE progress reaches 100% instead of stalling
        # at len(_translatable)/len(segments).
        passthrough_count = len(segments) - len(_translatable)
        batches = pack_into_batches(_translatable, budget_tokens=settings.token_budget)

        # Gap 1 fix: persist ORM Segment rows so run_post_check can UPDATE/INSERT against them.
        # segments here are app.pipeline.segment.Segment dataclass objects (not ORM). We create
        # ORM instances from them and commit once before the translate loop.
        # Phase 03.2: passthrough segments get source_text as their initial translated_text
        # so DB rows are immediately consistent (reassembler skips them anyway via kind check).
        orm_segments: list[SegmentORM] = [
            SegmentORM(
                id=seg.id,
                job_id=job_id,
                seq_in_job=seg.seq_in_job,
                source_text=seg.source_text,
                structural_position=seg.structural_position,
                is_comment=seg.is_comment,
                is_inserted=seg.is_inserted,
                is_deleted=seg.is_deleted,
                translated_text=seg.source_text if getattr(seg, "kind", "text") == "math_passthrough" else None,
                edited_text=None,
                expansion_ratio=None,
                run_index=seg.run_index,          # gap-closure 02-10: None for para-level, int for run-level
                run_group_size=seg.run_group_size,  # gap-closure 02-10: defaults to 1 in dataclass
                # Phase 4 OCR fields (D-04-26) — None for non-OCR segments
                confidence=getattr(seg, "confidence", None),
                region_bbox=(list(seg.region_bbox) if getattr(seg, "region_bbox", None) else None),
                region_label=getattr(seg, "region_label", None),
                # edited_source_text starts None; reviewer fills via PATCH (D-04-12)
                edited_source_text=None,
            )
            for seg in segments
        ]
        try:
            session.add_all(orm_segments)
            await session.commit()
            log.info("segments_persisted", job_id=job_id, count=segments_total)
        except IntegrityError:
            await session.rollback()
            log.warning(
                "segments_already_persisted_skipping",
                job_id=job_id,
                count=segments_total,
            )

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

        # Phase 03.2: pre-populate translated_map for math_passthrough segments.
        # getattr guard: Segment.kind exists after Plan 01; guard protects DOCX/PPTX
        # segments which also use this worker (they have kind="text" by default).
        for _seg in segments:
            if getattr(_seg, "kind", "text") == "math_passthrough":
                translated_map[_seg.id] = _seg.source_text

        # Map each batch back to its source Segment objects.
        # NOTE: batches were packed from _translatable (non-passthrough only),
        # so batch_seg_groups must index into _translatable, not segments.
        batch_seg_groups: list[list] = []
        offset = 0
        for batch in batches:
            batch_seg_groups.append(_translatable[offset : offset + len(batch)])
            offset += len(batch)

        # WR-01 fix: per-batch done counts (list indexed by batch_id) — avoids
        # nonlocal integer +=  race when concurrent coroutines read-add-write the
        # same value near an await boundary.
        batch_done_counts: list[int] = [0] * len(batch_seg_groups)

        async def _translate_one_batch(
            batch_id: int, batch_texts: list[str], batch_segs: list
        ) -> None:
            async with sem:
                results = await translate_batch_with_retry(
                    ctx=ctx,
                    segments=batch_texts,
                    source_lang=job.source_lang,
                    target_lang=job.target_lang,
                    glossary=glossary,  # GLOS-03: real glossary from DB (or None)
                    job_id=job_id,
                    batch_id=batch_id,
                )
                # WR-06 fix: only update the in-memory map here; DB writes are
                # moved outside the gather so all coroutines never share a session
                # concurrently (SQLAlchemy async sessions are not coroutine-safe).
                if len(results) != len(batch_segs):
                    log.warning(
                        "batch_result_count_mismatch",
                        job_id=job_id,
                        batch=batch_id,
                        expected=len(batch_segs),
                        got=len(results),
                    )
                for seg, translated in zip(batch_segs, results):
                    translated_map[seg.id] = translated

                # WR-01: record this batch's count at its own index (safe — one
                # writer per index), then compute running total for progress emit.
                # Phase 03.2: passthrough_count is added so progress reflects
                # all completed segments (LLM-translated + identity-passthrough).
                batch_done_counts[batch_id] = len(batch_texts)
                segments_done_now = sum(batch_done_counts) + passthrough_count
                await _publish_progress(
                    redis, job_id, "running", "translate",
                    segments_done_now, segments_total,
                    batch_id, 0,
                    f"Translating batch {batch_id + 1}/{len(batches)}"
                )

        await asyncio.gather(*[
            _translate_one_batch(i, [seg.source_text for seg in batch_segs], batch_segs)
            for i, batch_segs in enumerate(batch_seg_groups)
        ])

        # WR-06 fix: all DB writes happen sequentially here, after gather, on a
        # single session — no concurrent coroutines touching the session object.
        segments_done = sum(batch_done_counts) + passthrough_count
        for batch_id, batch_segs in enumerate(batch_seg_groups):
            for seg in batch_segs:
                translated = translated_map.get(seg.id)
                if translated is None:
                    continue
                # Gap 1: persist translated_text to DB
                await session.execute(
                    sa_update(SegmentORM)
                    .where(SegmentORM.id == seg.id)
                    .values(translated_text=translated)
                )
            await session.flush()

            # GLOS-04 + LAYOUT-01: post-translation check per batch
            # run_post_check is imported from glossary_service (Plan 03)
            # Writes overflow / glossary_violation / placeholder_mismatch / llm_refusal flags
            # Also stores expansion_ratio on each segment
            await run_post_check(
                session=session,
                batch_segs=batch_segs,
                translated_map={seg.id: translated_map[seg.id] for seg in batch_segs if seg.id in translated_map},
                glossary=glossary,
                source_lang=job.source_lang,
                target_lang=job.target_lang,
                expansion_thresholds=ctx["settings"].expansion_thresholds_dict,
                job_id=job_id,  # gap-closure 02-10: needed for compound PK WHERE + SegmentFlag.segment_job_id
            )

            await update_job_progress(
                session, job_id,
                segments_done, segments_total,
                batch_id, 0, JobStage.translate
            )

        # ----------------------------------------------------------------
        # STAGE 4: Reassemble + save output — dispatched by format (D-04)
        # ----------------------------------------------------------------
        await _publish_progress(
            redis, job_id, "running", "reassemble",
            segments_done, segments_total, len(batches), 0,
            "Reassembling document..."
        )

        _out_dir = os.path.join(data_dir, "jobs", job_id)
        os.makedirs(_out_dir, exist_ok=True)

        match _format_ctx["type"]:
            case "docx":
                _out_doc = reassemble_docx_runs(_format_ctx["doc"], segments, translated_map)
                output_path = os.path.join(_out_dir, "output.docx")
                _out_doc.save(output_path)

            case "pptx":
                from app.pipeline.pptx.reassembler import reassemble_pptx  # noqa: PLC0415
                # reassemble_pptx returns (Presentation, list[dict]) — unpack tuple
                _prs_out, _pptx_overflow = reassemble_pptx(
                    _format_ctx["prs"], segments, translated_map
                )
                output_path = os.path.join(_out_dir, "output.pptx")
                _prs_out.save(output_path)

                # Persist PPTX overflow + smartart flags
                #
                # M2 overflow vs auto-adjusted contract (UI-SPEC):
                #   FlagType.overflow + details.auto_adjusted=False → "OVERFLOW" warning badge (amber)
                #     Meaning: text expansion too large to safely auto-fit (shrink < 0.7); user must act.
                #   FlagType.overflow + details.auto_adjusted=True  → "AUTO-FIT" info badge (slate)
                #     Meaning: TEXT_TO_FIT_SHAPE applied successfully (shrink >= 0.7); informational only.
                # UI consumes details.auto_adjusted to differentiate badge rendering (plan 03-06).
                _pptx_flags: list[SegmentFlag] = []
                for _r in _pptx_overflow:
                    _seg_id = _r["segment_id"]
                    if _r.get("overflow"):
                        # Overflow — could not auto-fit safely (shrink factor < 0.7); warning
                        _pptx_flags.append(SegmentFlag(
                            segment_id=_seg_id,
                            segment_job_id=job_id,
                            flag_type=FlagType.overflow,
                            severity=FlagSeverity.warn,
                            details={"char_ratio": _r.get("char_ratio"), "auto_adjusted": False},
                        ))
                    elif _r.get("auto_adjusted"):
                        # Auto-fit applied successfully (shrink >= 0.7); informational
                        _pptx_flags.append(SegmentFlag(
                            segment_id=_seg_id,
                            segment_job_id=job_id,
                            flag_type=FlagType.overflow,
                            severity=FlagSeverity.info,
                            details={"char_ratio": _r.get("char_ratio"), "auto_adjusted": True},
                        ))

                # SmartArt: identify segments with .smartart in structural_position
                for _seg in segments:
                    if _seg.structural_position.endswith(".smartart"):
                        _pptx_flags.append(SegmentFlag(
                            segment_id=_seg.id,
                            segment_job_id=job_id,
                            flag_type=FlagType.smartart,
                            severity=FlagSeverity.warn,
                            details={"reason": "smartart_write_back_skipped"},
                        ))
                if _pptx_flags:
                    session.add_all(_pptx_flags)
                    await session.flush()

            case "pdf":
                _pdf_overflow_flags: list[dict] = []
                output_path = os.path.join(_out_dir, "output.pdf")
                from app.pipeline.pdf.reassembler import reassemble_pdf  # noqa: PLC0415
                reassemble_pdf(
                    _format_ctx["doc"], segments, translated_map,
                    output_path, _pdf_overflow_flags,
                )
                log.info(
                    "pdf_reassembled",
                    job_id=job_id,
                    overflow_count=sum(1 for f in _pdf_overflow_flags if f.get("overflow")),
                )

                # Persist PDF overflow + multi_column_degraded flags
                #
                # M2 overflow vs auto-adjusted contract (same as PPTX above):
                #   FlagType.overflow + details.auto_adjusted=False (or absent) → warning
                #     (insert_htmlbox could not fit text even at scale_low=0.7; spare_height < 0)
                #   FlagType.overflow + details.auto_adjusted=True → info
                #     (scaled but within 0.7 threshold)
                _pdf_db_flags: list[SegmentFlag] = []
                for _r in _pdf_overflow_flags:
                    _seg_id = _r["segment_id"]
                    _details = {k: v for k, v in _r.items() if k != "segment_id"}
                    if _r.get("overflow"):
                        # Overflow — insert_htmlbox returned spare_height < 0 at scale_low=0.7; warning
                        _pdf_db_flags.append(SegmentFlag(
                            segment_id=_seg_id,
                            segment_job_id=job_id,
                            flag_type=FlagType.overflow,
                            severity=FlagSeverity.warn,
                            details=_details,
                        ))
                    elif _r.get("auto_adjusted"):
                        # Auto-adjusted — insert_htmlbox scaled text down but it fit; informational
                        _pdf_db_flags.append(SegmentFlag(
                            segment_id=_seg_id,
                            segment_job_id=job_id,
                            flag_type=FlagType.overflow,
                            severity=FlagSeverity.info,
                            details=_details,
                        ))

                # multi_column_degraded: segments on degraded pages have "page.N.block.B" position
                # L3: "col" absent in structural_position == degraded page
                # (extractor writes page.N.block.B for degraded, page.N.col.C.block.B otherwise)
                # WR-02 fix: explicitly restrict to kind=="text" so table_cell segments
                # (whose positions contain "col") are excluded by kind, not by coincidence
                # of position format — guards against future format changes like "cell" instead of "col".
                _degraded_seg_ids = {
                    s.id for s in segments
                    if s.structural_position.startswith("page.")
                    and s.kind == "text"
                    and "col" not in s.structural_position
                }
                for _seg_id in _degraded_seg_ids:
                    _pdf_db_flags.append(SegmentFlag(
                        segment_id=_seg_id,
                        segment_job_id=job_id,
                        flag_type=FlagType.multi_column_degraded,
                        severity=FlagSeverity.info,
                        details={"reason": "3_or_more_columns_detected_flat_reading_order_applied"},
                    ))

                if _pdf_db_flags:
                    session.add_all(_pdf_db_flags)
                    await session.flush()

            case "scanned_pdf":
                from app.pipeline.scanned_pdf.composer import (  # noqa: PLC0415
                    compose_bilingual_pdf,
                    compose_translated_only_pdf,
                )
                from app.pipeline.scanned_pdf.segment_to_md import (  # noqa: PLC0415
                    segments_to_markdown,
                    md_to_docx,
                )
                _ocr_overflow_flags: list[dict] = []
                _scanned_pages_dir = _format_ctx["pages_dir"]
                _scanned_src_doc = _format_ctx["doc"]
                _scanned_total_pages = _format_ctx.get("total_pages", 1)

                for _attempt in range(3):  # COMPOSE_MAX_RETRIES = 2 (D-04-30): 3 attempts total
                    try:
                        await _publish_progress(
                            redis, job_id, "running", JobStage.compose,
                            0, _scanned_total_pages, 0, _attempt, "Composing outputs",
                            stage_progress={"stage": "compose", "current": 0, "total": _scanned_total_pages},
                        )
                        compose_bilingual_pdf(
                            segments,
                            translated_map,
                            _scanned_pages_dir,
                            os.path.join(_out_dir, "output.pdf"),
                            _ocr_overflow_flags,
                            _scanned_src_doc,
                        )
                        compose_translated_only_pdf(
                            segments,
                            translated_map,
                            os.path.join(_out_dir, "output-translated-only.pdf"),
                            _scanned_src_doc,
                        )
                        _md_text = segments_to_markdown(segments)
                        md_to_docx(_md_text, os.path.join(_out_dir, "output.docx"))
                        break
                    except Exception as exc:
                        if _attempt == 2:
                            raise
                        _wait = 2.0 ** (_attempt + 1)
                        log.warning(
                            "compose_stage_retry",
                            job_id=job_id,
                            attempt=_attempt + 1,
                            wait_s=_wait,
                            error=str(exc),
                        )
                        await asyncio.sleep(_wait)

                output_path = os.path.join(_out_dir, "output.pdf")

                # Persist compose overflow flags (mirrors pdf overflow flag pattern)
                _ocr_db_flags: list[SegmentFlag] = []
                for _r in _ocr_overflow_flags:
                    _seg_id = _r["segment_id"]
                    _details = {k: v for k, v in _r.items() if k != "segment_id"}
                    if _r.get("overflow"):
                        _ocr_db_flags.append(SegmentFlag(
                            segment_id=_seg_id,
                            segment_job_id=job_id,
                            flag_type=FlagType.overflow,
                            severity=FlagSeverity.warn,
                            details=_details,
                        ))
                if _ocr_db_flags:
                    session.add_all(_ocr_db_flags)
                    await session.flush()

                # D-04-23: needs_review from low-confidence OCR pages
                _low_conf_pages = _format_ctx.get("low_conf_pages", [])
                if _low_conf_pages:
                    job.status = JobStatus.needs_review
                    await session.flush()
                    log.info(
                        "scanned_pdf_needs_review",
                        job_id=job_id,
                        low_confidence_pages=_low_conf_pages,
                    )

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
        # Gap 2: roll back any in-flight transaction before calling transition_to_failed.
        # If run_post_check raised a FK violation (e.g. missing Segment rows), the session
        # is in PendingRollbackError state. transition_to_failed calls get_job() which
        # issues a SELECT — that would also raise. Rollback first.
        try:
            await session.rollback()
        except Exception:
            pass  # best-effort; if rollback itself fails, we still attempt the status update
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
    # job_timeout=1800s (30 min): JP doc with 346 segments at 1.2s pacing takes
    # ~8 min. Default arq timeout is 300s which kills large jobs mid-flight. Size
    # the cap for the biggest realistic document; actual runtime scales with pacing.
    job_timeout = 1800
    # Resolve Redis from Settings so worker connects to docker-compose `redis` host,
    # not arq's default localhost (which fails inside containers).
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
