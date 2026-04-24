---
phase: "01"
plan: "02"
subsystem: backend-core
tags: [config, logging, db-models, alembic, test-fixtures, sqlalchemy, pydantic-settings]
dependency_graph:
  requires: ["01-01"]
  provides: ["config", "db-models", "session", "alembic", "test-fixtures"]
  affects: ["01-03", "01-04", "01-05", "01-06", "01-07"]
tech_stack:
  added:
    - "pydantic-settings 2.x with SecretStr for API key + DSN"
    - "structlog JSON logging with contextvars job_id binding"
    - "SQLAlchemy 2.0 async ORM: Job + Segment models"
    - "async_sessionmaker(expire_on_commit=False)"
    - "Alembic async migration setup via async_engine_from_config"
    - "aiosqlite 0.19+ for SQLite unit test engine"
  patterns:
    - "SecretStr for DASHSCOPE_API_KEY and DATABASE_URL (T-02-01, T-02-02 mitigated)"
    - "String(36) Job.id enables SQLite compat for unit tests (W8/W12)"
    - "lru_cache on get_settings() — singleton per process"
    - "session-scoped test engine + function-scoped rollback-per-test"
key_files:
  created:
    - backend/src/app/core/config.py
    - backend/src/app/core/logging.py
    - backend/src/app/db/models.py
    - backend/src/app/db/session.py
    - backend/src/app/db/migrations/env.py
    - backend/src/app/db/migrations/script.py.mako
    - backend/src/app/db/migrations/versions/.gitkeep
    - backend/alembic.ini
    - backend/tests/conftest.py
    - backend/src/app/__init__.py
    - backend/src/app/core/__init__.py
    - backend/src/app/db/__init__.py
    - backend/src/app/db/migrations/__init__.py
    - backend/tests/__init__.py
    - backend/src/__init__.py
  modified:
    - backend/pyproject.toml
decisions:
  - "Job.id is String(36) not postgresql.UUID — SQLite compat for unit tests without ENUM or UUID type issues"
  - "sse-starlette pin changed from ==3.3.4 to >=1.6,<2 — 3.3.4 requires starlette 1.0.0, incompatible with fastapi 0.115"
  - "DATABASE_URL is SecretStr — resolved via get_secret_value() only inside session.py and migrations/env.py"
  - "configure_logging() is idempotent — safe to call from both API lifespan and arq worker startup"
metrics:
  duration_seconds: 420
  completed_date: "2026-04-24"
  tasks_completed: 3
  tasks_total: 3
  files_created: 15
  files_modified: 1
---

# Phase 1 Plan 02: Backend Core — Config, Models, Session, Alembic, Test Fixtures

**One-liner:** pydantic-settings config with SecretStr, structlog JSON logging, SQLAlchemy 2.0 async Job+Segment models (String(36) id for SQLite compat), Alembic async migration env, and shared pytest fixtures (SQLite in-memory session, mock Redis, mock LLM client).

## What Was Built

### Task 1: Config and Logging Modules (commit 668283b)

`backend/src/app/core/config.py` — `Settings` class via pydantic-settings:
- `dashscope_api_key: SecretStr` — never serialized by structlog (T-02-02 mitigated)
- `database_url: SecretStr` — DSN contains password (T-02-01 mitigated)
- `token_budget: int` — validated 500–7000 (D-07: 2–4K range empirically tunable)
- `worker_concurrency: int = 4` (D-17)
- `get_settings()` is `lru_cache`'d — singleton per process

`backend/src/app/core/logging.py` — structlog JSON logging (D-19):
- `configure_logging()` configures `JSONRenderer` to stdout; idempotent
- `bind_job_id(job_id)` / `clear_job_id()` — per-job context binding via contextvars

### Task 2: DB Models, Session, Alembic Init (commit 9270977)

`backend/src/app/db/models.py`:
- `Job` model: all D-10 columns (`status`, `stage`, `source_lang`, `target_lang`, `detected_lang`, `input_format`, `input_path`, `output_path`, `original_filename`, `segments_done`, `segments_total`, `retry_count`, `error_msg`, `has_tracked_changes`, `tracked_changes_action`, timestamps)
- `Segment` model: `id` = 16-char hex (D-06), `seq_in_job`, `structural_position`, `is_comment`, `is_inserted`, `is_deleted` (D-13/D-14)
- `JobStatus`/`JobStage`/`TrackedChangesAction` as `StrEnum` — type-safe ORM enums
- `Job.id = String(36)` (not `postgresql.UUID`) — enables SQLite compat for unit tests

