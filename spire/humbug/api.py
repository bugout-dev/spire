import logging
from uuid import UUID

from fastapi import (
    FastAPI,
    Form,
    Query,
    Request,
    Depends,
    Path,
    BackgroundTasks,
    Response,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session

from . import actions
from .data import (
    HumbugCreatReportTask,
    HumbugIntegrationResponse,
    HumbugIntegrationListResponse,
    HumbugTokenResponse,
    HumbugTokenListResponse,
    HumbugReport,
)
from ..data import VersionResponse
from .. import db
from ..middleware import BroodAuthMiddleware
from ..broodusers import bugout_api, BugoutAPICallFailed
from ..utils.settings import SPIRE_OPENAPI_LIST, DOCS_TARGET_PATH, DOCS_PATHS
from .version import SPIRE_HUMBUG_VERSION

SUBMODULE_NAME = "humbug"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "integrations", "description": "Operations with humbug integrations."},
    {"name": "tokens", "description": "Operations with integrations tokens."},
    {"name": "reports", "description": "Integration reports generation handlers."},
]

app = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to work with crash reports integrations.",
    version=SPIRE_HUMBUG_VERSION,
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


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """
    Spire humbug submodule version.
    """
    return VersionResponse(version=SPIRE_HUMBUG_VERSION)


