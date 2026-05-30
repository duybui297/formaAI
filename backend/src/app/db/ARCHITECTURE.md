# Module: db

## Purpose
SQLAlchemy 2.0 async ORM models, engine/session factory, and Alembic migrations for the AI Translation backend. PK strategy uses `String(36)` UUIDs (not native PG UUID) for SQLite test compat.

## Session (session.py)
- Module-level async engine via `create_async_engine`, created once at import time.
- Engine kwargs: `echo=False`; for non-sqlite URLs adds `pool_size=5`, `max_overflow=10`, and `connect_args={"statement_cache_size": 0}` (disables asyncpg prepared-statement cache to avoid `InvalidCachedStatementError` after Alembic column alters).
- `SessionFactory = async_sessionmaker(engine, expire_on_commit=False)` — avoids lazy-load errors after commit in async context.
- `get_session()` — FastAPI dependency; async generator yielding `AsyncSession`, auto-closes after response.
- Note: arq workers create their own `create_async_engine` pool in worker `startup()`; this module-level engine serves the FastAPI app and tests.

## Models (models.py)
| Model | Table | Key columns | Relationships |
|-------|-------|-------------|---------------|
| Job | jobs | id (String36 PK), status (JobStatus), stage (JobStage), source_lang, target_lang, detected_lang, input_format, input_path, output_path, original_filename, segments_done/total, retry_count, error_msg, has_tracked_changes, tracked_changes_action, glossary_id (FK glossaries SET NULL), low_confidence_pages (JSON), user_id (FK users CASCADE, indexed), created_at, updated_at | segments (1:N, selectin) |
| Segment | segments | compound PK (id String16 + job_id String36 FK jobs CASCADE), seq_in_job, source_text, translated_text, structural_position, is_comment, is_inserted, is_deleted, run_index, run_group_size, edited_text, expansion_ratio, confidence, region_bbox (JSON), region_label, edited_source_text, created_at | job (N:1), flags (1:N, selectin) |
| Glossary | glossaries | id (String36 PK), name, source_lang, target_lang, user_id (FK users CASCADE, indexed), created_at, updated_at | terms (1:N, selectin, cascade all/delete-orphan) |
| GlossaryTerm | glossary_terms | id (String36 PK), glossary_id (FK glossaries CASCADE, indexed), source_term, target_term, notes, created_at; UniqueConstraint(glossary_id, source_term) | glossary (N:1) |
| SegmentFlag | segment_flags | id (String36 PK), segment_id (String16), segment_job_id (String36), flag_type (FlagType, non-native enum), severity (FlagSeverity, non-native enum), details (JSON), created_at; compound FK (segment_job_id, segment_id)->segments CASCADE; Index(segment_id, flag_type) | segment (N:1) |
| User | users | id (String36 PK), email (unique, indexed), hashed_password, full_name, is_active, is_superuser, email_verified, created_at | — |
| PasswordResetToken | password_reset_tokens | id (String36 PK), token (unique, indexed), user_id (FK users CASCADE, indexed), expires_at, used_at, created_at | — |

## Enums
- **JobStatus**: queued, running, needs_review, failed, done
- **JobStage**: parse, ocr, translate, compose, reassemble, done, failed
- **TrackedChangesAction**: strip, preserve
- **FlagType**: overflow, glossary_violation, placeholder_mismatch, llm_refusal, smartart, multi_column_degraded, figure_passthrough, ocr_page_error
- **FlagSeverity**: info, warn, block

## Migrations
Alembic chain (env.py: async via `async_engine_from_config`, `target_metadata = Base.metadata`, DB URL resolved from `get_settings().database_url`, not alembic.ini placeholder).
- `e0e8f781ec72_init.py` — initial schema (jobs, segments).
- `0002_phase2_glossary_flags.py` — Phase 2: glossaries, glossary_terms, segment_flags tables.
- `0003_segment_compound_pk_run_fields.py` — Segment compound PK (job_id, id) + run_index/run_group_size fields.
- `0004_flagtype_phase3.py` — FlagType additions for Phase 3 (smartart, multi_column_degraded).
- `0005_widen_flag_type.py` — widen flag_type column (non-native enum sizing).
- `0006_phase4_ocr.py` — Phase 4 OCR segment columns (confidence, region_bbox, region_label, edited_source_text).
- `0007_job_low_confidence_pages.py` — Job.low_confidence_pages JSON column.
- `0008_auth_users.py` — auth: users + password_reset_tokens tables.
- `0009_job_glossary_user_id.py` — Job/Glossary user_id owner FK columns.
- `0010_seed_default_user.py` — seed default user row.

## Dependencies
sqlalchemy[asyncio] 2.0, asyncpg (async PG driver), alembic; pydantic-settings via `app.core.config`.
