# Module: services

## Purpose
Business-logic layer between API routes / arq workers and the DB + document pipeline. Holds Job state-machine transitions, glossary CRUD/import/post-checks, and idempotent export reassembly. Callers own the `AsyncSession` lifecycle.

## Files
| File | Responsibility |
|------|----------------|
| `job_service.py` | Job CRUD + state-machine transitions; per-job `errors.log` append |
| `glossary_service.py` | Glossary + term CRUD, CSV/TBX import, term loading, post-translation checks |
| `export_service.py` | Idempotent translated-output reassembly + download path resolution |

## Key operations

### job_service
- `create_job(...)`: inserts `Job` with `status=queued`; optional `glossary_id` FK (D-02-01), `user_id` FK (auth phase 2), tracked-changes metadata. Commits + refreshes.
- `get_job` / `get_job_for_user`: fetch by id, latter scoped to owner.
- State machine (all transitions idempotent — no-op on unknown `job_id`):
  - `transition_to_running` (JOB-02): `queued → running`, sets `stage=parse`.
  - `transition_to_done` (JOB-03): `running → done`, sets `stage=done`, `output_path`, optional `detected_lang` (D-16).
  - `transition_to_failed` (JOB-04): `running → failed`, sets `stage=failed`, `error_msg`.
  - Documented machine is `queued → running → done | failed` (no `needs_review` transition in this module; `needs_review` is an exportable status recognized by export_service).
- `update_job_progress`: updates `segments_done/total`, `retry_count`, `stage` (default `translate`) without changing status; mirrors Redis pub/sub state for SSE reconnects (D-10).
- `append_error_log` (D-11): appends timestamped line to `{data_dir}/jobs/{job_id}/errors.log` (D-04 layout); creates dir; never raises (best-effort, swallows `OSError`).

### glossary_service
- Glossary CRUD: `create_glossary`, `get_glossary`/`get_glossary_for_user`, `list_glossaries` (filter by lang pair + owner), `update_glossary_name`, `delete_glossary` (CASCADE deletes terms).
- Term CRUD: `create_term`, `update_term`, `delete_term`. Enforces ≥2-char terms (D-02-07); `(glossary_id, source_term)` unique (D-02-03) raised as `IntegrityError`.
- Import (GLOS-02): `parse_csv_glossary` (header-variant tolerant, `utf-8-sig` BOM strip), `parse_tbx_minimal` (TBX-Core tig/term + TBX-Basic ntig/termGrp/term, ElementTree). `import_csv_terms` bulk-inserts, pre-fetches existing `source_term`s to skip duplicates (avoids per-row rollback); returns `{imported, skipped_duplicates}`.
- `load_glossary_terms_for_job` (GLOS-03): worker helper returning `{source_term: target_term}`; `None` when no glossary or zero terms.
- `run_post_check` (GLOS-04 + LAYOUT-01): per-batch detectors writing `expansion_ratio` to segments and `SegmentFlag` rows (all `FlagSeverity.warn`): overflow (ratio > lang-pair threshold, default 1.5), glossary_violation (target term absent), placeholder_mismatch (`⟦T{n}⟧` token dropped), llm_refusal (output == input, source >8 chars, non-pure-ASCII). Uses compound PK `(job_id, id)` (gap-closure 02-10); single `add_all` + flush.

### export_service
- `export_job` (REV-05/06): idempotent reassembly; acquires per-`job_id` in-process `asyncio.Lock` (`WeakValueDictionary`, D-02-22; TODO v2 `pg_advisory_lock` for multi-worker). Requires status in `{done, needs_review}` else raises `ValueError`.
- DOCX path: loads segments ordered by `seq_in_job`, builds `translated_map` using `edited_text ?? translated_text` (explicit `None` check so empty-string edits respected), calls `reassemble_docx_runs`, atomic write (`tmp` → `os.replace`). Does not mutate segment rows.
- PPTX/PDF path: PoC pass-through — serves worker-written `{data_dir}/jobs/{job_id}/output.{ext}` as-is; edit re-application is a future feature.
- Output path: `{data_dir}/jobs/{job_id}/output.{ext}`.

## Inputs / outputs
- Input: `AsyncSession`, `data_dir`, ids/lang pairs/file bytes.
- Output: ORM model instances (`Job`, `Glossary`, `GlossaryTerm`), filesystem output paths (str), import summary dicts. Side effects: DB commits/flushes, files written under `data_dir`.

## Dependencies
- `sqlalchemy` async (`AsyncSession`, `select`, `update`, `IntegrityError`).
- `app.db.models`: `Job`, `JobStage`, `JobStatus`, `Glossary`, `GlossaryTerm`, `Segment`, `SegmentFlag`, `FlagType`, `FlagSeverity`.
- `app.pipeline.docx.reassembler.reassemble_docx_runs` (export DOCX).
- `python-docx` (`Document`), `structlog`, stdlib `csv`/`io`/`xml.etree.ElementTree`/`os`/`pathlib`/`asyncio`/`weakref`.
