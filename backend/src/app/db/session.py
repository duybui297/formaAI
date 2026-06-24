from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

# Module-level engine — created once at import time.
# Workers call create_async_engine directly in startup() for their own pool;
# this module-level engine is used by the FastAPI app and tests.
_db_url = _settings.database_url.get_secret_value()
_engine_kwargs: dict = {"echo": False}
if not _db_url.startswith("sqlite"):
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    # Disable asyncpg prepared-statement cache so we don't hit
    # InvalidCachedStatementError after Alembic migrations alter columns
    # the pool already cached plans for. Acceptable PoC tradeoff.
    _engine_kwargs["connect_args"] = {"statement_cache_size": 0}
engine = create_async_engine(_db_url, **_engine_kwargs)

# expire_on_commit=False: prevents lazy-load errors after commit in async context
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession, auto-closes after response."""
    async with SessionFactory() as session:
        yield session


async def db_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency wrapper with no parameters.

    Using this as Depends(db_dependency) avoids FastAPI confusing
    AsyncSession from the return annotation with a request parameter.
    """
    async with SessionFactory() as session:
        yield session