@app.post("/", tags=["integrations"], response_model=HumbugIntegrationResponse)
async def create_humbug_integration_handler(
    request: Request,
    group_id: str = Form(...),
    journal_name: str = Form(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugIntegrationResponse:
    """
    Create new integration for group with journal for crash reports.
    
    - **group_id** (uuid): Group ID attach integration to
    - **journal_name** (string): Name of journal for humbug reports
    """
    user_token = request.state.token
    user_group_id_list = request.state.user_group_id_list
    if group_id not in user_group_id_list:
        raise HTTPException(
            status_code=403, detail="You do not have permission to view this resource"
        )
    try:
        humbug_event_dependencies = actions.generate_humbug_dependencies(
            user_token, group_id, journal_name
        )

        humbug_event = await actions.create_humbug_integration(
            db_session,
            humbug_event_dependencies.journal_id,
            humbug_event_dependencies.group_id,
        )
        await actions.create_humbug_user(
            db_session,
            humbug_event.id,
            humbug_event_dependencies.user_id,
            humbug_event_dependencies.access_token_id,
        )
    except actions.JournalInvalidParameters:
        raise HTTPException(
            status_code=400,
            detail="Existing journal id or new journal name should be specified",
        )
    except BugoutAPICallFailed:
        raise HTTPException(
            status_code=500,
            detail="Unable to complete Humbug integration workflow with Bugout API",
        )

    return HumbugIntegrationResponse(
        id=humbug_event.id,
        group_id=humbug_event.group_id,
        journal_id=humbug_event.journal_id,
        journal_name=humbug_event_dependencies.journal_name,
        created_at=humbug_event.created_at,
        updated_at=humbug_event.updated_at,
    )


@app.get(
    "/integrations", tags=["integrations"], response_model=HumbugIntegrationListResponse
)
async def get_humbug_integration_list_handler(
    request: Request,
    group_id: str = Query(None),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugIntegrationListResponse:
    """
    Lists all integrations for groups user belongs to.
        
    - **group_id** (uuid, null): Filter integrations by group ID.
    """
    user_group_id_list = request.state.user_group_id_list
    if group_id is not None:
        if group_id not in user_group_id_list:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to view this resource",
            )

    integrations_list_response = HumbugIntegrationListResponse(integrations=[])
    try:
        humbug_events = await actions.get_humbug_integrations(
            db_session,
            groups_ids=user_group_id_list if group_id is None else [UUID(group_id)],
        )
    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )
    for event in humbug_events:
        access_token = event.bugout_user.access_token_id
        try:
            journal = bugout_api.get_journal(
                token=access_token, journal_id=event.journal_id
            )
            integration_response = HumbugIntegrationResponse(
                id=event.id,
                group_id=event.group_id,
                journal_id=event.journal_id,
                journal_name=journal.name,
                created_at=event.created_at,
                updated_at=event.updated_at,
            )
            integrations_list_response.integrations.append(integration_response)
        except Exception:
            logger.error(
                f"Missed journal with id: {event.journal_id} for integration id: {event.id}"
            )
            continue

    return integrations_list_response


@app.get(
    "/{humbug_id}", tags=["integrations"], response_model=HumbugIntegrationResponse
)
async def get_humbug_integration_handler(
    request: Request,
    humbug_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugIntegrationResponse:
    """
    Gets a specific integration.

    - **humbug_id** (uuid): Specific integration ID
    - **group_id** (uuid, null): Filter integrations by group ID
    """
    user_group_id_list = request.state.user_group_id_list
    try:
        humbug_event = await actions.get_humbug_integration(
            db_session, humbug_id=humbug_id, groups_ids=user_group_id_list
        )
        access_token = humbug_event.bugout_user.access_token_id
        journal = bugout_api.get_journal(
            token=access_token, journal_id=humbug_event.journal_id
        )
    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )
    return HumbugIntegrationResponse(
        id=humbug_event.id,
        group_id=humbug_event.group_id,
        journal_id=humbug_event.journal_id,
        journal_name=journal.name,
        created_at=humbug_event.created_at,
        updated_at=humbug_event.updated_at,
    )


@app.delete(
    "/{humbug_id}", tags=["integrations"], response_model=HumbugIntegrationResponse
)
async def delete_humbug_integration_handler(
    request: Request,
    background_tasks: BackgroundTasks,
    humbug_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugIntegrationResponse:
    """
    Delete a specific integration.

    - **humbug_id** (uuid): Specific integration ID
    """
    user_token = request.state.token
    user_group_id_list = request.state.user_group_id_list
    try:
        humbug_event = await actions.get_humbug_integration(
            db_session, humbug_id, groups_ids=user_group_id_list
        )
        await actions.delete_humbug_integration(
            db_session, humbug_id, groups_ids=user_group_id_list
        )
    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )

    background_tasks.add_task(
        actions.remove_humbug_dependencies, db_session, user_token, humbug_event,
    )

    return HumbugIntegrationResponse(
        id=humbug_event.id,
        group_id=humbug_event.group_id,
        journal_id=humbug_event.journal_id,
        created_at=humbug_event.created_at,
        updated_at=humbug_event.updated_at,
    )


@app.get("/{humbug_id}/tokens", tags=["tokens"], response_model=HumbugTokenListResponse)
async def get_restricted_token_handler(
    request: Request,
    humbug_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugTokenListResponse:
    """
    The list of restricted tokens returns for integration.

    - **humbug_id** (uuid): Specific integration ID
    """
    # TODO(kompotkot): How to control active token or not?
    user_group_id_list = request.state.user_group_id_list
    try:
        humbug_event = await actions.get_humbug_integration(
            db_session, humbug_id=humbug_id, groups_ids=user_group_id_list
        )
        humbug_tokens = await actions.get_humbug_tokens(
            db_session=db_session,
            event_id=humbug_event.id,
            user_id=humbug_event.bugout_user.user_id,
        )
    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )

    humbug_tokens_response = HumbugTokenListResponse(
        user_id=humbug_event.bugout_user.user_id,
        humbug_id=humbug_event.id,
        tokens=[
            HumbugTokenResponse(
                restricted_token_id=token.restricted_token_id,
                app_name=token.app_name,
                app_version=token.app_version,
            )
            for token in humbug_tokens
        ],
    )
    return humbug_tokens_response


@app.post(
    "/{humbug_id}/tokens", tags=["tokens"], response_model=HumbugTokenListResponse
)
async def create_restricted_token_handler(
    request: Request,
    humbug_id: UUID = Path(...),
    app_name: str = Form(...),
    app_version: str = Form(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugTokenListResponse:
    """
    Create new restricted token for integration.

    - **humbug_id** (uuid): Specific integration ID
    - **app_name** (string): Application name
    - **app_version** (string): Application version
    """
    user_group_id_list = request.state.user_group_id_list
    try:
        humbug_event = await actions.get_humbug_integration(
            db_session, humbug_id=humbug_id, groups_ids=user_group_id_list
        )
        restricted_token = await actions.create_humbug_token(
            db_session=db_session,
            token=humbug_event.bugout_user.access_token_id,
            humbug_user=humbug_event.bugout_user,
            app_name=app_name,
            app_version=app_version,
        )

    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )
    except AssertionError:
        raise HTTPException(status_code=500)

    humbug_tokens_response = HumbugTokenListResponse(
        user_id=restricted_token.user_id,
        humbug_id=humbug_event.id,
        tokens=[
            HumbugTokenResponse(
                restricted_token_id=restricted_token.restricted_token_id,
                app_name=restricted_token.app_name,
                app_version=restricted_token.app_version,
            )
        ],
    )
    return humbug_tokens_response


@app.delete(
    "/{humbug_id}/tokens", tags=["tokens"], response_model=HumbugTokenListResponse
)
async def delete_restricted_token_handler(
    request: Request,
    humbug_id: UUID = Path(...),
    restricted_token_id: UUID = Form(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> HumbugTokenListResponse:
    """
    Revokes restricted token for integration.

    - **humbug_id** (uuid): Specific integration ID
    - **restricted_token_id** (uuid): Restricted token to revoke
    """
    user_group_id_list = request.state.user_group_id_list
    try:
        humbug_event = await actions.get_humbug_integration(
            db_session, humbug_id=humbug_id, groups_ids=user_group_id_list
        )
        restricted_token = await actions.delete_humbug_token(
            db_session, humbug_event.id, restricted_token_id
        )
    except actions.HumbugEventNotFound:
        raise HTTPException(
            status_code=404, detail="Humbug integration not found in database"
        )
    except actions.HumbugTokenNotFound:
        raise HTTPException(
            status_code=404, detail="Provided restricted token id not found"
        )

    humbug_tokens_response = HumbugTokenListResponse(
        user_id=restricted_token.user_id,
        humbug_id=humbug_event.id,
        tokens=[
            HumbugTokenResponse(
                restricted_token_id=restricted_token.restricted_token_id,
                app_name=restricted_token.app_name,
                app_version=restricted_token.app_version,
            )
        ],
    )
    return humbug_tokens_response


@app.post("/reports", tags=["reports"], response_model=None)
async def create_reports_handler(request: Request, report: HumbugReport,) -> Response:
    """
    Add report to integration journal.

    - **title** (string): Entry title
    - **content** (string): Entry content
    - **tags** (list): Entry tags
    """

    restricted_token = request.state.token

    with db.yield_redis_pool() as redis_client:

        redis_client.lpush(
            "reports_queue",
            HumbugCreatReportTask(report=report, bugout_token=restricted_token).json(),
        )

    return Response(status_code=200)
