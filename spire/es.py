"""
Elasticsearch clients
"""
from contextlib import contextmanager
import os

import elasticsearch


def es_client_from_env() -> elasticsearch.Elasticsearch:
    """
    Create an elasticsearch client using configuration from environment variables. Respects the
    following environment variables:
    - ELASTICSEARCH_USER
    - ELASTICSEARCH_PASSWORD
    - ELASTICSEARCH_HOSTS
    """
    user = os.environ.get("ELASTICSEARCH_USER")
    password = os.environ.get("ELASTICSEARCH_PASSWORD")
    http_auth = None
    if user is not None:
        if password is None:
            raise ValueError(
                f"ELASTICSEARCH_USER={user} without matching ELASTICSEARCH_PASSWORD environment "
                "variable"
            )
        http_auth = (user, password)
    hosts = os.environ.get("ELASTICSEARCH_HOSTS", "localhost").split(",")
    kwargs = {
        "hosts": hosts,
        "http_auth": http_auth,
    }
    return elasticsearch.Elasticsearch(**kwargs)


def yield_es_client_from_env() -> elasticsearch.Elasticsearch:
    """
    Yields an elasticsearch client (created using environment variables). As per FastAPI docs:
    https://fastapi.tiangolo.com/tutorial/sql-databases/#create-a-dependency
    """
    client = es_client_from_env()
    yield client


yield_es_client_from_env_ctx = contextmanager(yield_es_client_from_env)
