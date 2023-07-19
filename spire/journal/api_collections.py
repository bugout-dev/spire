import logging
from typing import List, Optional
from uuid import UUID

from elasticsearch import Elasticsearch
from fastapi import BackgroundTasks, Body, Depends, FastAPI, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .. import db, es
from ..data import VersionResponse
from ..middleware import BroodAuthMiddleware
from ..utils.settings import (
    DOCS_PATHS,
    DOCS_TARGET_PATH,
    SPIRE_OPENAPI_LIST,
    SPIRE_RAW_ORIGINS_LST,
)
from . import handlers, search
from .data import (
    CollectionSearchResponse,
    EntitiesResponse,
    Entity,
    EntityCollection,
    EntityCollectionResponse,
    EntityCollectionsResponse,
    EntityList,
    EntityResponse,
    JournalRepresentationTypes,
)
from .version import SPIRE_COLLECTIONS_VERSION

SUBMODULE_NAME = "collections"

logger = logging.getLogger(__name__)

tags_metadata = [
    {"name": "collections", "description": "Operations with collections."},
    {"name": "entities", "description": "Operations with collection entities."},
    {"name": "tags", "description": "Operations with collection entity tags."},
    {"name": "permissions", "description": "Collection access managements."},
    {"name": "search", "description": "Collection search."},
]

app = FastAPI(
    title=f"Spire {SUBMODULE_NAME} submodule",
    description="Spire API endpoints to work with entities, statistics and search in collections.",
    version=SPIRE_COLLECTIONS_VERSION,
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
    Spire collections submodule version.
    """
    return VersionResponse(version=SPIRE_COLLECTIONS_VERSION)


@app.get(
    "/",
    tags=["collections"],
    response_model=EntityCollectionsResponse,
)
async def list_collections(
    request: Request,
    db_session: Session = Depends(db.yield_connection_from_env),
) -> EntityCollectionsResponse:
    """
    List all collections user has access to.
    """
    result = await handlers.list_journals_handler(
        db_session=db_session,
        request=request,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.post(
    "/",
    tags=["collections"],
    response_model=EntityCollectionResponse,
)
async def create_collection(
    request: Request,
    create_request: EntityCollection = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> EntityCollectionResponse:
    """
    Creates a collection object for the authenticated user.
    """
    result = await handlers.create_journal_handler(
        db_session=db_session,
        request=request,
        create_request=create_request,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.delete(
    "/{collection_id}",
    tags=["collections"],
    response_model=EntityCollectionResponse,
)
async def delete_collection(
    request: Request,
    collection_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityCollectionResponse:
    """
    Soft delete the collection with the given ID (assuming the collection was created by the authenticated
    user).
    """
    result = await handlers.delete_journal_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        es_client=es_client,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.post(
    "/{collection_id}/entities",
    tags=["entities"],
    response_model=EntityResponse,
)
async def create_collection_entity(
    request: Request,
    collection_id: UUID = Path(...),
    create_request: Entity = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityResponse:
    """
    Creates a collection entity.
    """
    result = await handlers.create_journal_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        create_request=create_request,
        es_client=es_client,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.post(
    "/{collection_id}/bulk",
    tags=["entities"],
    response_model=EntitiesResponse,
)
async def create_collection_entities_pack(
    request: Request,
    collection_id: UUID = Path(...),
    create_request: EntityList = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntitiesResponse:
    """
    Creates a pack of collection entities.
    """
    result = await handlers.create_journal_entries_pack_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        create_request=create_request,
        es_client=es_client,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.get(
    "/{collection_id}/entities",
    tags=["entities"],
    response_model=EntitiesResponse,
)
async def get_entities(
    request: Request,
    collection_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    context_type: Optional[str] = Query(None),
    context_id: Optional[str] = Query(None),
    context_url: Optional[str] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
) -> EntitiesResponse:
    """
    List all entities in a collection.
    """
    result = await handlers.get_entries_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        limit=limit,
        offset=offset,
        representation=JournalRepresentationTypes.COLLECTION,
        context_type=context_type,
        context_id=context_id,
        context_url=context_url,
    )

    return result


@app.delete(
    "/{collection_id}/entities/{entity_id}",
    tags=["entities"],
    response_model=EntityResponse,
)
async def delete_entity(
    request: Request,
    collection_id: UUID = Path(...),
    entity_id: UUID = Path(...),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> EntityResponse:
    """
    Deletes collection entity.
    """
    result = await handlers.delete_entry_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        entry_id=entity_id,
        es_client=es_client,
        representation=JournalRepresentationTypes.COLLECTION,
    )

    return result


@app.get(
    "/{collection_id}/search",
    tags=["search"],
    response_model=CollectionSearchResponse,
)
async def search_journal(
    request: Request,
    background_tasks: BackgroundTasks,
    collection_id: UUID = Path(...),
    q: str = Query(""),
    filters: Optional[List[str]] = Query(None),
    limit: int = Query(10),
    offset: int = Query(0),
    content: bool = Query(True),
    order: search.ResultsOrder = Query(search.ResultsOrder.DESCENDING),
    db_session: Session = Depends(db.yield_connection_from_env),
    es_client: Elasticsearch = Depends(es.yield_es_client_from_env),
) -> CollectionSearchResponse:
    """
    Executes a search query against the given collection.
    """
    result = await handlers.search_journal_handler(
        db_session=db_session,
        request=request,
        journal_id=collection_id,
        es_client=es_client,
        background_tasks=background_tasks,
        q=q,
        limit=limit,
        offset=offset,
        content=content,
        order=order,
        representation=JournalRepresentationTypes.COLLECTION,
        filters=filters,
    )

    return result
