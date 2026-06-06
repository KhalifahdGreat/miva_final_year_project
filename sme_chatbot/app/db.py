"""Postgres connection pool.

A single async-friendly psycopg pool, created at startup and closed at
shutdown.  Every request acquires a connection via FastAPI dependencies
(see app/deps.py).
"""

from __future__ import annotations

from collections.abc import Iterator

from psycopg_pool import ConnectionPool

from .config import get_settings


_pool: ConnectionPool | None = None


def init_pool() -> ConnectionPool:
    """Create and open the global connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    s = get_settings()
    _pool = ConnectionPool(
        s.database_url,
        min_size=s.database_pool_min,
        max_size=s.database_pool_max,
        open=True,
    )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def pool() -> ConnectionPool:
    if _pool is None:
        return init_pool()
    return _pool


def acquire() -> Iterator:
    """Generator-based FastAPI dependency that yields a live connection."""
    with pool().connection() as conn:
        yield conn
