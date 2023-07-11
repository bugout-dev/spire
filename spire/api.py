"""
Top-level Spire API
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .data import PingResponse, VersionResponse
from .go.api import app as go_api
from .journal.api import app as journal_api
from .public.api import app_public as public_api
from .slack.api import app as slack_api
from .github.api import app as github_api
from .preferences.api import app as preferences_api
from .humbug.api import app as humbug_app
from .utils.settings import SPIRE_RAW_ORIGINS_LST
from .version import SPIRE_VERSION

LOG_LEVEL = logging.INFO
if os.getenv("SPIRE_DEBUG", "").lower() == "true":
    LOG_LEVEL = logging.DEBUG

LOG_FORMAT = "[%(levelname)s] %(name)s (Source: %(pathname)s:%(lineno)d, Time: %(asctime)s) - %(message)s"
logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL)

app = FastAPI(openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=SPIRE_RAW_ORIGINS_LST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(status="ok")


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    return VersionResponse(version=SPIRE_VERSION)


app.mount("/go", go_api)
app.mount("/slack", slack_api)
app.mount("/journals", journal_api)
app.mount("/public", public_api)
app.mount("/github", github_api)
app.mount("/preferences", preferences_api)
app.mount("/humbug", humbug_app)
