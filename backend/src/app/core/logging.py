from __future__ import annotations

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog for JSON output to stdout. Safe to call multiple times.

    Per D-19: structlog emits JSON to stdout (captured by docker logs).
    job_id is bound as a context var via bind_job_id().
    """
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
