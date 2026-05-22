# ADR-0005: arq + Redis for async job queue

**Status**: Accepted
**Date**: 2026-04-17
**Decider(s)**: Thu

## Context

Translation jobs are long-running (seconds to minutes), need to survive
process restarts, need progress reporting, and must be polled for status
by the frontend (via SSE). Multiple jobs run concurrently.

Three queue options on the Python side:

1. FastAPI `BackgroundTasks` — built-in, simplest.
2. arq + Redis — asyncio-native job queue.
3. Celery + Redis — battle-tested, larger ecosystem.

The rest of the stack is async-first (FastAPI, asyncio, async SQLAlchemy).

## Decision

Use **arq 0.27** with **Redis 7** as the job queue. arq workers run in
the same asyncio event loop as request handlers — no sync/async bridge.

## Alternatives considered

- **FastAPI `BackgroundTasks`** — no persistence (dies on restart), no
  status API, no retry. Disqualified for any real job.
- **Celery + Redis** — async support is bolted on via `celery[async]`
  and is less clean; needs a separate Beat process for scheduled work;
  broker config more complex.
- **RQ** — sync-only worker model; awkward inside an asyncio app.

## Consequences

- ✅ Lightweight: single Redis dependency, no extra processes.
- ✅ Workers and API share asyncio event loop semantics — no thread-pool
  surprises.
- ✅ `job.result()` + `job.status()` for native status polling
  (consumed by SSE endpoint).
- ⚠️ arq is in "maintenance mode" upstream — stable but not actively
  developed. Re-evaluate before v2 of the product.
- ⚠️ arq 0.27 officially supports Python 3.9–3.11; 3.12 works in
  practice but verify before bumping.

## References

- `CLAUDE.md` → *7. FastAPI + Next.js for Long-Running Jobs*
- `backend/src/app/workers/translate_worker.py`
- arq: https://pypi.org/project/arq/
