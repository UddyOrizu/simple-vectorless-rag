"""A single asyncpg pool for the app's lifetime, created on FastAPI
startup and closed on shutdown (see main.py's lifespan handler)."""
from typing import Optional

import asyncpg

from . import config
from .repository import init_schema

_pool: Optional[asyncpg.Pool] = None


async def connect() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=10)
        await init_schema(_pool)
    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialized -- connect() must run at startup.")
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
