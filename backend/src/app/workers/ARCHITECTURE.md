# Module: workers

## Purpose

arq async worker that runs translation jobs off the request path. Dequeues a job by id, drives the full pipeline (parse → batch-pack → translate → reassemble), persists segments/flags to Postgres, and publishes progress to Redis pub/sub for the SSE route to forward to the frontend.

## Files

| File | Responsibility |
|------|----------------|
| translate_worker.py | arq startup/shutdown lifecycle, `translate_job` entry point, retry wrapper, progress publishing, and the full parse/batch/translate/reassemble orchestration dispatched per format (docx, pptx, pdf, scanned_pdf). |

## WorkerSettings

- **functions** = `[translate_job]` — direct reference, never a string (string refs cause silent "function not found"; RESEARCH.md Pitfall #5).
- **max_jobs** = `1` — DashScope intl free-tier QPS cap is tight; concurrent jobs collapse into 429 storms that never drain. One job at a time is the only reliable mode on free tier; bump on paid tier. (Per-job concurrency is still parallel — see `worker_concurrency` Semaphore in translate stage.)
- **job_timeout** = `3600` (60 min) — sized for the largest realistic doc (1409-segment native PDF ≈ 28 min translate + ~2 min reassemble at ~1.2s pacing).
- **on_startup** = `startup`, **on_shutdown** = `shutdown`.
- **redis_settings** = `RedisSettings.from_dsn(get_settings().redis_url)` — resolves the docker-compose `redis` host instead of arq's default localhost (which fails in containers).

### startup(ctx) shared resources

- `ctx["settings"]` — app settings.
- `ctx["llm_client"]` — `AsyncOpenAI` pointed at DashScope intl, `max_retries=0` (CORE-06 owns retry).
- `ctx["engine"]` — SQLAlchemy async engine, `pool_size=5`, `pool_pre_ping=True`, `statement_cache_size=0` (avoids `InvalidCachedStatementError` after migration DDL).
- `ctx["session_factory"]` — `async_sessionmaker(expire_on_commit=False)`.
- `ctx["redis"]` — `redis.asyncio.Redis` for pub/sub progress (D-10).
- `ctx["ocr_pipeline"]` — PaddleOCR `PPStructureV3` singleton for `scanned_pdf` jobs (mobile det/rec models, table/formula/seal/chart pipelines disabled to cut memory ~3x). Imported inside startup so a missing paddleocr install doesn't crash module load; set to `None` with a warning if unavailable.

### shutdown(ctx)

Closes `llm_client`, disposes `engine`, closes `redis`.

## Job execution flow

`translate_job(ctx, job_id)` binds job_id to logging, opens a session, delegates to `_run_translation`, and clears job_id in `finally`. The outer `try/except` is an infrastructure-error safety net (`_run_translation` handles its own domain failures).

`_run_translation(ctx, session, job_id)`:

1. **Load job** via `get_job`; return early if not found.
2. **Status queued → running** (`transition_to_running`), publish `parse` progress.
3. **Stage 1 — Parse** via `match job.input_format`:
   - `docx`: open `Document`, optionally `strip_tracked_changes` (D-13 when `tracked_changes_action == "strip"`), `extract_run_segments`.
   - `pptx`: open `Presentation`, `extract_pptx_segments`.
   - `pdf`: `pymupdf.open`, `extract_pdf_segments`.
   - `scanned_pdf`: `pymupdf.open`, render pages dir, `extract_scanned_pdf_segments` via OCR pipeline with up to 3 attempts (OCR_MAX_RETRIES=2) and `ocr` stage progress; collects `low_conf_pages`.
   - default: raise `ValueError` (unsupported format).
   - Empty segments → `transition_to_done(output_path="")`, publish done, return.
4. **Load glossary** once via `load_glossary_terms_for_job(session, job.glossary_id)` → `{src: tgt}` or None.
5. **Stage 2 — Batch pack** (D-07): split off `math_passthrough` segments (identity-translated, counted as already done), `pack_into_batches(_translatable, budget_tokens=settings.token_budget)`. Persist ORM `Segment` rows (one commit before the loop; `IntegrityError` → rollback + skip as already-persisted). Publish `translate` progress.
6. **Stage 3 — Translate** (D-17): `asyncio.Semaphore(settings.worker_concurrency)` caps concurrent DashScope calls within the job. Each batch runs `_translate_one_batch` → `translate_batch_with_retry`, fills `translated_map` in memory only (sessions are not coroutine-safe), records per-batch done counts in a list indexed by batch_id (WR-01: avoids `+=` race), publishes per-batch progress. `asyncio.gather` runs all batches.
7. **Persist translations** sequentially after gather (single session, no concurrent access): `UPDATE Segment.translated_text` per segment (compound PK `(id, job_id)` in WHERE), `run_post_check` per batch (overflow / glossary_violation / placeholder_mismatch / llm_refusal flags + expansion_ratio), `update_job_progress`.
8. **Stage 4 — Reassemble + save** via `match _format_ctx["type"]`, writing to `data_dir/jobs/{job_id}/`:
   - `docx`: `reassemble_docx_runs` → `output.docx`.
   - `pptx`: `reassemble_pptx` → `output.pptx`; persist overflow flags (warn vs info via `auto_adjusted`) and `smartart` flags.
   - `pdf`: `reassemble_pdf` → `output.pdf`; persist overflow flags and `multi_column_degraded` flags (positions lacking `col` on `kind=="text"` segments).
   - `scanned_pdf`: `compose_bilingual_pdf` + `compose_translated_only_pdf` + markdown→`output.docx`, up to 3 attempts (COMPOSE_MAX_RETRIES=2) with `compose` stage progress; persist compose-overflow and `ocr_page_error` flags; if `low_conf_pages`, set `job.low_confidence_pages` and `status = needs_review`.
9. **Status running → done** (`transition_to_done`, output_path), publish `done`.

On failure: `SegmentTooLargeError` (D-08) and generic `Exception` both write `errors.log` (`append_error_log`), roll back the session (Gap 2 — clears `PendingRollbackError` before `transition_to_failed` issues its SELECT), mark `transition_to_failed`, and publish a `failed` payload with an `error` object. The generic handler **re-raises so arq also marks the job failed** in its own queue.

## Progress reporting

`_publish_progress(...)` builds the D-10 payload and `redis.publish(f"job:{job_id}", json.dumps(payload))`. The API service's SSE endpoint subscribes to `job:{job_id}` and forwards events to the frontend via `EventSourceResponse` (D-09).

Payload shape:

```
{
  "status":         "running" | "done" | "failed",
  "stage":          "parse" | "translate" | "reassemble" | "ocr" | "compose" | "done" | "failed",
  "segments_done":  int,
  "segments_total": int,
  "current_batch":  int,
  "retry_count":    int,
  "last_message":   str,
  "error":          { code, message, failing_segments } | absent,
  "stage_progress": { stage, current, total } | absent,   # OCR / compose substages
  "low_confidence_pages": [int] | absent                  # D-04-02
}
```

## Retry

`translate_batch_with_retry(ctx, segments, source_lang, target_lang, glossary, job_id, batch_id)` (CORE-06):

- Loops up to `_MAX_RETRIES = 3` calling `translate_batch`.
- **Retries** `RateLimitError` (429), `APIStatusError` with `status_code >= 500`, and `APIConnectionError`.
- **Does not retry** `APIStatusError` with 4xx (non-429) — re-raised immediately.
- Backoff `_BACKOFF_BASE ** (attempt + 1)` = 2s / 4s / 8s exponential.
- All retries exhausted → raises `RuntimeError` chained from the last exception.

Note OCR and compose stages have their own separate in-stage retry loops (3 attempts, 2^(attempt+1) backoff), independent of this LLM-call wrapper.

## Dependencies

- **arq** — `RedisSettings`, `WorkerSettings`, lifecycle hooks.
- **redis.asyncio** — pub/sub progress publishing.
- **sqlalchemy (async)** — `create_async_engine`, `async_sessionmaker`, `update`; `IntegrityError`.
- **openai** — exception types (`RateLimitError`, `APIStatusError`, `APIConnectionError`); client built by `app.llm.client.make_llm_client`.
- **app.llm** — `translator.translate_batch`, `token_budget.pack_into_batches` / `SegmentTooLargeError`.
- **app.pipeline** — docx (`extractor`, `reassembler`, `tracked`), pptx, pdf, scanned_pdf (extractor, composer, segment_to_md) — imported lazily per format.
- **app.services** — `job_service` (get_job, transition_to_running/done/failed, update_job_progress, append_error_log), `glossary_service` (load_glossary_terms_for_job, run_post_check).
- **app.db.models** — `Segment`, `SegmentFlag`, `JobStage`, `JobStatus`, `FlagType`, `FlagSeverity`.
- **app.core** — `config.get_settings`, `logging` (configure_logging, bind_job_id, clear_job_id).
- **paddleocr** — `PPStructureV3` (optional; scanned_pdf only).
