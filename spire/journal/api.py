import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast
from uuid import UUID

import boto3
import requests  # type: ignore
from elasticsearch import Elasticsearch
from fastapi import (
    BackgroundTasks,
    Body,
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .. import db, es
from ..data import VersionResponse
from ..middleware import BroodAuthMiddleware
from ..utils.settings import (
    BUGOUT_DRONES_TOKEN,
    BUGOUT_DRONES_TOKEN_HEADER,
    BULK_CHUNKSIZE,
    DEFAULT_JOURNALS_ES_INDEX,
    DOCS_PATHS,
    DOCS_TARGET_PATH,
    DRONES_BUCKET,
    DRONES_BUCKET_STATISTICS_PREFIX,
    DRONES_URL,
    SPIRE_OPENAPI_LIST,
    SPIRE_RAW_ORIGINS_LST,
    STATISTICS_S3_PRESIGNED_URL_EXPIRATION_TIME,
)
from . import actions, handlers, search
from .data import (
    CreateEntriesTagsRequest,
    CreateJournalAPIRequest,
    CreateJournalEntryTagRequest,
    CreateJournalEntryTagsAPIRequest,
    CreateJournalRequest,
    DeleteJournalEntriesByTagsAPIRequest,
    DeleteJournalEntryTagAPIRequest,
    DeletingQuery,
    DronesStatisticsResponce,
    EntitiesResponse,
    Entity,
    EntityList,
    EntityResponse,
    EntryRepresentationTypes,
    EntryUpdateTagActions,
    JournalEntriesBySearchDeletionResponse,
    JournalEntriesByTagsDeletionResponse,
    JournalEntryContent,
    JournalEntryIds,
    JournalEntryListContent,
    JournalEntryResponse,
    JournalEntryScopes,
    JournalEntryTagsResponse,
    JournalPermissionsResponse,
    JournalResponse,
    JournalScopes,
    JournalScopesAPIRequest,
    JournalScopeSpec,
    JournalSearchResultsResponse,
    JournalSpec,
    JournalStatisticsResponse,
    JournalStatisticsSpecs,
    JournalTypes,
    ListJournalEntriesResponse,
    ListJournalScopeSpec,
    ListJournalsResponse,
    ListScopesResponse,
    ScopeResponse,
    StatsTypes,
    TagUsage,
    TimeScale,
    UpdateJournalScopesAPIRequest,
    UpdateJournalSpec,
    UpdateStatsRequest,
)
from .representations import journal_representation_parsers
from .version import SPIRE_JOURNALS_VERSION

SUBMODULE_NAME = "journals"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "journals", "description": "Operations with journal."},
    {"name": "entries", "description": "Operations with journal entry."},
    {
        "name": "entities",
        "description": "Operations with journal entry in representation as entity.",
    },
    {"name": "tags", "description": "Operations with journal tag."},
    {"name": "statistics", "description": "Journal statistics generation handlers."},
    {"name": "permissions", "description": "Journal access managements."},
    {"name": "search", "description": "Journal search."},
]

app = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to work with entries, statistics and search in journals.",
    version=SPIRE_JOURNALS_VERSION,
    openapi_tags=tags_metadata,
    openapi_url=f"/{DOCS_TARGET_PATH}/openapi.json"
    if SUBMODULE_NAME in SPIRE_OPENAPI_LIST
    else None,
    docs_url=None,
    redoc_url=f"/{DOCS_TARGET_PATH}",
)

# Important to save consistency for middlewares (stack queue)
app.add_middleware(
    CORSMiddleware,
    allow_origins=SPIRE_RAW_ORIGINS_LST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BroodAuthMiddleware, whitelist=DOCS_PATHS)


@app.get("/version", response_model=VersionResponse)
async def version() -> VersionResponse:
    """
    Spire journals submodule version.
    """
    return VersionResponse(version=SPIRE_JOURNALS_VERSION)


@app.get("/permissions", tags=["permissions"], response_model=ListScopesResponse)
@app.get("/scopes", include_in_schema=False, response_model=ListScopesResponse)
async def get_scopes(
    create_request: Optional[JournalScopesAPIRequest] = None,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> ListScopesResponse:
    """
    Retrieves the list of possible permissions that can be assigned
    to holders (user or group) for journal.

    - **api** (string): Resource applicable to, e.g. "journals"
    \f
    :param create_request: Journal permissions request.
    """
    # TODO(kompotkot): DEPRECATED! Delete @app.get("/scopes")
    api_signifier = "journals"
    if create_request is not None:
        api_signifier = create_request.api
    try:
        scopes = await actions.get_scopes(db_session, api_signifier)
        return ListScopesResponse(
            scopes=[
                ScopeResponse(
                    api=scope.api,
                    scope=scope.scope,
                    description=scope.description,
                )
                for scope in scopes
            ]
        )
    except actions.PermissionsNotFound:
        raise HTTPException(status_code=404)


@app.get(
    "/{journal_id}/scopes", tags=["permissions"], response_model=ListJournalScopeSpec
)
async def get_journal_scopes_handler(
    journal_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> ListJournalScopeSpec:
    """
    Retrieves the journal permissions with the given user_id or list of group_id
    user belongs to.

    - **journal_id** (uuid): Journal ID to extract permissions from
    \f
    :param journal_id: Journal ID to extract permissions from.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.READ},
    )

    try:
        journals_p = await actions.get_journal_scopes(
            db_session,
            request.state.user_id,
            request.state.user_group_id_list,
            journal_id,
        )

        journals_scopes = [
            JournalScopeSpec(
                holder_type=journal_p.holder_type,
                journal_id=journal_p.journal_id,
                holder_id=journal_p.holder_id,
                permission=journal_p.permission,
            )
            for journal_p in journals_p
        ]

        return ListJournalScopeSpec(scopes=journals_scopes)

    except actions.PermissionsNotFound:
        logger.error(f"No permissions found for journal_id={journal_id}")
        raise HTTPException(status_code=404)
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")


@app.get(
    "/{journal_id}/permissions",
    tags=["permissions"],
    response_model=JournalPermissionsResponse,
)
async def get_journal_permissions(
    request: Request,
    journal_id: UUID = Path(...),
    holder_ids: Optional[str] = Query(None),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalPermissionsResponse:
    """
    If requester has JournalScopes.READ permission on a journal,
    they can see all permission holders for that journal.

    - **journal_id** (uuid): Journal ID to extract permissions from
    - **holder_ids** (list, None): Filter our holders (user or group) by ID
    \f
    :param journal_id: Journal ID to extract permissions from.
    :param holder_ids: Filter our holders (user or group) by ID.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.READ},
    )

    permissions = await actions.get_journal_permissions(
        db_session,
        journal_id,
        holder_ids.split(",") if holder_ids is not None else None,
    )

    return JournalPermissionsResponse(journal_id=journal_id, permissions=permissions)


