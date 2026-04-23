---
phase: 01-foundation-docx-pipeline
plan: "02"
type: execute
wave: 1
depends_on:
  - "01"
files_modified:
  - backend/src/app/core/config.py
  - backend/src/app/core/logging.py
  - backend/src/app/db/models.py
  - backend/src/app/db/session.py
  - backend/src/app/db/migrations/env.py
  - backend/src/app/db/migrations/versions/.gitkeep
  - backend/src/app/__init__.py
  - backend/src/app/core/__init__.py
  - backend/src/app/db/__init__.py
  - backend/alembic.ini
  - backend/tests/conftest.py
  - backend/tests/__init__.py
autonomous: true
requirements:
  - INFRA-03
  - JOB-01

must_haves:
  truths:
    - "Settings loads from environment variables with pydantic-settings SecretStr for DASHSCOPE_API_KEY"
    - "AsyncEngine and async_sessionmaker are created once at app startup"
    - "Job and Segment SQLAlchemy models with all Phase 1 fields exist"
    - "Alembic is initialized and can generate migrations"
    - "structlog is configured to emit JSON to stdout with job_id context binding"
  artifacts:
    - path: "backend/src/app/core/config.py"
      provides: "Settings class: dashscope_api_key (SecretStr), dashscope_base_url, database_url, redis_url, data_dir, token_budget, worker_concurrency"
      exports: ["Settings", "get_settings"]
    - path: "backend/src/app/db/models.py"
      provides: "Job and Segment SQLAlchemy models"
      contains: "class Job", "class Segment"
    - path: "backend/src/app/db/session.py"
      provides: "AsyncEngine factory, async_sessionmaker, get_session dependency"
      exports: ["create_engine", "get_session", "engine"]
    - path: "backend/alembic.ini"
      provides: "Alembic config pointing at migrations/"
    - path: "backend/tests/conftest.py"
      provides: "Shared test fixtures: mock AsyncSession, mock Redis, mock AsyncOpenAI"
  key_links:
    - from: "backend/src/app/core/config.py"
      to: "DASHSCOPE_API_KEY env var"
      via: "pydantic-settings BaseSettings"
    - from: "backend/src/app/db/session.py"
      to: "DATABASE_URL env var"
      via: "Settings.database_url"
    - from: "backend/src/app/db/models.py"
      to: "Alembic migrations"
      via: "SQLAlchemy DeclarativeBase"
---

<objective>
Create the backend Python module skeleton: pydantic-settings config, structlog JSON logging, SQLAlchemy 2.0 async DB models (Job + Segment), Alembic migration setup, and the shared test fixtures (conftest.py). This is the data layer all subsequent backend plans depend on.

Purpose: Establish the schema contract and config primitives that worker, API, and pipeline plans will consume.
Output: backend/src/app/{core,db}/ modules fully implemented. Alembic can generate a migration. conftest.py provides async session + Redis + LLM mock fixtures.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md
@.planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md

<interfaces>
<!-- Key schema decisions from CONTEXT.md for executor -->

D-04: Per-job file layout: .data/jobs/{job_id}/source.{ext}, output.{ext}, segments.json, errors.log.
      Job.input_path / Job.output_path reference these paths.
D-05: Segments form a structural tree with parent refs. Each Segment carries:
      - id (sha256[:16] per D-06)
      - seq_in_job (int, for "segment 143/210" display)
      - job_id (FK to Job)
      - source_text (str)
      - translated_text (str | None)
      - structural_position (str — encodes para/cell/header/comment location)
      - is_comment (bool, D-14)
      - is_inserted / is_deleted (bool, tracked-changes D-13)
D-06: Segment ID = sha256(source_text + structural_position)[:16]. Also seq_in_job.
D-10: Job progress payload shape (maps to Job columns):
      status: queued|running|needs_review|failed|done
      stage: parse|translate|reassemble|done|failed
      segments_done: int
      segments_total: int
D-19: structlog JSON to stdout, job_id bound as context var per job.

Job table required columns:
  id (UUID PK), status, stage, source_lang, target_lang, input_format (docx/pdf/pptx),
  input_path, output_path, segments_done, segments_total, retry_count, error_msg,
  detected_lang (from qwen auto-detect), has_tracked_changes, tracked_changes_action (strip/preserve/null),
  created_at, updated_at

Segment table required columns:
  id (str 16-char hex PK), seq_in_job (int), job_id (UUID FK),
  source_text, translated_text (nullable), structural_position,
  is_comment (bool default False), is_inserted (bool default False), is_deleted (bool default False),
  created_at

