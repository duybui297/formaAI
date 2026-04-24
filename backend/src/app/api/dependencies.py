"""
FastAPI shared dependencies.

W11: arq pool created ONCE in lifespan, read via get_arq_pool() —
never create a per-request pool.
"""
from __future__ import annotations

from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """FastAPI dependency: returns the shared Redis client from app state."""
    return request.app.state.redis


def get_arq_pool(request: Request):
    """FastAPI dependency: returns the shared arq pool from app state.

    W11: pool is created ONCE at startup in lifespan — never per-request.
    """
    return request.app.state.arq_pool


def get_settings(request: Request):
    """FastAPI dependency: returns the cached Settings from app state."""
    return request.app.state.settings
