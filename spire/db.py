"""
Spire database connection
"""
from contextlib import contextmanager
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import redis
from .utils.settings import (
    BUGOUT_SPIRE_THREAD_DB_POOL_SIZE,
    BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW,
    REDIS_URL,
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


@contextmanager
def yield_redis_pool():
    try:
        redis_client = redis.Redis(host="127.0.0.1", port=6379)
        yield redis_client
    finally:
        redis_client.close()


yield_connection_from_env_ctx = contextmanager(yield_connection_from_env)