@app.post(
    "/{journal_id}/scopes", tags=["permissions"], response_model=ListJournalScopeSpec
)
async def add_journal_scopes(
    request: Request,
    create_request: UpdateJournalScopesAPIRequest = Body(...),
    journal_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> ListJournalScopeSpec:
    """
    Add journal permission if user has access to.

    Only group type allowed for updating scopes.
    Only groups available to user can be managed.

    - **holder_type**: User or group
    - **holder_id**: User or group ID
    - **permissions**: List of permissions to update
    \f
    :param journal_id: Journal ID to extract permissions from.
    :param create_request: Journal permissions parameters.
    """
    ensure_permissions_set: Set[Union[JournalScopes, JournalEntryScopes]] = {
        JournalScopes.UPDATE
    }
    if JournalScopes.DELETE.value in create_request.permissions:
        ensure_permissions_set.add(JournalScopes.DELETE)
    if JournalEntryScopes.DELETE.value in create_request.permissions:
        ensure_permissions_set.add(JournalEntryScopes.DELETE)

    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        ensure_permissions_set,
    )
    user_token = request.state.token
    try:
        added_permissions = await actions.update_journal_scopes(
            user_token,
            db_session,
            create_request.holder_type,
            create_request.holder_id,
            create_request.permissions,
            journal_id,
        )
        journals_scopes = [
            JournalScopeSpec(
                journal_id=journal_id,
                holder_type=create_request.holder_type,
                holder_id=create_request.holder_id,
                permission=permission,
            )
            for permission in added_permissions
        ]

        return ListJournalScopeSpec(scopes=journals_scopes)

    except actions.PermissionsNotFound:
        logger.error(f"No permissions for journal_id={journal_id}")
        raise HTTPException(status_code=404)
    except actions.PermissionAlreadyExists:
        logger.error(f"Provided permission already exists for journal_id={journal_id}")
        raise HTTPException(status_code=409)
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")


@app.delete(
    "/{journal_id}/scopes", tags=["permissions"], response_model=ListJournalScopeSpec
)
async def delete_journal_scopes(
    request: Request,
    delete_request: UpdateJournalScopesAPIRequest = Body(...),
    journal_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> ListJournalScopeSpec:
    """
    Delete journal permission if user has access to it.
    journal.update permission required.

    - **holder_type**: User or group
    - **holder_id**: User or group ID
    - **permissions**: List of permissions to delete
    \f
    :param journal_id: Journal ID to extract permissions from.
    :param delete_request: Journal permissions parameters.
    """
    if delete_request.holder_type == "group":
        if delete_request.holder_id not in request.state.user_group_id_list_owner:
            raise HTTPException(
                status_code=400,
                detail="Only group owner/admin allowed to manage group in journal",
            )
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.UPDATE},
    )
    user_token = request.state.token
    try:
        added_permissions = await actions.delete_journal_scopes(
            user_token,
            db_session,
            delete_request.holder_type,
            delete_request.holder_id,
            delete_request.permissions,
            journal_id,
        )
        journals_scopes = [
            JournalScopeSpec(
                journal_id=journal_id,
                holder_type=delete_request.holder_type,
                holder_id=delete_request.holder_id,
                permission=permission,
            )
            for permission in added_permissions
        ]

        return ListJournalScopeSpec(scopes=journals_scopes)

    except actions.PermissionsNotFound:
        logger.error(f"No permissions for journal_id={journal_id}")
        raise HTTPException(status_code=404)
    except actions.PermissionAlreadyExists:
        logger.error(f"Provided permission already exists for journal_id={journal_id}")
        raise HTTPException(status_code=409)
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")


