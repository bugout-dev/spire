"""
Spire database connection
"""
from contextlib import contextmanager
from typing import Optional

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from .utils.settings import (
    SPIRE_DB_URI,
    SPIRE_DB_URI_READ_ONLY,
    SPIRE_DB_POOL_RECYCLE_SECONDS,
    SPIRE_DB_STATEMENT_TIMEOUT_MILLIS,
    BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    BUGOUT_REDIS_URL,
    BUGOUT_REDIS_PASSWORD,
    BUGOUT_HUMBUG_REDIS_TIMEOUT,
    BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS,
)


def create_spire_engine(
    url: Optional[str],
    pool_size: int,
    max_overflow: int,
    statement_timeout: int,
    pool_recycle: int = SPIRE_DB_POOL_RECYCLE_SECONDS,
):
    # Pooling: https://docs.sqlalchemy.org/en/14/core/pooling.html#sqlalchemy.pool.QueuePool
    # Statement timeout: https://stackoverflow.com/a/44936982
    return create_engine(
        url=url,
        pool_size=pool_size,
        pool_recycle=pool_recycle,
        max_overflow=max_overflow,
        connect_args={"options": f"-c statement_timeout={statement_timeout}"},
    )


engine = create_spire_engine(
    url=SPIRE_DB_URI,
    pool_size=BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    max_overflow=BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    statement_timeout=SPIRE_DB_STATEMENT_TIMEOUT_MILLIS,
    pool_recycle=SPIRE_DB_POOL_RECYCLE_SECONDS,
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


# Read only database
RO_engine = create_spire_engine(
    url=SPIRE_DB_URI_READ_ONLY,
    pool_size=BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    max_overflow=BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    statement_timeout=SPIRE_DB_STATEMENT_TIMEOUT_MILLIS,
    pool_recycle=SPIRE_DB_POOL_RECYCLE_SECONDS,
)
RO_SessionLocal = sessionmaker(bind=RO_engine)


def yield_db_read_only_session() -> Session:
    """
    Yields read only database connection (created using environment variables).
    As per FastAPI docs:
    https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-dependency
    """
    session = RO_SessionLocal()
    try:
        yield session
    finally:
        session.close()


# Redis
RedisPool = redis.ConnectionPool.from_url(
    f"redis://:{BUGOUT_REDIS_PASSWORD}@{BUGOUT_REDIS_URL}",
    max_connections=BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS,
    socket_timeout=BUGOUT_HUMBUG_REDIS_TIMEOUT,
    health_check_interval=10,
)


def redis_connection():
    return redis.Redis(connection_pool=RedisPool)


yield_connection_from_env_ctx = contextmanager(yield_connection_from_env)
