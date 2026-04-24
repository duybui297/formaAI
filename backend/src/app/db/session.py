from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

# Module-level engine — created once at import time.
# Workers call create_async_engine directly in startup() for their own pool;
# this module-level engine is used by the FastAPI app and tests.
engine = create_async_engine(
    _settings.database_url.get_secret_value(),
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# expire_on_commit=False: prevents lazy-load errors after commit in async context
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an AsyncSession, auto-closes after response."""
    async with SessionFactory() as session:
        yield session
