"""
GET /jobs/{id}/stream — SSE progress stream via Redis pub/sub.

D-09: SSE is the primary real-time transport. Frontend falls back to
TanStack Query polling when SSE is unavailable.

Design notes:
- Pattern source: RESEARCH.md §7 (exact pubsub + EventSourceResponse pattern)
- Pitfall #3 mitigation: pubsub.unsubscribe() + pubsub.aclose() in finally block
  to prevent Redis subscription memory leak on disconnect or crash.
- T-06b-02: CancelledError caught; finally always runs.
- ping=15: server sends SSE comment every 15 s to keep the connection alive
  through proxies that close idle long-poll connections.
- X-Accel-Buffering: no — disables nginx proxy buffering so events reach the
  client immediately without waiting for a buffer flush.
"""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, Depends
from sse_starlette import EventSourceResponse
from starlette.requests import Request

from app.api.dependencies import get_redis

log = structlog.get_logger()

router = APIRouter()

# Statuses that indicate the job has reached a terminal state.
# SSE stream closes immediately after yielding the terminal event.
_TERMINAL_STATUSES = frozenset({"done", "failed", "needs_review"})


@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(
    job_id: str,
    request: Request,
    redis=Depends(get_redis),
) -> EventSourceResponse:
    """
    JOB-02/03: SSE stream of job progress events.

    Primary transport per D-09. Polling fallback in frontend when SSE
    is unavailable or disconnects.

    Pitfall #3: pub/sub subscription is always released in the finally block
    to prevent Redis memory leaks on abrupt client disconnect.

    # TODO(phase-2): add JWT auth
    """

    async def _job_progress_generator():
        pubsub = redis.pubsub()
        await pubsub.subscribe(f"job:{job_id}")
        log.debug("sse_subscribed", job_id=job_id)

        try:
            while True:
                # Check for client disconnect before polling Redis
                if await request.is_disconnected():
                    log.debug("sse_client_disconnected", job_id=job_id)
                    break

                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message["type"] == "message":
                    payload = json.loads(message["data"])
                    yield {"data": json.dumps(payload), "event": "progress"}
                    log.debug(
                        "sse_event_sent",
                        job_id=job_id,
                        status=payload.get("status"),
                    )

                    # Close stream on terminal status (D-09)
                    if payload.get("status") in _TERMINAL_STATUSES:
                        log.debug("sse_terminal_status", job_id=job_id, status=payload.get("status"))
                        break
                else:
                    # No message — yield to event loop before polling again
                    await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            # T-06b-02: client aborted; finally block will clean up
            pass
        finally:
            # Pitfall #3: ALWAYS unsubscribe to prevent Redis pub/sub memory leak
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.aclose()
            log.debug("sse_unsubscribed", job_id=job_id)

    return EventSourceResponse(
        _job_progress_generator(),
        ping=15,
        headers={
            "X-Accel-Buffering": "no",   # Disable nginx buffering for SSE
            "Cache-Control": "no-store",
        },
    )
