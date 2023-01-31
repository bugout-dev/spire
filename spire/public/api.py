"""
Public endpoints.

FastAPI doesn't like Generic Routes https://github.com/tiangolo/fastapi/issues/913#issuecomment
"""
import logging
from typing import List, Optional
from uuid import UUID

from bugout.data import (
    BugoutJournal,
    BugoutJournalEntries,
    BugoutJournalEntry,
    BugoutJournals,
    BugoutSearchResults,
)
from bugout.exceptions import BugoutResponseException
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from ..broodusers import bugout_api
from ..data import VersionResponse
from ..db import yield_db_read_only_session
from ..utils.settings import DOCS_TARGET_PATH, SPIRE_OPENAPI_LIST
from . import actions
from .version import SPIRE_PUBLIC_VERSION

SUBMODULE_NAME = "public"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "public journals", "description": "Operations with public journal."},
]

app_public = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to manage journal preferences.",
    version=SPIRE_PUBLIC_VERSION,
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
app_public.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app_public.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """
    Spire public submodule version.
    """
    return VersionResponse(version=SPIRE_PUBLIC_VERSION)


@app_public.get("/", tags=["public journals"])
async def list_public_journals_handler(
    user_id: UUID = Query(...),
    db_session: Session = Depends(yield_db_read_only_session),
) -> BugoutJournals:
    """
    List journals with public access.
    """
    try:
        public_user = actions.get_public_user(db_session=db_session, user_id=user_id)
        result: BugoutJournals = bugout_api.list_journals(
            token=public_user.restricted_token_id
        )
    except actions.PublicUserNotFound:
        raise HTTPException(status_code=404, detail="Public user not found")
    except BugoutResponseException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

    return result


@app_public.get("/{journal_id}/check", tags=["public journals"])
async def check_journal_public(
    journal_id: UUID = Path(...),
    db_session: Session = Depends(yield_db_read_only_session),
) -> bool:
    """
    Check if journal is available to public access.

    - **journal_id** (uuid): Journal ID
    """
    try:
        actions.get_public_journal(db_session=db_session, journal_id=journal_id)
        return True
    except actions.PublicJournalNotFound:
        return False
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)


@app_public.get("/{journal_id}", tags=["public journals"], response_model=BugoutJournal)
async def get_public_journal_handler(
    journal_id: UUID = Path(...),
    db_session: Session = Depends(yield_db_read_only_session),
) -> BugoutJournal:
    """
    Get public journal.

    - **journal_id** (uuid): Journal ID
    """
    try:
        public_journal = actions.get_public_journal(db_session, journal_id)
        public_user = actions.get_public_user(db_session, public_journal.user_id)

        result = bugout_api.get_journal(
            token=public_user.restricted_token_id, journal_id=public_journal.journal_id
        )
    except actions.PublicJournalNotFound:
        raise HTTPException(status_code=404, detail="Public journal not found")
    except BugoutResponseException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

    return result


@app_public.get(
    "/{journal_id}/entries",
    tags=["public journals"],
    response_model=BugoutJournalEntries,
)
async def get_public_journal_entries_handler(
    journal_id: UUID = Path(...),
    db_session: Session = Depends(yield_db_read_only_session),
) -> BugoutJournalEntries:
    """
    Get list of public journal entries.

    - **journal_id** (uuid): Journal ID
    """
    try:
        public_journal = actions.get_public_journal(db_session, journal_id)
        public_user = actions.get_public_user(db_session, public_journal.user_id)

        result = bugout_api.get_entries(
            token=public_user.restricted_token_id, journal_id=public_journal.journal_id
        )
    except actions.PublicJournalNotFound:
        raise HTTPException(status_code=404, detail="Public journal not found")
    except BugoutResponseException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

    return result


@app_public.get(
    "/{journal_id}/entries/{entry_id}",
    tags=["public journals"],
    response_model=BugoutJournalEntry,
)
async def get_public_journal_entry_handler(
    journal_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    db_session: Session = Depends(yield_db_read_only_session),
) -> BugoutJournalEntry:
    """
    Get public journal entry.

    - **journal_id** (uuid): Journal ID
    - **entry_id** (uuid): Entry ID
    """
    try:
        public_journal = actions.get_public_journal(db_session, journal_id)
        public_user = actions.get_public_user(db_session, public_journal.user_id)

        result = bugout_api.get_entry(
            token=public_user.restricted_token_id,
            journal_id=public_journal.journal_id,
            entry_id=entry_id,
        )
    except actions.PublicJournalNotFound:
        raise HTTPException(status_code=404, detail="Public journal not found")
    except BugoutResponseException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

    return result


@app_public.get(
    "/{journal_id}/search", tags=["public journals"], response_model=BugoutSearchResults
)
async def search_public_journal_handler(
    journal_id: UUID = Path(...),
    q: str = Query(""),
    filters: Optional[List[str]] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
    content: bool = Query(True),
    db_session: Session = Depends(yield_db_read_only_session),
) -> BugoutSearchResults:
    """
    Executes a search query against the given public journal.
    """
    try:
        public_journal = actions.get_public_journal(db_session, journal_id)
        public_user = actions.get_public_user(db_session, public_journal.user_id)

        result = bugout_api.search(
            token=public_user.restricted_token_id,
            journal_id=public_journal.journal_id,
            query=q,
            filters=filters,
            limit=limit,
            offset=offset,
            content=content,
        )
    except actions.PublicJournalNotFound:
        raise HTTPException(status_code=404, detail="Public journal not found")
    except BugoutResponseException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500)

    return result
