from distutils.util import strtobool
import os
from typing import Any, cast, Union


class BugoutAuthConfigurationError(ValueError):
    """
    Raised when Bugout bot tries to authenticate using a Bugout authentication server, but no
    such server is specified.
    """


BUGOUT_TIMEOUT_SECONDS_RAW = os.environ.get("BUGOUT_TIMEOUT_SECONDS", 5)
try:
    BUGOUT_TIMEOUT_SECONDS = int(BUGOUT_TIMEOUT_SECONDS_RAW)
except:
    raise Exception(
        f"Could not parse BUGOUT_TIMEOUT_SECONDS as int: {BUGOUT_TIMEOUT_SECONDS_RAW}"
    )

THREAD_WORKERS = int(os.getenv("THREAD_WORKERS", 2))

# Database
SPIRE_DB_URI = os.environ.get("SPIRE_DB_URI")
if SPIRE_DB_URI is None:
    raise ValueError("SPIRE_DB_URI environment variable not set")
SPIRE_DB_URI_READ_ONLY = os.environ.get("SPIRE_DB_URI_READ_ONLY")
if SPIRE_DB_URI_READ_ONLY is None:
    raise ValueError("SPIRE_DB_URI_READ_ONLY environment variable not set")

SPIRE_DB_POOL_RECYCLE_SECONDS_RAW = os.environ.get("SPIRE_DB_POOL_RECYCLE_SECONDS")
SPIRE_DB_POOL_RECYCLE_SECONDS = 1800
try:
    if SPIRE_DB_POOL_RECYCLE_SECONDS_RAW is not None:
        SPIRE_DB_POOL_RECYCLE_SECONDS = int(SPIRE_DB_POOL_RECYCLE_SECONDS_RAW)
except:
    raise ValueError(
        f"SPIRE_DB_POOL_RECYCLE_SECONDS must be an integer: {SPIRE_DB_POOL_RECYCLE_SECONDS_RAW}"
    )

SPIRE_DB_STATEMENT_TIMEOUT_MILLIS_RAW = os.environ.get(
    "SPIRE_DB_STATEMENT_TIMEOUT_MILLIS"
)
SPIRE_DB_STATEMENT_TIMEOUT_MILLIS = 30000
try:
    if SPIRE_DB_STATEMENT_TIMEOUT_MILLIS_RAW is not None:
        SPIRE_DB_STATEMENT_TIMEOUT_MILLIS = int(SPIRE_DB_STATEMENT_TIMEOUT_MILLIS_RAW)
except:
    raise ValueError(
        f"SPIRE_DB_STATEMENT_TIMEOUT_MILLIS must be an integer: {SPIRE_DB_STATEMENT_TIMEOUT_MILLIS_RAW}"
    )

BUGOUT_SPIRE_THREAD_DB_POOL_SIZE = 2
BUGOUT_SPIRE_THREAD_DB_POOL_SIZE_RAW = os.environ.get(
    "BUGOUT_SPIRE_THREAD_DB_POOL_SIZE"
)
BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW = 2
BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW_RAW = os.environ.get(
    "BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW"
)
try:
    if BUGOUT_SPIRE_THREAD_DB_POOL_SIZE_RAW is not None:
        BUGOUT_SPIRE_THREAD_DB_POOL_SIZE = int(BUGOUT_SPIRE_THREAD_DB_POOL_SIZE_RAW)
except:
    raise Exception(
        f"Could not parse BUGOUT_SPIRE_THREAD_DB_POOL_SIZE as int: {BUGOUT_SPIRE_THREAD_DB_POOL_SIZE_RAW}"
    )
try:
    if BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW_RAW is not None:
        BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW = int(
            BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW_RAW
        )
except:
    raise Exception(
        f"Could not parse BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW as int: {BUGOUT_SPIRE_THREAD_DB_MAX_OVERFLOW_RAW}"
    )

BUGOUT_CLIENT_ID_HEADER_RAW = os.environ.get("BUGOUT_CLIENT_ID_HEADER")
if BUGOUT_CLIENT_ID_HEADER_RAW is not None:
    BUGOUT_CLIENT_ID_HEADER = BUGOUT_CLIENT_ID_HEADER_RAW
else:
    raise ValueError("BUGOUT_CLIENT_ID_HEADER environment variable must be set")

INSTALLATION_TOKEN = os.environ.get("BUGOUT_BOT_INSTALLATION_TOKEN", "")
BOT_INSTALLATION_TOKEN_HEADER_RAW = os.environ.get(
    "BUGOUT_BOT_INSTALLATION_TOKEN_HEADER"
)
if BOT_INSTALLATION_TOKEN_HEADER_RAW is not None:
    BOT_INSTALLATION_TOKEN_HEADER = BOT_INSTALLATION_TOKEN_HEADER_RAW
else:
    raise ValueError(
        "BUGOUT_BOT_INSTALLATION_TOKEN_HEADER environment variable must be set"
    )

