import logging
from typing import Optional

from fastapi import FastAPI, Response, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .data import DefaultJournal
from .. import db
from . import actions
from .errors import PreferenceLocked
from ..data import VersionResponse
from ..middleware import BroodAuthMiddleware
from ..utils.settings import (
    CORS_ALLOWED_ORIGINS,
    SPIRE_OPENAPI_LIST,
    DOCS_PATHS,
    DOCS_TARGET_PATH,
)
from .version import SPIRE_PREFERENCES_VERSION

SUBMODULE_NAME = "preferences"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "default journal", "description": "Default journal preferences."},
]

app = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to manage journal preferences.",
    version=SPIRE_PREFERENCES_VERSION,
    openapi_tags=tags_metadata,
    openapi_url=f"/{DOCS_TARGET_PATH}/openapi.json"
    if SUBMODULE_NAME in SPIRE_OPENAPI_LIST
    else None,
    docs_url=None,
    redoc_url=f"/{DOCS_TARGET_PATH}",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BroodAuthMiddleware, whitelist=DOCS_PATHS)


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """
    Spire preferences submodule version.
    """
    return VersionResponse(version=SPIRE_PREFERENCES_VERSION)


@app.get("/default_journal", tags=["default journal"], response_model=DefaultJournal)
async def get_actions(
    request: Request, db_session: Session = Depends(db.yield_connection_from_env)
) -> DefaultJournal:
    """
    Get ID of default journal.
    """
    result = actions.default_journal_get(db_session, request.state.user_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail="No default journal set for this user"
        )
    return DefaultJournal(id=result.journal_id)


@app.post("/default_journal", tags=["default journal"], response_model=DefaultJournal)
@app.put("/default_journal", tags=["default journal"], response_model=DefaultJournal)
async def set_actions(
    actions_spec: DefaultJournal,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> DefaultJournal:
    """
    Update default journal.

    - **id** (uuid): Journal ID
    """
    journal_id = actions_spec.id
    try:
        actions.default_journal_upsert(db_session, request.state.user_id, journal_id)
    except PreferenceLocked as e:
        logger.error(repr(e))
        raise HTTPException(status_code=423)
    return actions_spec


@app.delete("/default_journal", tags=["default journal"], response_model=None)
async def unset_actions(
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> Response:
    """
    Unset default journal.
    """
    try:
        actions.default_journal_delete(db_session, request.state.user_id)
    except PreferenceLocked as e:
        logger.error(repr(e))
        raise HTTPException(status_code=423)

    return Response(status_code=200)