@app.get(
    "/",
    tags=["journals"],
    response_model=ListJournalsResponse,
)
async def list_journals(
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> ListJournalsResponse:
    """
    List all journals user has access to.
    """
    try:
        journals = await actions.find_journals(
            db_session=db_session,
            user_id=request.state.user_id,
            user_group_id_list=request.state.user_group_id_list,
        )

        journal_responses = [
            JournalResponse(
                id=journal.id,
                bugout_user_id=journal.bugout_user_id,
                holder_ids=journal.holders_ids,
                name=journal.name,
                created_at=journal.created_at,
                updated_at=journal.updated_at,
            )
            for journal in journals
        ]
    except actions.JournalNotFound:
        logger.error(f"Journals not found for user={request.state.user_id}")
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error list journals: {str(e)}")
        raise HTTPException(status_code=500)

    return ListJournalsResponse(journals=journal_responses)


@app.post(
    "/",
    tags=["journals"],
    response_model=JournalResponse,
)
async def create_journal(
    request: Request,
    create_request: CreateJournalAPIRequest = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalResponse:
    """
    Creates a journal object for the authenticated user.
    """
    search_index: Optional[str] = DEFAULT_JOURNALS_ES_INDEX
    if create_request.journal_type == JournalTypes.HUMBUG:
        search_index = None

    journal_request = CreateJournalRequest(
        bugout_user_id=request.state.user_id,
        name=create_request.name,
        search_index=search_index,
    )
    try:
        journal = await actions.create_journal(db_session, journal_request)
    except Exception as e:
        logger.error(f"Error creating journal: {str(e)}")
        raise HTTPException(status_code=500)

    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids={holder.holder_id for holder in journal.permissions},
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


@app.get("/{journal_id}", tags=["journals"], response_model=JournalResponse)
async def get_journal(
    journal_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalResponse:
    """
    Retrieves the journal with the given ID (assuming the journal was created
    by the authenticated user).

    :param journal_id: Journal ID to extract permissions from
    """
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.READ},
    )

    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids={holder.holder_id for holder in journal.permissions},
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


@app.put("/{journal_id}", tags=["journals"], response_model=JournalResponse)
async def update_journal(
    journal_id: UUID,
    update_request: CreateJournalAPIRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalResponse:
    """
    Updates the given journal using the parameters in the update_request
    assuming the journal was created by the authenticated user.

    :param journal_id: Journal ID to extract permissions from
    :param update_request: Journal parameters
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    update_spec = UpdateJournalSpec(name=update_request.name)
    try:
        journal = await actions.update_journal(
            db_session,
            journal_spec,
            update_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error updating journal: {str(e)}")
        raise HTTPException(status_code=500)

    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids={holder.holder_id for holder in journal.permissions},
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


@app.delete(
    "/{journal_id}",
    tags=["journals"],
    response_model=JournalResponse,
)
async def delete_journal(
    request: Request,
    journal_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalResponse:
    """
    Soft delete the journal with the given ID (assuming the journal was created by the authenticated
    user).
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.DELETE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.delete_journal(
            db_session,
            journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error deleting journal: {str(e)}")
        raise HTTPException(status_code=500)

    es_index = journal.search_index

    search.delete_journal_entries(es_client, es_index=es_index, journal_id=journal_id)

    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids={holder.holder_id for holder in journal.permissions},
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


@app.post("/{journal_id}/stats", response_model=DronesStatisticsResponce)
async def update_journal_stats(
    journal_id: UUID,
    request: Request,
    update_request: UpdateStatsRequest,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> DronesStatisticsResponce:
    """
    Return journal statistics
    journal.read permission required.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.READ},
    )

    drones_statistics = requests.post(
        f"{DRONES_URL}/jobs/stats_update",
        json={
            "journal_id": str(journal_id),
            "stats_version": update_request.stats_version,
            "stats_type": update_request.stats_type,
            "timescale": update_request.timescale,
        },
        headers={BUGOUT_DRONES_TOKEN_HEADER: BUGOUT_DRONES_TOKEN},  # type: ignore
        timeout=7,
    ).json()
    return DronesStatisticsResponce.parse_obj(drones_statistics)


@app.get(
    "/{journal_id}/stats",
    tags=["statistics"],
    response_model=JournalStatisticsResponse,
)
async def generate_journal_stats(
    journal_id: UUID,
    request: Request,
    tags: List[str] = Query(None),
    entries_hour: Optional[bool] = Query(None),
    entries_day: Optional[bool] = Query(None),
    entries_week: Optional[bool] = Query(None),
    entries_month: Optional[bool] = Query(None),
    entries_total: Optional[bool] = Query(None),
    most_used_tags: Optional[bool] = Query(None),
    timescales: List[str] = Query(None),
    stats_files: List[str] = Query(None),
    stats_version: int = Query(5),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalStatisticsResponse:
    """
    Return journal statistics
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    stats_spec = JournalStatisticsSpecs(
        entries_hour=entries_hour,
        entries_day=entries_day,
        entries_week=entries_week,
        entries_month=entries_month,
        entries_total=entries_total,
        most_used_tags=most_used_tags,
    )

    # Generate link to S3 buket

    s3_version_prefix = "v5/"
    if stats_version == 2:
        s3_version_prefix = "v2/"
    elif stats_version == 3:
        s3_version_prefix = "v3/"
    elif stats_version == 4:
        s3_version_prefix = "v4/"
    elif stats_version != 5:
        raise HTTPException(400, f"Invalid stats_version={stats_version}")

    try:
        statistics = await actions.journal_statistics(
            db_session,
            journal_spec,
            stats_spec=stats_spec,
            tags=tags,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retriving journal stats: {str(e)}")
        raise HTTPException(status_code=500)

    if stats_version >= 5:
        available_timescales = [timescale.value for timescale in TimeScale]

        available_stats_files = [stats_type.value for stats_type in StatsTypes]

        if not stats_files:
            stats_files = available_stats_files
        else:
            stats_files = [
                stats_type
                for stats_type in stats_files
                if stats_type in available_stats_files
            ]

        if not timescales:
            timescales = available_timescales
        else:
            timescales = [
                timescale
                for timescale in timescales
                if timescale in available_timescales
            ]

        stats_urls: Dict[str, Union[str, Dict[str, str]]] = {}

        s3_client = boto3.client("s3")

        for timescale in timescales:
            timescale_stats: Dict[str, str] = {}
            for stats_file in stats_files:
                # Generate link to S3 buket
                try:
                    result_key = f"{DRONES_BUCKET_STATISTICS_PREFIX}/{journal_id}/{s3_version_prefix}{timescale}/{stats_file}.json"
                    stats_presigned_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": DRONES_BUCKET, "Key": result_key},
                        ExpiresIn=STATISTICS_S3_PRESIGNED_URL_EXPIRATION_TIME,
                        HttpMethod="GET",
                    )
                    timescale_stats[stats_file] = stats_presigned_url
                except Exception as err:
                    logger.warning(
                        f"Can't generate S3 presigned url in stats endpoint for Bucket:{DRONES_BUCKET}, Key:{result_key} get error:{err}"
                    )
            stats_urls[timescale] = timescale_stats

        statistics.journal_statistics = stats_urls

    elif stats_version < 5:
        stats_files = ["stats", "errors", "users"]

        stats_urls = {}

        s3_client = boto3.client("s3")
        for stats_file in stats_files:
            # Generate link to S3 buket
            try:
                result_key = f"{DRONES_BUCKET_STATISTICS_PREFIX}/{journal_id}/{s3_version_prefix}{stats_file}.json"
                stats_presigned_url = s3_client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": DRONES_BUCKET, "Key": result_key},
                    ExpiresIn=STATISTICS_S3_PRESIGNED_URL_EXPIRATION_TIME,
                    HttpMethod="GET",
                )
                stats_urls[stats_file] = stats_presigned_url
            except Exception as err:
                logger.warning(
                    f"Can't generate S3 presigned url in stats endpoint for Bucket:{DRONES_BUCKET}, Key:{result_key} get error:{err}"
                )

        statistics.journal_statistics = stats_urls.get("stats")
        statistics.journal_errors_statistics = cast(str, stats_urls.get("errors"))
        statistics.journal_users_statistics = cast(str, stats_urls.get("users"))

    return statistics


@app.post(
    "/{journal_id}/entries",
    tags=["entries"],
    response_model=JournalEntryResponse,
)
async def create_journal_entry(
    request: Request,
    journal_id: UUID = Path(...),
    create_request: JournalEntryContent = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntryResponse:
    """
    Creates a journal entry
    """
    result = await handlers.create_journal_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        create_request=create_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTRY,
    )

    return result


@app.post(
    "/{journal_id}/entities",
    tags=["entities"],
    response_model=EntityResponse,
)
async def create_journal_entity(
    request: Request,
    journal_id: UUID = Path(...),
    create_request: Entity = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityResponse:
    """
    Creates a journal entity.
    """
    result = await handlers.create_journal_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        create_request=create_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTITY,
    )

    return result


@app.post(
    "/{journal_id}/entries/bulk",
    tags=["entries"],
    response_model=ListJournalEntriesResponse,
)
@app.post(
    "/{journal_id}/bulk",
    tags=["entries"],
    response_model=ListJournalEntriesResponse,
)
async def create_journal_entries_pack(
    request: Request,
    journal_id: UUID = Path(...),
    create_request: JournalEntryListContent = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> ListJournalEntriesResponse:
    """
    Creates a pack of journal entries.
    """
    result = await handlers.create_journal_entries_pack_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        create_request=create_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTRY,
    )

    return result


@app.post(
    "/{journal_id}/entities/bulk",
    tags=["entities"],
    response_model=EntitiesResponse,
)
async def create_journal_entities_pack(
    request: Request,
    journal_id: UUID = Path(...),
    create_request: EntityList = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntitiesResponse:
    """
    Creates a pack of journal entities.
    """
    result = await handlers.create_journal_entries_pack_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        create_request=create_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTITY,
    )

    return result


@app.get(
    "/{journal_id}/entries",
    tags=["entries"],
    response_model=ListJournalEntriesResponse,
)
async def get_entries(
    request: Request,
    journal_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    context_type: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    context_url: Optional[str] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
) -> ListJournalEntriesResponse:
    """
    List all entries in a journal.
    """
    result = await handlers.get_entries_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        limit=limit,
        offset=offset,
        representation=EntryRepresentationTypes.ENTRY,
        context_type=context_type,
        context_id=context_id,
        context_url=context_url,
    )

    return result


@app.get(
    "/{journal_id}/entities",
    tags=["entities"],
    response_model=EntitiesResponse,
)
async def get_entities(
    request: Request,
    journal_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    context_type: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    context_url: Optional[str] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
) -> EntitiesResponse:
    """
    List all entities in a journal.
    """
    result = await handlers.get_entries_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        limit=limit,
        offset=offset,
        representation=EntryRepresentationTypes.ENTITY,
        context_type=context_type,
        context_id=context_id,
        context_url=context_url,
    )

    return result


@app.get(
    "/{journal_id}/entries/{entry_id}",
    tags=["entries"],
    response_model=JournalEntryResponse,
)
async def get_entry(
    journal_id: UUID,
    entry_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalEntryResponse:
    """
    Gets a single journal entry.
    """
    result = await handlers.get_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entry_id,
        representation=EntryRepresentationTypes.ENTRY,
    )

    return result


@app.get(
    "/{journal_id}/entities/{entity_id}",
    tags=["entities"],
    response_model=EntityResponse,
)
async def get_entity(
    journal_id: UUID,
    entity_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> EntityResponse:
    """
    Gets a single journal entity.
    """
    result = await handlers.get_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entity_id,
        representation=EntryRepresentationTypes.ENTITY,
    )

    return result


@app.get(
    "/{journal_id}/entries/{entry_id}/content",
    tags=["entries"],
    response_model=JournalEntryContent,
)
async def get_entry_content(
    journal_id: UUID,
    entry_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalEntryContent:
    """
    Retrieves the text content of a journal entry
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal_entry_container = await actions.get_journal_entries(
            db_session,
            journal_spec,
            entry_id,
            user_group_id_list=request.state.user_group_id_list,
        )
        if len(journal_entry_container) == 0:
            raise actions.EntryNotFound()
        assert len(journal_entry_container) == 1
        journal_entry = journal_entry_container[0]
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    return JournalEntryContent(title=journal_entry.title, content=journal_entry.content)


# TODO(neeraj): Remove /content routes - unnecessarily complicated. This should be coordinated with
# the frontend. The routes should only be removed after the frontend is only using the non-/content
# routes.
@app.put(
    "/{journal_id}/entries/{entry_id}",
    tags=["entries"],
    response_model=JournalEntryContent,
)
@app.put(
    "/{journal_id}/entries/{entry_id}/content",
    include_in_schema=False,
    response_model=JournalEntryContent,
)
async def update_entry_content(
    request: Request,
    journal_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    update_request: JournalEntryContent = Body(...),
    tags_action: EntryUpdateTagActions = Query(EntryUpdateTagActions.merge),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntryContent:
    """
    Modifies the content of a journal entry through a simple override.
    If tags in not empty, update them - delete old and insert new.
    """
    result = await handlers.update_entry_content_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entry_id,
        update_request=update_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTRY,
        tags_action=tags_action,
    )

    return result


@app.put(
    "/{journal_id}/entities/{entity_id}",
    tags=["entities"],
    response_model=EntityResponse,
)
async def update_entity_content(
    request: Request,
    journal_id: UUID = Path(...),
    entity_id: UUID = Path(...),
    update_request: Entity = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityResponse:
    """
    Modifies the content of a journal entity through a simple override.
    """
    result = await handlers.update_entry_content_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entity_id,
        update_request=update_request,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTITY,
        tags_action=EntryUpdateTagActions.replace,
    )

    return result


@app.delete(
    "/{journal_id}/entries/{entry_id}/lock",
    tags=["entries"],
    response_model=JournalEntryContent,
)
async def delete_entry_lock(
    request: Request,
    journal_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalEntryContent:
    """
    Releases journal entry lock.
    Entry may be unlocked by other user.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )
    try:
        (
            journal_entry,
            tag_objects,
            entry_lock,
        ) = await actions.get_journal_entry_with_tags(
            db_session=db_session, journal_entry_id=entry_id
        )
        if journal_entry is None:
            raise actions.EntryNotFound(
                f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
            )
        if entry_lock is not None:
            db_session.delete(entry_lock)
            db_session.commit()
    except actions.EntryNotFound:
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    return JournalEntryContent(
        title=journal_entry.title,
        content=journal_entry.content,
        tags=[tag.tag for tag in tag_objects],
        locked_by=None,
    )


@app.delete(
    "/{journal_id}/entries/{entry_id}",
    tags=["entries"],
    response_model=JournalEntryResponse,
)
async def delete_entry(
    request: Request,
    journal_id: UUID = Path(...),
    entry_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntryResponse:
    """
    Deletes journal entry.
    """
    result = await handlers.delete_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entry_id,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTRY,
    )

    return result


@app.delete(
    "/{journal_id}/entities/{entity_id}",
    tags=["entities"],
    response_model=EntityResponse,
)
async def delete_entity(
    request: Request,
    journal_id: UUID = Path(...),
    entity_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityResponse:
    """
    Deletes journal entity.
    """
    result = await handlers.delete_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=journal_id,
        entry_id=entity_id,
        es_client=es_client,
        representation=EntryRepresentationTypes.ENTITY,
    )

    return result


@app.delete(
    "/{journal_id}/bulk", tags=["entries"], response_model=ListJournalEntriesResponse
)
async def delete_entries(
    journal_id: UUID,
    entries_ids: JournalEntryIds,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> ListJournalEntriesResponse:
    """
    Deletes a journal entries
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.DELETE},
    )
    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)

    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index

    try:
        journal_entries_response = await actions.delete_journal_entries(
            db_session,
            journal_spec,
            entries_ids.entries,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")
    except actions.EntryNotFound:
        logger.error(
            f"Entries not found with entries ids=[{','.join([str(entry_id) for entry_id in entries_ids.entries])}] in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error deleting journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            search.bulk_delete_entries(
                es_client,
                es_index=es_index,
                journal_id=str(journal_id),
                entries_ids=entries_ids.entries,
            )
        except Exception as e:
            logger.warning(
                f"Error deindexing entries ids=[{','.join([str(entry_id) for entry_id in entries_ids.entries])}] from index for journal "
                f"({journal_id}) for user ({request.state.user_id})"
            )
    return journal_entries_response


@app.delete(
    "/{journal_id}/bulk_search",
    tags=["entries"],
    response_model=JournalEntriesBySearchDeletionResponse,
)
async def delete_entries_by_search(
    journal_id: UUID,
    income_search_query: DeletingQuery,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntriesBySearchDeletionResponse:
    """
    Deletes a journal entries
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.DELETE},
    )
    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)

    search_query = income_search_query.search_query

    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)

    if journal.search_index is not None:
        raise HTTPException(status_code=403, detail="Not allowed for indexed journals.")

    limit = 100
    offset = 0

    normalized_query = search.normalized_search_query(
        search_query, filters=[], strict_filter_mode=False
    )

    deleted_count = 0

    total_results, rows = search.search_database(
        db_session, journal_id, normalized_query, 10, 0
    )

    for _ in range(1 + total_results // limit):
        total_results, rows = search.search_database(
            db_session, journal_id, normalized_query, limit, offset
        )

        entries_ids = [entry.id for entry in rows]

        try:
            journal_entries_response = await actions.delete_journal_entries(
                db_session,
                journal_spec,
                entries_ids,
                user_group_id_list=request.state.user_group_id_list,
            )
        except actions.JournalNotFound:
            logger.error(
                f"Journal not found with ID={journal_id} for user={request.state.user_id}"
            )
            raise HTTPException(status_code=404, detail="Journal not found")
        except actions.EntryNotFound:
            logger.error(
                f"Entries not found with entries ids=[{','.join([str(id) for id in entries_ids])}] in journal with ID={journal_id}"
            )
            raise HTTPException(status_code=404, detail="Entry not found")
        except Exception as e:
            logger.error(f"Error deleting journal entries: {str(e)}")
            raise HTTPException(status_code=500)

        deleted_count += len(rows)

    return JournalEntriesBySearchDeletionResponse(
        journal_id=journal_id, num_deleted=deleted_count, search_query=search_query
    )


@app.delete(
    "/{journal_id}/bulk_tags",
    tags=["entries"],
    response_model=JournalEntriesByTagsDeletionResponse,
)
async def delete_entries_by_tags(
    journal_id: UUID,
    tags_request: DeleteJournalEntriesByTagsAPIRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntriesByTagsDeletionResponse:
    """
    Deletes a journal entries by tags list using AND condition
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.DELETE},
    )
    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)

    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)

    es_index = journal.search_index

    num_entries_to_delete = await actions.get_entries_count_by_tags(
        db_session,
        journal.id,
        tags_request.tags,
    )

    for offset in range(0, num_entries_to_delete, BULK_CHUNKSIZE):
        try:
            removed_entries_ids = await actions.hard_delete_by_tags(
                db_session,
                journal.id,
                tags_request.tags,
                limit=offset + BULK_CHUNKSIZE,
                offset=offset,
            )
        except Exception as e:
            logger.error(f"Error hard delete by tag: {str(e)}")
            raise HTTPException(status_code=500)

        if es_index is not None:
            try:
                search.bulk_delete_entries(
                    es_client, es_index, journal.id, removed_entries_ids
                )
            except Exception as e:
                logger.error(
                    f"Warning: deleting by tags exception on bulk delete in elastic: {str(e)}"
                )

    return JournalEntriesByTagsDeletionResponse(
        journal_id=journal.id,
        num_deleted=num_entries_to_delete,
        tags=tags_request.tags,
    )


@app.get("/{journal_id}/tags", tags=["tags"], response_model=List[TagUsage])
async def most_used_tags(
    journal_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> List[TagUsage]:
    """
    Get all tags for a journal entry.
    """

    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        tags: List[Tuple[str, int]] = await actions.get_journal_most_used_tags(
            db_session,
            journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    return [TagUsage(tag=tag[0], count=tag[1]) for tag in tags]


@app.post(
    "/{journal_id}/entries/{entry_id}/tags", tags=["tags"], response_model=List[str]
)
async def create_tags(
    journal_id: UUID,
    entry_id: UUID,
    api_tag_request: CreateJournalEntryTagsAPIRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> List[str]:
    """
    Create tags for a journal entry.
    """
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index

    tag_request = CreateJournalEntryTagRequest(
        journal_entry_id=entry_id, tags=api_tag_request.tags
    )
    try:
        await actions.create_journal_entry_tags(
            db_session,
            journal,
            tag_request,
        )
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            journal_entry = await actions.get_journal_entry(
                db_session=db_session, journal_entry_id=entry_id
            )
            if journal_entry is None:
                raise actions.EntryNotFound(
                    f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
                )
            entry = journal_entry
            all_tags = await actions.get_journal_entry_tags(
                db_session,
                journal_spec,
                entry_id,
                user_group_id_list=request.state.user_group_id_list,
            )
            all_tags_str = [tag.tag for tag in all_tags]
            search.new_entry(
                es_client,
                es_index=es_index,
                journal_id=entry.journal_id,
                entry_id=entry.id,
                title=entry.title,
                content=entry.content,
                tags=all_tags_str,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                context_type=entry.context_type,
                context_id=entry.context_id,
                context_url=entry.context_url,
            )
        except actions.EntryNotFound:
            raise HTTPException(status_code=404, detail="Entry not found")
        except Exception as e:
            logger.warning(
                f"Error creating tags for entry ({str(entry_id)}) in journal ({str(journal_id)}) "
                f"for user ({request.state.user_id}): {repr(e)}"
            )

    return api_tag_request.tags


@app.get(
    "/{journal_id}/entries/{entry_id}/tags",
    tags=["tags"],
    response_model=JournalEntryTagsResponse,
)
async def get_tags(
    journal_id: UUID,
    entry_id: UUID,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> JournalEntryTagsResponse:
    """
    Get all tags for a journal entry.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        tags = await actions.get_journal_entry_tags(
            db_session,
            journal_spec,
            entry_id,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    return JournalEntryTagsResponse(
        journal_id=journal_id, entry_id=entry_id, tags=[tag.tag for tag in tags]
    )


@app.put(
    "/{journal_id}/entries/{entry_id}/tags", tags=["tags"], response_model=List[str]
)
async def update_tags(
    journal_id: UUID,
    entry_id: UUID,
    api_tag_request: CreateJournalEntryTagsAPIRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> List[str]:
    """
    Update tags for a journal entry tags.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index

    tag_request = CreateJournalEntryTagRequest(
        journal_entry_id=entry_id, tags=api_tag_request.tags
    )
    try:
        tags = await actions.update_journal_entry_tags(
            db_session,
            journal,
            entry_id,
            tag_request,
        )
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error journal entries tags update: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            journal_entry = await actions.get_journal_entry(
                db_session=db_session, journal_entry_id=entry_id
            )
            if journal_entry is None:
                raise actions.EntryNotFound(
                    f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
                )
            entry = journal_entry
            all_tags_str = [tag.tag for tag in tags]
            search.new_entry(
                es_client,
                es_index=es_index,
                journal_id=entry.journal_id,
                entry_id=entry.id,
                title=entry.title,
                content=entry.content,
                tags=all_tags_str,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                context_type=entry.context_type,
                context_id=entry.context_id,
                context_url=entry.context_url,
            )
        except actions.EntryNotFound:
            raise HTTPException(status_code=404, detail="Entry not found")
        except Exception as e:
            logger.warning(
                f"Error creating tags for entry ({str(entry_id)}) in journal ({str(journal_id)}) for "
                f"user ({request.state.user_id}): {repr(e)}"
            )

    return api_tag_request.tags


@app.post(
    "/{journal_id}/bulk_entries_tags",
    tags=["tags"],
    response_model=List[JournalEntryResponse],
)
async def create_entries_tags(
    journal_id: UUID,
    entries_tags_request: CreateEntriesTagsRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> List[JournalEntryResponse]:
    """
    Create tags for multiple journal entries.
    """

    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index
    try:
        updated_entry_ids = await actions.create_journal_entries_tags(
            db_session, journal, entries_tags_request
        )
    except actions.EntriesNotFound as e:
        logger.error(f"Entries not found with entries")
        raise HTTPException(
            status_code=404, detail=f"Not entries with ids: {e.entries}"
        )
    except actions.CommitFailed as e:
        logger.error(f"Can't write tags for entries to database")
        raise HTTPException(
            status_code=409, detail=f"Can't write tags for entries to database"
        )
    except Exception as e:
        logger.error(f"Error journal entries tags update: {str(e)}")
        raise HTTPException(status_code=500)

    try:
        entries_objects = await actions.get_journal_entries_with_tags(
            db_session, journal_entries_ids=updated_entry_ids
        )
    except Exception as e:
        logger.error(f"Error get journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            search.bulk_create_entries(
                es_client,
                es_index=es_index,
                journal_id=journal_id,
                entries=entries_objects,
            )

        except Exception as e:
            logger.warning(
                f"Error creating tags for entry ({updated_entry_ids}) in journal ({str(journal_id)}) for "
                f"user ({request.state.user_id}): {repr(e)}"
            )

    return entries_objects


@app.delete(
    "/{journal_id}/bulk_entries_tags",
    tags=["tags"],
    response_model=List[JournalEntryResponse],
)
async def delete_entries_tags(
    journal_id: UUID,
    entries_tags_request: CreateEntriesTagsRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> List[JournalEntryResponse]:
    """
    Delete tags for multiple journal entries.
    """

    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index

    try:
        deleted_entry_ids = await actions.delete_journal_entries_tags(
            db_session, journal, entries_tags_request
        )
    except actions.CommitFailed as e:
        logger.error(f"Can't delete tags form entries")
        raise HTTPException(
            status_code=409, detail=f"Can't delete tags from entries in database"
        )
    except actions.EntriesNotFound as e:
        logger.error(f"Entries not found with entries")
        raise HTTPException(
            status_code=404, detail=f"Not entries with ids: {e.entries}"
        )
    except Exception as e:
        logger.error(f"Error journal entries tags update: {str(e)}")
        raise HTTPException(status_code=500)

    entries_objects = await actions.get_journal_entries_with_tags(
        db_session, journal_entries_ids=deleted_entry_ids
    )

    if es_index is not None:
        try:
            search.bulk_create_entries(
                es_client,
                es_index=es_index,
                journal_id=journal_id,
                entries=entries_objects,
            )

        except Exception as e:
            logger.warning(
                f"Error creating tags for entry ({deleted_entry_ids}) in journal ({str(journal_id)}) for "
                f"user ({request.state.user_id}): {repr(e)}"
            )

    return entries_objects


@app.delete(
    "/{journal_id}/entries/{entry_id}/tags",
    tags=["tags"],
    response_model=JournalEntryTagsResponse,
)
async def delete_tag(
    journal_id: UUID,
    entry_id: UUID,
    api_request: DeleteJournalEntryTagAPIRequest,
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> JournalEntryTagsResponse:
    """
    Delete a tag on a journal entry.

    journal.read permission required.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)
    es_index = journal.search_index

    try:
        tag = await actions.delete_journal_entry_tag(
            db_session,
            journal_spec,
            entry_id,
            api_request.tag,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404, detail="Journal not found")
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error deleting journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            journal_entry = await actions.get_journal_entry(
                db_session=db_session, journal_entry_id=entry_id
            )
            if journal_entry is None:
                raise actions.EntryNotFound(
                    f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
                )
            entry = journal_entry
            all_tags = await actions.get_journal_entry_tags(
                db_session,
                journal_spec,
                entry_id,
                user_group_id_list=request.state.user_group_id_list,
            )
            all_tags_str = [tag.tag for tag in all_tags]
            search.new_entry(
                es_client,
                es_index=es_index,
                journal_id=entry.journal_id,
                entry_id=entry.id,
                title=entry.title,
                content=entry.content,
                tags=all_tags_str,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
                context_type=entry.context_type,
                context_id=entry.context_id,
                context_url=entry.context_url,
            )
        except actions.EntryNotFound:
            raise HTTPException(status_code=404, detail="Entry not found")
        except Exception as e:
            logger.warning(
                f"Error creating tags for entry ({str(entry_id)}) in journal ({str(journal_id)}) for"
                f"user ({request.state.user_id}): {repr(e)}"
            )

    tags = []
    if tag is not None:
        tags.append(tag.tag)
    return JournalEntryTagsResponse(journal_id=journal_id, entry_id=entry_id, tags=tags)


@app.get(
    "/{journal_id}/search",
    tags=["search"],
    response_model=JournalSearchResultsResponse,
)
async def search_journal(
    request: Request,
    background_tasks: BackgroundTasks,
    journal_id: UUID = Path(...),
    q: str = Query(""),
    filters: Optional[List[str]] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
    content: bool = Query(True),
    order: search.ResultsOrder = Query(search.ResultsOrder.DESCENDING),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
    representation: EntryRepresentationTypes = Query(EntryRepresentationTypes.ENTRY),
) -> JournalSearchResultsResponse:
    """
    Executes a search query against the given journal.
    """
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    try:
        journal = await actions.find_journal(
            db_session=db_session,
            journal_spec=journal_spec,
            user_group_id_list=request.state.user_group_id_list,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error retrieving journal: {str(e)}")
        raise HTTPException(status_code=500)

    if filters is None:
        filters = []
    search_query = search.normalized_search_query(q, filters, strict_filter_mode=False)

    url: str = str(request.url).rstrip("/")
    journal_url = "/".join(url.split("/")[:-1])

    results: List[Any] = []

    es_index = journal.search_index
    # TODO: !!!!!!!!!!!!!!
    # TODO: !!!!!!!!!!!!!!
    es_index = None
    # TODO: !!!!!!!!!!!!!!
    # TODO: !!!!!!!!!!!!!!
    if es_index is None:
        total_results, rows = search.search_database(
            db_session, journal_id, search_query, limit, offset, order=order
        )
        max_score: Optional[float] = 1.0

        for entry in rows:
            entry_url = ""
            if representation == EntryRepresentationTypes.ENTRY:
                entry_url = f"{journal_url}/entries/{str(entry.id)}"
            elif representation == EntryRepresentationTypes.ENTITY:
                entry_url = f"{journal_url}/entities/{str(entry.id)}"
            content_url = f"{entry_url}/content"

            result = await journal_representation_parsers[representation][
                "search_entry"
            ](
                str(entry.id),
                str(journal.id),
                entry_url,
                content_url,
                entry.title,
                entry.tags,
                str(entry.created_at),
                str(entry.updated_at),
                1.0,
                entry.context_type,
                entry.context_id,
                entry.context_url,
                entry.content,
            )
            results.append(result)
    else:
        search_results = search.search(
            es_client,
            es_index=es_index,
            journal_id=journal_id,
            search_query=search_query,
            size=limit,
            start=offset,
            order=order,
        )

        total_results = search_results.get("total", {}).get("value", 0)
        max_score = search_results.get("max_score")
        if max_score is None:
            max_score = 0.0

        for hit in search_results.get("hits", []):
            entry_url = ""
            if representation == EntryRepresentationTypes.ENTRY:
                entry_url = f"{journal_url}/entries/{hit['_id']}"
            elif representation == EntryRepresentationTypes.ENTITY:
                entry_url = f"{journal_url}/entities/{hit['_id']}"

            content_url = f"{entry_url}/content"
            source = hit.get("_source", {})
            source_tags: Union[str, List[str]] = source.get("tag", [])
            tags = []
            if source_tags == str(source_tags):
                source_tags = cast(str, source_tags)
                tags = [source_tags]
            else:
                source_tags = cast(List[str], source_tags)
                tags = source_tags

            result = await journal_representation_parsers[representation][
                "search_entry"
            ](
                entry_id=source.get("entry_id", ""),
                journal_id=str(journal.id),
                entry_url=entry_url,
                content_url=content_url,
                title=source.get("title", ""),
                tags=tags,
                created_at=datetime.fromtimestamp(source.get("created_at")).isoformat(),
                updated_at=datetime.fromtimestamp(source.get("updated_at")).isoformat(),
                score=hit.get("_score"),
                context_type=source.get("context_type"),
                context_id=source.get("context_id"),
                context_url=source.get("context_url"),
                content=source.get("content", "") if content is True else None,
            )
            results.append(result)

    next_offset: Optional[int] = None
    if offset + limit < total_results:
        next_offset = offset + limit

    response = JournalSearchResultsResponse(
        total_results=total_results,
        offset=offset,
        next_offset=next_offset,
        max_score=max_score,
        results=results,
    )

    bugout_client_id = actions.bugout_client_id_from_request(request)
    background_tasks.add_task(
        actions.store_search_results,
        search_url=url,
        journal_id=journal_id,
        bugout_user_id=request.state.user_id,
        bugout_client_id=bugout_client_id,
        q=q,
        filters=filters,
        limit=limit,
        offset=offset,
        response=response,
    )

    return response