# GitHub
GITHUB_BOT_USERNAME = os.environ.get("BUGOUT_GITHUB_BOT_USERNAME", "bugout-dev")

GITHUB_SUMMARY_BUCKET = os.environ.get("AWS_S3_GITHUB_SUMMARY_BUCKET")
GITHUB_SUMMARY_PREFIX = os.environ.get("AWS_S3_GITHUB_SUMMARY_PREFIX", "").rstrip("/")

GITHUB_SECRET_B64 = os.environ.get("BUGOUT_GITHUB_PRIVATE_KEY_BASE64", "")
GITHUB_KEYFILE: Any = os.environ.get("BUGOUT_GITHUB_PRIVATE_KEY_FILE")
GITHUB_APP_ID = os.environ.get("BUGOUT_GITHUB_APP_ID")
GITHUB_WEBHOOK_SECRET = os.environ.get("BUGOUT_GITHUB_WEBHOOK_SECRET")

GITHUB_REDIRECT_URL = os.environ.get(
    "BUGOUT_GITHUB_REDIRECT_URL", "https://github.com/apps/bugout-dev"
)

BUGOUT_REDIS_URL = os.getenv("BUGOUT_REDIS_URL")
BUGOUT_REDIS_PASSWORD = os.getenv("BUGOUT_REDIS_PASSWORD")
REDIS_REPORTS_QUEUE = os.getenv("REDIS_REPORTS_QUEUE")

SPIRE_API_URL = os.environ.get("SPIRE_API_URL", "")


def auth_url_from_env() -> str:
    """
    Retrieves Bugout authentication server URL from the BUGOUT_AUTH_URL environment variable.

    #TODO(komptkot): Delete same func from slack.admin
    """
    bugout_auth_url = os.environ.get("BUGOUT_AUTH_URL")
    if bugout_auth_url is None:
        raise BugoutAuthConfigurationError(
            "BUGOUT_AUTH_URL environment variable not set"
        )
    bugout_auth_url = bugout_auth_url.rstrip("/")
    return bugout_auth_url


# CORS
# TODO(neeraj): Use this in journals/api.py. Right now the CORS settings there are hard-coded.
_origins_raw = os.environ.get("SPIRE_CORS_ALLOWED_ORIGINS")
if _origins_raw is None:
    raise ValueError("SPIRE_CORS_ALLOWED_ORIGINS environment variable must be set")
CORS_ALLOWED_ORIGINS = _origins_raw.split(",")

DEFAULT_JOURNALS_ES_INDEX = "bugout-main"
BULK_CHUNKSIZE = 1000

# Drones AWS bucket
DRONES_BUCKET = os.environ.get("AWS_S3_DRONES_BUCKET")
DRONES_BUCKET_STATISTICS_PREFIX = os.environ.get(
    "AWS_S3_DRONES_BUCKET_STATISTICS_PREFIX", "prod/statistics/journals"
).rstrip("/")
DRONES_URL = os.environ.get("BUGOUT_DRONES_URL")
BUGOUT_DRONES_TOKEN = os.environ.get("BUGOUT_DRONES_TOKEN")
BUGOUT_DRONES_TOKEN_HEADER = os.environ.get("BUGOUT_DRONES_TOKEN_HEADER")
STATISTICS_S3_PRESIGNED_URL_EXPIRATION_TIME = 60  # seconds

# OpenAPI
DOCS_TARGET_PATH = "docs"
SPIRE_OPENAPI_LIST = []
SPIRE_OPENAPI_LIST_RAW = os.environ.get("SPIRE_OPENAPI_LIST")
if SPIRE_OPENAPI_LIST_RAW is not None:
    SPIRE_OPENAPI_LIST = SPIRE_OPENAPI_LIST_RAW.split(",")

DOCS_PATHS = []
for path in SPIRE_OPENAPI_LIST:
    DOCS_PATHS.append(f"/{path}/{DOCS_TARGET_PATH}")
    DOCS_PATHS.append(f"/{path}/{DOCS_TARGET_PATH}/openapi.json")

BUGOUT_HUMBUG_REDIS_TIMEOUT_RAW = os.environ.get("BUGOUT_HUMBUG_REDIS_TIMEOUT")
BUGOUT_HUMBUG_REDIS_TIMEOUT = 0.5
if BUGOUT_HUMBUG_REDIS_TIMEOUT_RAW is not None:
    try:
        BUGOUT_HUMBUG_REDIS_TIMEOUT = float(BUGOUT_HUMBUG_REDIS_TIMEOUT_RAW)
    except:
        pass

BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS_RAW = os.environ.get(
    "BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS"
)
BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS = 10
if BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS_RAW is not None:
    try:
        BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS = int(
            BUGOUT_HUMBUG_REDIS_CONNECTIONS_PER_PROCESS_RAW
        )
    except:
        pass
