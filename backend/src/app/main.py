"""
FastAPI application entry point.

Lifespan creates and tears down all shared resources:
- SQLAlchemy AsyncEngine (DB pool)
- Redis async client (pub/sub, caching)
- arq pool (W11: shared pool, never per-request)

D-19: configure_logging() is called before any logger is acquired.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import arq
import structlog
from arq.connections import RedisSettings
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine

from app.api.middleware.cors import add_cors_middleware
from app.api.routes import auth, export, glossaries, health, jobs, languages, segments, sse, upload
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.llm.client import make_llm_client

log = structlog.get_logger()

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared infrastructure on startup; dispose cleanly on shutdown.

    Order matters:
    - startup: logging → engine → redis → arq_pool
    - shutdown: arq_pool → redis → engine (reverse order)
    """
    configure_logging()

    app.state.settings = settings
    db_url = settings.database_url.get_secret_value()
    # SQLite uses StaticPool and rejects pool_size/max_overflow (tests use
    # sqlite+aiosqlite:///:memory:). Only pass pool args for server DBs.
    engine_kwargs: dict = {"echo": False}
    if not db_url.startswith("sqlite"):
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
    app.state.engine = create_async_engine(db_url, **engine_kwargs)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    # W11: arq pool created ONCE at startup — injected via get_arq_pool() dependency
    app.state.arq_pool = await arq.create_pool(
        RedisSettings.from_dsn(settings.redis_url)
    )
    # Phase 2: shared LLM client for synchronous regenerate endpoint (REV-04)
    app.state.llm_client = make_llm_client(settings)
    log.info("app_started")

    yield

    await app.state.arq_pool.close()
    await app.state.redis.aclose()
    await app.state.engine.dispose()
    log.info("app_stopped")


app = FastAPI(
    title="AI Translation",
    description="AI-powered document translation PoC — AICore internal demo.",
    version="0.1.0",
    lifespan=lifespan,
)

add_cors_middleware(app)

# Mount routers — no prefix (keep URLs flat for PoC simplicity)
app.include_router(health.router)
app.include_router(upload.router)
app.include_router(languages.router)
app.include_router(glossaries.router)
app.include_router(jobs.router)
app.include_router(segments.router)
app.include_router(export.router)
app.include_router(sse.router)
app.include_router(auth.router)
