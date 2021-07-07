"""
Spire database connection
"""
from contextlib import contextmanager
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import aioredis # type: ignore

from .utils.settings import (
    BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_DB,
)

connection_str = os.environ.get("SPIRE_DB_URI")
if connection_str is None:
    raise ValueError("SPIRE_DB_URI environment variable not set")

engine = create_engine(
    connection_str,
    pool_size=BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    max_overflow=BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
)
SessionLocal = sessionmaker(bind=engine)


class RedisCache:
    def __init__(self):
        self.redis_cache: Optional[Redis] = None

    async def init_cache(self):
        self.redis_cache = await aioredis.create_redis_pool(
            "redis://localhost:6379/?encoding=utf-8"
        )

    async def close(self):
        self.redis_cache.close()
        await self.redis_cache.wait_closed()


redis_cache = RedisCache()


def yield_connection_from_env() -> Session:
    """
    Yields a database connection (created using environment variables). As per FastAPI docs:
    https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-dependency
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


yield_connection_from_env_ctx = contextmanager(yield_connection_from_env)