Python patterns from CLAUDE.md:
  - pydantic-settings: use SecretStr for DASHSCOPE_API_KEY
  - SQLAlchemy 2.0: use AsyncSession + async_sessionmaker
  - DSN: postgresql+asyncpg://...
  - Use composition over inheritance (no ORM model inheritance)
  - Immutable config: Settings can be frozen=True (but NOT ORM models)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Create Config and Logging Modules</name>
  <files>
    backend/src/app/__init__.py
    backend/src/app/core/__init__.py
    backend/src/app/core/config.py
    backend/src/app/core/logging.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-19 structlog, D-18 healthcheck items)
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 4: make_llm_client signature, Settings usage)
    ./CLAUDE.md (Python Security Essentials: SecretStr, pydantic-settings)
  </read_first>
  <behavior>
    - Settings.dashscope_api_key is SecretStr — never logs the value
    - Settings.database_url is SecretStr — DSN contains password
    - get_settings() is lru_cache'd — single instance per process
    - structlog configured once at module load with JSON renderer
    - configure_logging() is idempotent (safe to call multiple times)
  </behavior>
  <action>
Create `backend/src/app/__init__.py` (empty).
Create `backend/src/app/core/__init__.py` (empty).

Create `backend/src/app/core/config.py`:
```python
from __future__ import annotations
from functools import lru_cache
from pydantic import AnyUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # DashScope (AI-SPEC §4: must be intl key from dashscope-intl.aliyuncs.com)
    dashscope_api_key: SecretStr
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"

    # Database (D-03: postgresql+asyncpg DSN)
    database_url: SecretStr

    # Redis (D-03)
    redis_url: str = "redis://redis:6379/0"

    # File storage (D-04: per-job layout)
    data_dir: str = "/data"

    # Translation batch token budget (D-07: 2-4K range; tune empirically)
    token_budget: int = 3000

    # Worker batch concurrency (D-17: 4 concurrent DashScope calls per job)
    worker_concurrency: int = 4

    @field_validator("token_budget")
    @classmethod
    def validate_token_budget(cls, v: int) -> int:
        if not (500 <= v <= 7000):
            raise ValueError(f"token_budget must be 500-7000, got {v}")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `backend/src/app/core/logging.py` (D-19: structlog JSON to stdout):
```python
from __future__ import annotations
import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for JSON output to stdout. Safe to call multiple times."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_job_id(job_id: str) -> None:
    """Bind job_id to all subsequent log calls in this coroutine context (D-19)."""
    structlog.contextvars.bind_contextvars(job_id=job_id)


def clear_job_id() -> None:
    """Clear job_id binding after job completes."""
    structlog.contextvars.clear_contextvars()
```
  </action>
  <verify>
    <automated>
      cd /home/thu/dev/projects/ai-translation/backend &amp;&amp;
      python -c "import sys; sys.path.insert(0, 'src'); from app.core.config import Settings, get_settings; print('config OK')" 2>&amp;1 | grep -q "config OK" || echo "MISSING - needs uv install first" &amp;&amp;
      grep -q "SecretStr" src/app/core/config.py &amp;&amp;
      grep -q "dashscope_api_key" src/app/core/config.py &amp;&amp;
      grep -q "token_budget" src/app/core/config.py &amp;&amp;
      grep -q "bind_job_id" src/app/core/logging.py &amp;&amp;
      grep -q "JSONRenderer" src/app/core/logging.py
    </automated>
  </verify>
  <done>
    config.py defines Settings with dashscope_api_key (SecretStr), database_url (SecretStr), redis_url, data_dir, token_budget (validated 500-7000), worker_concurrency.
    get_settings() is lru_cache'd.
    logging.py provides configure_logging() (JSON structlog) and bind_job_id()/clear_job_id() for D-19 job context binding.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create DB Models, Session, and Alembic Init</name>
  <files>
    backend/src/app/db/__init__.py
    backend/src/app/db/models.py
    backend/src/app/db/session.py
    backend/alembic.ini
    backend/src/app/db/migrations/__init__.py
    backend/src/app/db/migrations/env.py
    backend/src/app/db/migrations/script.py.mako
    backend/src/app/db/migrations/versions/.gitkeep
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-CONTEXT.md (D-04, D-05, D-06, D-10: Job columns + Segment schema)
    .planning/phases/01-foundation-docx-pipeline/01-RESEARCH.md (Section 6: create_async_engine pattern, async_sessionmaker)
    ./CLAUDE.md (SQLAlchemy 2.0 async, asyncpg driver; Repository Pattern)
  </read_first>
  <behavior>
    - Job model: all required Phase 1 columns; status/stage as Python Enum (not raw string)
    - Segment model: id is 16-char hex string (not UUID); job_id FK references Job.id
    - Session fixture in tests: rolls back after each test (CLAUDE.md Python Testing)
    - async_sessionmaker has expire_on_commit=False (prevents lazy-load after commit in async context)
  </behavior>
  <action>
Create `backend/src/app/db/__init__.py` (empty).

Create `backend/src/app/db/models.py`:
```python
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, ForeignKey, DateTime, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    needs_review = "needs_review"
    failed = "failed"
    done = "done"


