"""
Redirect calls to journals and entries by their permalinks.
"""
import logging
from itertools import chain
from typing import List, Union
from uuid import UUID

from bugout.calls import BugoutUnexpectedResponse
from fastapi import (
    FastAPI,
    Form,
    Request,
    Path,
    Depends,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import user

from . import data
from . import actions
from ..data import VersionResponse
from .. import db
from ..broodusers import bugout_api
from ..middleware import BroodAuthMiddleware
from ..utils.settings import SPIRE_OPENAPI_LIST, DOCS_PATHS, DOCS_TARGET_PATH
from .version import SPIRE_GO_VERSION

SUBMODULE_NAME = "go"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "permalinks", "description": "Journal short link."},
    {"name": "permalink access", "description": "Operations with permalinks."},
]

app = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to manage journal preferences.",
    version=SPIRE_GO_VERSION,
    openapi_tags=tags_metadata,
    openapi_url=f"/{DOCS_TARGET_PATH}/openapi.json"
    if SUBMODULE_NAME in SPIRE_OPENAPI_LIST
    else None,
    docs_url=None,
    redoc_url=f"/{DOCS_TARGET_PATH}",
)

allowed_origins = [
    "https://alpha.bugout.dev",
    "https://bugout.dev",
    "https://journal.bugout.dev",
    "http://localhost:3000",
]

# Important to save consistency for middlewares (stack queue)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BroodAuthMiddleware, whitelist=DOCS_PATHS)


def ensure_journal_permission(
    user_token: UUID, holder_ids_list: List[Union[str, UUID]], journal_id: UUID
) -> None:
    try:
        permissions = bugout_api.get_journal_permissions(
            token=user_token, journal_id=journal_id, holder_ids=holder_ids_list
        )
        permissions_flat = set(
            chain.from_iterable(
                [
                    holder_permissions.permissions
                    for holder_permissions in permissions.permissions
                ]
            )
        )
        if "journals.update" not in permissions_flat:
            raise HTTPException(
                status_code=403,
                detail="You don't have permissions to set journal permalink",
            )
    except BugoutUnexpectedResponse:
        raise HTTPException(status_code=404, detail="Journal doesn't exists")


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """
    Spire go submodule version.
    """
    return VersionResponse(version=SPIRE_GO_VERSION)


@app.get("/{journal_permalink}", tags=["permalinks"])
async def journal_by_permalink_handler(
    journal_permalink: str = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> RedirectResponse:
    """
    Get journal by short link.
    """
    try:
        journal_id, journal_public = await actions.extract_permalink(
            db_session, data.RecordType.journal, journal_permalink
        )
    except actions.JournalPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for requested journal",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    if journal_public:
        url = f"/public/{str(journal_id)}"
    else:
        url = f"/journals/{str(journal_id)}"

    return RedirectResponse(url=url)


@app.get("/{journal_permalink}/entries", tags=["permalinks"])
async def journal_entries_by_permalink_handler(
    journal_permalink: str = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> RedirectResponse:
    """
    Get journal entries by short link.
    """
    try:
        journal_id, journal_public = await actions.extract_permalink(
            db_session, data.RecordType.journal, journal_permalink
        )
    except actions.JournalPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for requested journal",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    if journal_public:
        url = f"/public/{str(journal_id)}/entries"
    else:
        url = f"/journals/{str(journal_id)}/entries"

    return RedirectResponse(url=url)


@app.get("/{journal_permalink}/entries/{entry_permalink}", tags=["permalinks"])
async def get_journal_entries_by_permalink_handler(
    journal_permalink: str = Path(...),
    entry_permalink: str = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> RedirectResponse:
    """
    Get specific journal entry by short link.
    """
    try:
        journal_id, journal_public = await actions.extract_permalink(
            db_session, data.RecordType.journal, journal_permalink
        )
        entry_id, _ = await actions.extract_permalink(
            db_session, data.RecordType.entry, entry_permalink
        )
    except actions.JournalPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for requested journal",
        )
    except actions.JournalEntryPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for requested entry",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    if journal_public:
        url = f"/public/{str(journal_id)}/entries/{str(entry_id)}"
    else:
        url = f"/journals/{str(journal_id)}/entries/{str(entry_id)}"

    return RedirectResponse(url=url)


@app.get("/{journal_permalink}/search", tags=["permalinks"])
async def search_permalink_journal_handler(
    request: Request,
    journal_permalink: str = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> RedirectResponse:
    """
    Search accross journal by permalink.
    """
    try:
        journal_id, journal_public = await actions.extract_permalink(
            db_session, data.RecordType.journal, journal_permalink
        )
    except actions.JournalPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for requested journal",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    if journal_public:
        url = f"/public/{str(journal_id)}/search?{str(request.query_params)}"
    else:
        url = f"/journals/{str(journal_id)}/search?{str(request.query_params)}"

    return RedirectResponse(url=url)


@app.post(
    "/permalinks/journal",
    tags=["permalink actions"],
    response_model=data.PermalinkJournalResponse,
)
async def set_journal_permalink(
    request: Request,
    journal_id: UUID = Form(...),
    permalink: str = Form(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> data.PermalinkJournalResponse:
    """
    Creates new permalink if there are no permalinks for specific journal.
    """
    ensure_journal_permission(
        user_token=request.state.token,
        holder_ids_list=[request.state.user_id] + request.state.user_group_id_list,
        journal_id=journal_id,
    )
    try:
        journal_permalink = await actions.set_journal_permalink(
            db_session, journal_id, permalink
        )
    except actions.JournalPermalinkExists:
        raise HTTPException(
            status_code=400,
            detail="Journal permalink already set, please revoke it to be able to add new one",
        )
    except actions.JournalPermalinkBadSymbols:
        raise HTTPException(
            status_code=400, detail="Journal permalink contains not allowed symbols"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    return data.PermalinkJournalResponse(
        journal_id=journal_permalink.journal_id,
        permalink=journal_permalink.permalink,
        public=journal_permalink.public,
    )


@app.delete(
    "/permalinks/journal",
    tags=["permalink actions"],
    response_model=data.PermalinkJournalResponse,
)
async def revoke_journal_permalink(
    request: Request,
    journal_id: UUID = Form(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> data.PermalinkJournalResponse:
    """
    Deletes journal permalink.
    """
    ensure_journal_permission(
        user_token=request.state.token,
        holder_ids_list=[request.state.user_id] + request.state.user_group_id_list,
        journal_id=journal_id,
    )
    try:
        journal_permalink = await actions.revoke_journal_permalink(
            db_session, journal_id
        )
    except actions.JournalPermalinkNotFound:
        raise HTTPException(
            status_code=404,
            detail="There is no permalink for provided journal id",
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500)

    return data.PermalinkJournalResponse(
        journal_id=journal_permalink.journal_id,
        permalink=journal_permalink.permalink,
        public=journal_permalink.public,
    )
