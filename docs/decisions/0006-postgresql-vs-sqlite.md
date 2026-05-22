# ADR-0006: PostgreSQL 16 over SQLite for jobs DB

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

We need a relational store for jobs, segments, glossaries, flags. arq's
Redis holds the queue itself, but job metadata (status, file paths,
language pairs, timestamps, output paths) belongs in a database.

Two natural choices:

1. SQLite — zero ops, single file.
2. PostgreSQL — full server, ops cost.

Multiple translation jobs run concurrently; each writes status updates
multiple times per job.

## Decision

Use **PostgreSQL 16** with **SQLAlchemy 2.0 async** + **asyncpg** driver
+ **Alembic** for migrations. `JSONB` for the glossary terms column.

## Alternatives considered

- **SQLite + aiosqlite** — write serialization bottleneck. Only one
  writer at a time; with concurrent jobs each updating status, the
  queue would back up immediately.
- **MySQL / MariaDB** — Thu's other production projects already run
  PostgreSQL; no reason to introduce a second DB engine.
- **DuckDB** — analytical, not OLTP. Wrong tool.

## Consequences

- ✅ Concurrent writers, MVCC, mature replication story.
- ✅ `JSONB` is a clean fit for glossary terms (variable-length JSON
  blobs with index support).
- ✅ asyncpg is the fastest async PostgreSQL driver in Python
  (binary protocol).
- ✅ Operational knowledge already in the team (Thu's stack).
- ⚠️ One more container in `docker-compose`. Trivial cost.
- ⚠️ Tests use `sqlite+aiosqlite:///:memory:` with `StaticPool`; engine
  config branches on DSN to avoid passing `pool_size` to SQLite (see
  `app/main.py`).

## References

- `CLAUDE.md` → *9. Database*
- `backend/src/app/db/models.py`, `backend/src/app/db/session.py`
- `backend/alembic/`