class JobStage(str, enum.Enum):
    parse = "parse"
    translate = "translate"
    reassemble = "reassemble"
    done = "done"
    failed = "failed"


class TrackedChangesAction(str, enum.Enum):
    strip = "strip"
    preserve = "preserve"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[JobStatus] = mapped_column(SAEnum(JobStatus), default=JobStatus.queued, nullable=False)
    stage: Mapped[JobStage | None] = mapped_column(SAEnum(JobStage), nullable=True)

    source_lang: Mapped[str] = mapped_column(String(64), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(64), nullable=False)
    detected_lang: Mapped[str | None] = mapped_column(String(64), nullable=True)

    input_format: Mapped[str] = mapped_column(String(16), nullable=False)  # docx/pdf/pptx
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)

    segments_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    segments_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    has_tracked_changes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracked_changes_action: Mapped[TrackedChangesAction | None] = mapped_column(
        SAEnum(TrackedChangesAction), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    segments: Mapped[list[Segment]] = relationship("Segment", back_populates="job", lazy="selectin")


class Segment(Base):
    __tablename__ = "segments"

    # D-06: 16-char hex from sha256(source_text + structural_position)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    seq_in_job: Mapped[int] = mapped_column(Integer, nullable=False)

    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)

    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    structural_position: Mapped[str] = mapped_column(Text, nullable=False)

    # D-13/D-14: tracked changes + comments
    is_comment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_inserted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[Job] = relationship("Job", back_populates="segments")
```

Create `backend/src/app/db/session.py` (RESEARCH.md §6 engine pattern):
```python
from __future__ import annotations
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import get_settings