`backend/src/app/db/session.py`:
- Module-level `AsyncEngine` with `pool_size=5, max_overflow=10`
- `SessionFactory = async_sessionmaker(engine, expire_on_commit=False)` — prevents lazy-load errors post-commit
- `get_session()` — FastAPI `AsyncGenerator` dependency

`backend/alembic.ini` + `migrations/env.py`:
- `script_location = src/app/db/migrations`
- Async migration via `async_engine_from_config` + `NullPool`
- `target_metadata = Base.metadata` — enables autogenerate
- URL resolved from `get_settings().database_url.get_secret_value()`

### Task 3: Shared Test Fixtures (commit e90ae27)

`backend/tests/conftest.py`:
- `test_engine` (session-scoped): SQLite in-memory engine; creates all ORM tables
- `db_session` (function-scoped): `AsyncSession` with `rollback()` after each test
- `mock_redis`: `AsyncMock` with `publish`/`ping` for worker unit tests
- `mock_llm_client`: `AsyncMock` `AsyncOpenAI` with configurable `choices[0].message.content`
- `mock_arq_ctx`: combined ctx dict `{llm_client, redis, session_factory}` for worker tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] sse-starlette==3.3.4 incompatible with fastapi>=0.115,<0.116**
- **Found during:** Task 1 (uv sync failure)
- **Issue:** `sse-starlette==3.3.4` requires `starlette==1.0.0`; `fastapi>=0.115` requires `starlette>=0.40,<0.47`. Pin is unsatisfiable.
- **Fix:** Changed pin from `==3.3.4` to `>=1.6,<2` in `pyproject.toml`. Latest compatible version is `1.8.2`.
- **Files modified:** `backend/pyproject.toml`
- **Commit:** 668283b

**2. [Rule 2 - Missing critical functionality] aiosqlite not in test deps**
- **Found during:** Task 3 (conftest uses `sqlite+aiosqlite:///:memory:`)
- **Issue:** `conftest.py` requires `aiosqlite` for async SQLite test engine; it was not in `[project.optional-dependencies].test`.
- **Fix:** Added `"aiosqlite>=0.19"` to test deps via `uv add --optional test`.
- **Files modified:** `backend/pyproject.toml`, `backend/uv.lock`
- **Commit:** 668283b

**3. [Rule 1 - Bug] mock_arq_ctx session_factory needed async context manager protocol**
- **Found during:** Task 3 (review of conftest design)
- **Issue:** Plan's conftest sketch used `AsyncMock(return_value=db_session)` for `session_factory`, which doesn't implement `__aenter__`/`__aexit__`. Worker code uses `async with session_factory() as session:`.
- **Fix:** Used `MagicMock()` with `__aenter__ = AsyncMock(return_value=db_session)` and `__aexit__ = AsyncMock(return_value=False)` — correctly implements the async context manager protocol.
- **Files modified:** `backend/tests/conftest.py`
- **Commit:** e90ae27

## Threat Surface Scan

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-02-01 | `database_url: SecretStr` — `get_secret_value()` required; DSN never appears in logs |
| T-02-02 | `dashscope_api_key: SecretStr` — structlog never serializes SecretStr values |
| T-02-04 | `Job.input_path`/`output_path` constructed server-side from `data_dir + job_id` — no user-supplied path in Phase 1 |

No new security surface introduced beyond the plan's threat model.

## Known Stubs

None — this plan creates infrastructure (config, models, migrations, fixtures). No data flows to UI rendering.

## Self-Check

**Files exist:**
- [x] `backend/src/app/core/config.py`
- [x] `backend/src/app/core/logging.py`
- [x] `backend/src/app/db/models.py`
- [x] `backend/src/app/db/session.py`
- [x] `backend/src/app/db/migrations/env.py`
- [x] `backend/alembic.ini`
- [x] `backend/tests/conftest.py`

**Commits exist:**
- [x] 668283b — config + logging + dep fixes
- [x] 9270977 — db models + session + alembic
- [x] e90ae27 — test fixtures

**Import checks passed:**
- `from app.db.models import Job, Segment` — OK
- `from app.core.config import Settings, get_settings` — OK
- `from app.core.logging import configure_logging, bind_job_id` — OK
- `pytest tests/ --no-cov` — collects 0 tests, no errors (exit 5 = no tests, expected)

## Self-Check: PASSED
