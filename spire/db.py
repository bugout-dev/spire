"""
Spire database connection
"""
from contextlib import contextmanager
from datetime import time
import os

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql.expression import true

from .utils.settings import (
    BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    BUGOUT_REDIS_URL,
    BUGOUT_REDIS_PASSWORD,
    BUGOUT_HUMBUG_REDIS_TIMEOUT,
    BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS,
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


RedisPool = redis.ConnectionPool.from_url(
    f"redis://:{BUGOUT_REDIS_PASSWORD}@{BUGOUT_REDIS_URL}",
    max_connections=BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS,
    socket_timeout=BUGOUT_HUMBUG_REDIS_TIMEOUT,
    health_check_interval=10,
)


def redis_connection():
    return redis.Redis(connection_pool=RedisPool)


yield_connection_from_env_ctx = contextmanager(yield_connection_from_env)