_settings = get_settings()
engine = create_async_engine(
    _settings.database_url.get_secret_value(),
    pool_size=5,
    max_overflow=10,
    echo=False,
)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession, auto-closes after response."""
    async with SessionFactory() as session:
        yield session
```

For Alembic: run `cd backend && alembic init src/app/db/migrations` conceptually. Create the files manually:

Create `backend/alembic.ini` pointing to backend/src/app/db/migrations:
```ini
[alembic]
script_location = src/app/db/migrations
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `backend/src/app/db/migrations/env.py` with async engine support:
```python
import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

from app.db.models import Base
from app.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    return get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    settings = {"sqlalchemy.url": get_url()}
    connectable = async_engine_from_config(
        settings, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/src/app/db/migrations/script.py.mako` (standard Alembic template):
```
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

Create `backend/src/app/db/migrations/versions/.gitkeep` (empty file, so git tracks the empty directory).
  </action>
  <verify>
    <automated>
      grep -q "class Job" backend/src/app/db/models.py &amp;&amp;
      grep -q "class Segment" backend/src/app/db/models.py &amp;&amp;
      grep -q "has_tracked_changes" backend/src/app/db/models.py &amp;&amp;
      grep -q "is_comment" backend/src/app/db/models.py &amp;&amp;
      grep -q "async_sessionmaker" backend/src/app/db/session.py &amp;&amp;
      grep -q "expire_on_commit=False" backend/src/app/db/session.py &amp;&amp;
      test -f backend/alembic.ini &amp;&amp;
      grep -q "target_metadata = Base.metadata" backend/src/app/db/migrations/env.py
    </automated>
  </verify>
  <done>
    db/models.py has Job (queued/running/needs_review/failed/done states, all D-10 columns, has_tracked_changes, tracked_changes_action) and Segment (16-char hex id, seq_in_job, is_comment, is_inserted, is_deleted).
    db/session.py creates AsyncEngine with pool_size=5, async_sessionmaker with expire_on_commit=False, get_session() FastAPI dependency.
    alembic.ini + migrations/env.py use async engine; target_metadata points to Base.metadata.
  </done>
</task>

<task type="auto">
  <name>Task 3: Create Shared Test Fixtures (conftest.py)</name>
  <files>
    backend/tests/__init__.py
    backend/tests/conftest.py
  </files>
  <read_first>
    .planning/phases/01-foundation-docx-pipeline/01-PATTERNS.md (Backend Tests section — pattern sources for test files)
    .planning/phases/01-foundation-docx-pipeline/01-AI-SPEC.md (Section 4: AsyncOpenAI client factory signature)
    ./CLAUDE.md (Python Testing: pytest-asyncio, AsyncSession fixture, rollback-after-test)
  </read_first>
  <action>
Create `backend/tests/__init__.py` (empty).

Create `backend/tests/conftest.py` with shared fixtures for all backend tests:

```python
from __future__ import annotations
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# ---------------------------------------------------------------------------
# In-memory SQLite for unit tests (no Postgres required for unit tests)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """One SQLite in-memory engine per test session."""
    from app.db.models import Base
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """
    AsyncSession per test, rolled back after.
    Per CLAUDE.md Python Testing: function-scoped, fresh isolation.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests. Tracks publish calls."""
    redis = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.ping = AsyncMock(return_value=True)
    redis.pubsub = MagicMock()
    return redis


# ---------------------------------------------------------------------------
# Mock AsyncOpenAI (for translate_batch unit tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_llm_client():
    """
    Mock AsyncOpenAI client. Configurable response content via mock_llm_client.chat.completions.create.return_value.
    """
    client = AsyncMock()
    # Default: return 2 translated lines for 2 input segments
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello world\nThis is a test"
    mock_response.usage = MagicMock(
        prompt_tokens=10, completion_tokens=12, total_tokens=22
    )
    client.chat.completions.create = AsyncMock(return_value=mock_response)
    return client


# ---------------------------------------------------------------------------
# arq ctx mock
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_arq_ctx(mock_redis, mock_llm_client, db_session):
    """Mock arq worker ctx dict with all required keys."""
    return {
        "llm_client": mock_llm_client,
        "redis": mock_redis,
        "session_factory": AsyncMock(return_value=db_session),
    }
```

Also add `aiosqlite` to the test dependencies in pyproject.toml since we use SQLite for unit tests:
Add `"aiosqlite>=0.19"` to the `[project.optional-dependencies]` test section.
  </action>
  <verify>
    <automated>
      grep -q "db_session" backend/tests/conftest.py &amp;&amp;
      grep -q "mock_redis" backend/tests/conftest.py &amp;&amp;
      grep -q "mock_llm_client" backend/tests/conftest.py &amp;&amp;
      grep -q "rollback" backend/tests/conftest.py &amp;&amp;
      grep -q "mock_arq_ctx" backend/tests/conftest.py
    </automated>
  </verify>
  <done>
    tests/conftest.py provides: db_session (SQLite in-memory, rolls back per test), mock_redis (AsyncMock with publish/ping), mock_llm_client (AsyncMock with configurable response), mock_arq_ctx (dict with all three).
    pyproject.toml test deps includes aiosqlite.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| env → Settings | database_url is SecretStr; get_secret_value() required to access DSN |
| ORM models → DB | SQLAlchemy type-mapped columns prevent SQL injection via ORM layer |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-01 | Information Disclosure | Settings.database_url | mitigate | SecretStr prevents accidental logging; get_secret_value() required |
| T-02-02 | Information Disclosure | Settings.dashscope_api_key | mitigate | SecretStr; never appears in structlog JSON output |
| T-02-03 | Tampering | Alembic migrations | accept | Internal PoC; no external access to migration commands |
| T-02-04 | Elevation of Privilege | Job.input_path / output_path | mitigate | Paths constructed by server from data_dir + job_id; user cannot supply arbitrary paths in Phase 1 (no user-provided path input) |
</threat_model>

<verification>
After all tasks complete:
1. `grep -q "class Job" backend/src/app/db/models.py` — passes
2. `grep -q "SecretStr" backend/src/app/core/config.py` — passes
3. `grep -q "mock_arq_ctx" backend/tests/conftest.py` — passes
4. `cd backend && python -c "from app.db.models import Job, Segment; print('models OK')"` — passes (after uv install)
5. `cd backend && alembic check` — no error (after Postgres is running and migration generated)
</verification>

<success_criteria>
- Settings has SecretStr for dashscope_api_key and database_url; token_budget validated 500-7000
- Job model has all D-10 columns plus has_tracked_changes, tracked_changes_action, detected_lang, original_filename
- Segment model has 16-char hex id, seq_in_job, structural_position, is_comment, is_inserted, is_deleted
- alembic.ini + migrations/env.py use async engine with Base.metadata as target_metadata
- conftest.py provides db_session (SQLite, rollback-per-test), mock_redis, mock_llm_client, mock_arq_ctx
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-docx-pipeline/01-02-SUMMARY.md`
</output>
