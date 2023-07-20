import json
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Set, Union, cast
from uuid import UUID

from elasticsearch import Elasticsearch
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.orm import Session

from ..utils.settings import DEFAULT_JOURNALS_ES_INDEX
from . import actions, search
from .data import (
    CollectionScopeSpec,
    ContextSpec,
    CreateJournalAPIRequest,
    CreateJournalEntryRequest,
    CreateJournalEntryTagRequest,
    CreateJournalRequest,
    Entity,
    EntityCollection,
    EntryUpdateTagActions,
    JournalEntryContent,
    JournalEntryListContent,
    JournalEntryScopes,
    JournalRepresentationTypes,
    JournalScopes,
    JournalScopeSpec,
    JournalSpec,
    JournalTypes,
    UpdateJournalScopesAPIRequest,
)
from .models import JournalEntryTag
from .representations import journal_representation_parsers, parse_entity_to_entry

logger = logging.getLogger(__name__)


# list_journals_handler operates for api endpoints:
# - list_journals
# - list_collections
async def list_journals_handler(
    db_session: Session, request: Request, representation: JournalRepresentationTypes
):
    try:
        journals = await actions.find_journals(
            db_session=db_session,
            user_id=request.state.user_id,
            user_group_id_list=request.state.user_group_id_list,
        )

        parsed_journals = []
        for j in journals:
            obj = await journal_representation_parsers[representation]["journal"](
                j, j.holders_ids
            )
            parsed_journals.append(obj)

        result = await journal_representation_parsers[representation]["journals"](
            parsed_journals
        )
    except actions.JournalNotFound:
        logger.error(f"Journals not found for user={request.state.user_id}")
        raise HTTPException(status_code=404)
    except Exception as err:
        logger.error(err)
        raise HTTPException(status_code=500)

    return result


# create_journal_handler operates for api endpoints:
# - create_journal
# - create_collection
async def create_journal_handler(
    db_session: Session,
    request: Request,
    create_request: Union[CreateJournalAPIRequest, EntityCollection],
    representation: JournalRepresentationTypes,
):
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

        result = await journal_representation_parsers[representation]["journal"](
            journal, {holder.holder_id for holder in journal.permissions}
        )
    except Exception as e:
        logger.error(f"Error creating journal: {str(e)}")
        raise HTTPException(status_code=500)

    return result


# delete_journal_handler operates for api endpoints:
# - delete_journal
# - delete_collection
async def delete_journal_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    es_client: Elasticsearch,
    representation: JournalRepresentationTypes,
):
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

    return await journal_representation_parsers[representation]["journal"](
        journal, {holder.holder_id for holder in journal.permissions}
    )


# create_journal_entry_handler operates for api endpoints:
# - create_journal_entry
# - create_collection_entity
async def create_journal_entry_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    create_request: Union[JournalEntryContent, Entity],
    es_client: Elasticsearch,
    representation: JournalRepresentationTypes,
):
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.CREATE},
    )
    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)

    tags: List[str]
    if representation == JournalRepresentationTypes.JOURNAL:
        creation_request = CreateJournalEntryRequest(
            journal_spec=journal_spec,
            title=create_request.title,
            content=create_request.content,
            tags=create_request.tags,
            context_type=create_request.context_type,
            context_id=create_request.context_id,
            context_url=create_request.context_url,
        )

        if create_request.created_at is not None:
            created_at_utc = datetime.astimezone(
                create_request.created_at, tz=timezone.utc
            )
            created_at = created_at_utc.replace(tzinfo=None)
            creation_request.created_at = created_at

        tags = create_request.tags if create_request.tags is not None else []
    elif representation == JournalRepresentationTypes.COLLECTION:
        title, tags, content = parse_entity_to_entry(
            create_entity=create_request,
        )
        creation_request = CreateJournalEntryRequest(
            journal_spec=journal_spec,
            title=title,
            content=json.dumps(content),
            tags=tags,
            context_type="entity",
        )
    else:
        raise HTTPException(status_code=500)

    es_index = journal.search_index
    try:
        journal_entry, entry_lock = await actions.create_journal_entry(
            db_session=db_session,
            journal=journal,
            entry_request=creation_request,
            locked_by=request.state.user_id,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error creating journal entry: {str(e)}")
        raise HTTPException(status_code=500)

    if es_index is not None:
        try:
            search.new_entry(
                es_client,
                es_index=es_index,
                journal_id=journal_entry.journal_id,
                entry_id=journal_entry.id,
                title=journal_entry.title,
                content=journal_entry.content,
                tags=tags,
                created_at=journal_entry.created_at,
                updated_at=journal_entry.updated_at,
                context_type=journal_entry.context_type,
                context_id=journal_entry.context_id,
                context_url=journal_entry.context_url,
            )
        except Exception as e:
            logger.warning(
                f"Error indexing journal entry ({journal_entry.id}) in journal "
                f"({journal_entry.journal_id}) for user ({request.state.user_id})"
            )

    return await journal_representation_parsers[representation]["entry"](
        id=journal_entry.id,
        journal_id=journal_entry.journal_id,
        title=journal_entry.title,
        content=journal_entry.content,
        url=str(request.url).rstrip("/"),
        tags=tags,
        created_at=journal_entry.created_at,
        updated_at=journal_entry.updated_at,
        context_url=journal_entry.context_url,
        context_type=journal_entry.context_type,
        context_id=journal_entry.context_id,
        locked_by=entry_lock.locked_by,
    )


# create_journal_entries_pack_handler operates for api endpoints:
# - create_journal_entries_pack
# - create_collection_entities_pack
async def create_journal_entries_pack_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    create_request: Union[JournalEntryListContent, Entity],
    es_client: Elasticsearch,
    representation: JournalRepresentationTypes,
):
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.CREATE},
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

    try:
        response = await actions.create_journal_entries_pack(
            db_session,
            journal.id,
            create_request,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error creating journal entry: {str(e)}")
        raise HTTPException(status_code=500)

    es_index = journal.search_index
    if es_index is not None:
        e_list = (
            response.entities
            if representation == JournalRepresentationTypes.COLLECTION
            else response.entries
        )
        search.bulk_create_entries(es_client, es_index, journal_id, e_list)

    return response


# get_entries_handler operates for api endpoints:
# - get_entries
# - get_entities
async def get_entries_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    limit: int,
    offset: int,
    representation: JournalRepresentationTypes,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_url: Optional[str] = None,
):
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)
    context_spec = ContextSpec(
        context_type=context_type, context_id=context_id, context_url=context_url
    )
    try:
        entries = await actions.get_journal_entries(
            db_session,
            journal_spec,
            None,
            user_group_id_list=request.state.user_group_id_list,
            context_spec=context_spec,
            limit=limit,
            offset=offset,
        )
    except actions.JournalNotFound:
        logger.error(
            f"Journal not found with ID={journal_id} for user={request.state.user_id}"
        )
        raise HTTPException(status_code=404)
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    parsed_entries = []

    for e in entries:
        tag_objects = await actions.get_journal_entry_tags(
            db_session,
            journal_spec,
            e.id,
            user_group_id_list=request.state.user_group_id_list,
        )

        obj = await journal_representation_parsers[representation]["entry"](
            id=e.id,
            journal_id=journal_id,
            title=e.title,
            content=e.content,
            url=str(request.url).rstrip("/"),
            tags=[tag.tag for tag in tag_objects],
            created_at=e.created_at,
            updated_at=e.updated_at,
            context_url=e.context_url,
            context_type=e.context_type,
            context_id=e.context_id,
            locked_by=None,
        )
        parsed_entries.append(obj)

    return await journal_representation_parsers[representation]["entries"](
        parsed_entries
    )


# get_entry_handler operates for api endpoints:
# - get_entry
# - get_entity
async def get_entry_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    entry_id: UUID,
    representation: JournalRepresentationTypes,
):
    actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.READ},
    )

    try:
        (
            journal_entry,
            tag_objects,
            entry_lock,
        ) = await actions.get_journal_entry_with_tags(
            db_session=db_session, journal_entry_id=entry_id
        )
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    url: str = str(request.url).rstrip("/")

    return await journal_representation_parsers[representation]["entry"](
        id=journal_entry.id,
        journal_id=journal_id,
        title=journal_entry.title,
        content=journal_entry.content,
        url=url,
        tags=[tag.tag for tag in tag_objects],
        created_at=journal_entry.created_at,
        updated_at=journal_entry.updated_at,
        context_url=journal_entry.context_url,
        context_type=journal_entry.context_type,
        context_id=journal_entry.context_id,
        locked_by=None if entry_lock is None else entry_lock.locked_by,
    )


# update_entry_content_handler operates for api endpoints:
# - update_entry_content
# - update_entity_content
# TODO(kompotkot): Entity - Strip title to address and title itself
# TODO(kompotkot): Entity - If updated address - update title
async def update_entry_content_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    entry_id: UUID,
    update_request: Union[JournalEntryContent, Entity],
    es_client: Elasticsearch,
    representation: JournalRepresentationTypes,
    tags_action: EntryUpdateTagActions = EntryUpdateTagActions.merge,
):
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.UPDATE},
    )

    es_index = journal.search_index

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
    except actions.EntryNotFound:
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    if entry_lock is not None and entry_lock.locked_by != request.state.user_id:
        return await journal_representation_parsers[representation]["entry"](
            id=journal_entry.id,
            journal_id=journal_id,
            title=journal_entry.title,
            content=journal_entry.content,
            url=str(request.url).rstrip("/"),
            tags=[tag.tag for tag in tag_objects],
            created_at=journal_entry.created_at,
            updated_at=journal_entry.updated_at,
            context_url=journal_entry.context_url,
            context_type=journal_entry.context_type,
            context_id=journal_entry.context_id,
            locked_by=entry_lock.locked_by,
        )

    title: str
    content: str
    tags: List[str]
    if representation == JournalRepresentationTypes.JOURNAL:
        title = update_request.title
        content = update_request.content
        tags = update_request.tags
    elif representation == JournalRepresentationTypes.COLLECTION:
        title, tags, content_raw = parse_entity_to_entry(
            create_entity=update_request,
        )
        content = json.dumps(content_raw)
    else:
        raise HTTPException(status_code=500)

    try:
        journal_entry, entry_lock = await actions.update_journal_entry(
            db_session=db_session,
            new_title=title,
            new_content=content,
            locked_by=request.state.user_id,
            journal_entry=journal_entry,
            entry_lock=entry_lock,
        )
    except Exception as e:
        logger.error(f"Error updating journal entry: {str(e)}")
        raise HTTPException(status_code=500)

    updated_tag_objects: List[JournalEntryTag] = []
    try:
        if tags_action == EntryUpdateTagActions.replace:
            tag_request = CreateJournalEntryTagRequest(
                journal_entry_id=entry_id, tags=tags
            )
            updated_tag_objects = await actions.update_journal_entry_tags(
                db_session,
                journal,
                entry_id,
                tag_request,
            )
        elif tags_action == EntryUpdateTagActions.merge:
            tag_request = CreateJournalEntryTagRequest(
                journal_entry_id=entry_id, tags=tags
            )
            new_tag_objects = await actions.create_journal_entry_tags(
                db_session,
                journal,
                tag_request,
            )
            updated_tag_objects = tag_objects + new_tag_objects
    except actions.EntryNotFound:
        logger.error(
            f"Entry not found with ID={entry_id} in journal with ID={journal_id}"
        )
        raise HTTPException(status_code=404, detail="Entry not found")
    except Exception as e:
        logger.error(f"Error listing journal entries: {str(e)}")
        raise HTTPException(status_code=500)

    tags = [tag.tag for tag in updated_tag_objects]
    if es_index is not None:
        try:
            search.new_entry(
                es_client,
                es_index=es_index,
                journal_id=journal_entry.journal_id,
                entry_id=journal_entry.id,
                title=journal_entry.title,
                content=journal_entry.content,
                tags=tags,
                created_at=journal_entry.created_at,
                updated_at=journal_entry.updated_at,
                context_type=journal_entry.context_type,
                context_id=journal_entry.context_id,
                context_url=journal_entry.context_url,
            )
        except Exception as e:
            logger.warning(
                f"Error indexing journal entry ({journal_entry.id}) in journal "
                f"({journal_entry.journal_id}) for user ({request.state.user_id})"
            )

    return await journal_representation_parsers[representation]["entry"](
        id=journal_entry.id,
        journal_id=journal_id,
        title=journal_entry.title,
        content=journal_entry.content,
        url=str(request.url).rstrip("/"),
        tags=tags,
        created_at=journal_entry.created_at,
        updated_at=journal_entry.updated_at,
        context_url=journal_entry.context_url,
        context_type=journal_entry.context_type,
        context_id=journal_entry.context_id,
        locked_by=entry_lock.locked_by,
    )


# delete_entry_handler operates for api endpoints:
# - delete_entry
# - delete_entity
async def delete_entry_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    entry_id: UUID,
    es_client: Elasticsearch,
    representation: JournalRepresentationTypes,
):
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.DELETE},
    )

    try:
        journal_entry = await actions.delete_journal_entry(
            db_session,
            journal,
            entry_id,
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

    es_index = journal.search_index
    if es_index is not None:
        try:
            search.delete_entry(
                es_client,
                es_index=es_index,
                journal_id=journal_entry.journal_id,
                entry_id=journal_entry.id,
            )
        except Exception as e:
            logger.warning(
                f"Error deindexing entry ({journal_entry.id}) from index for journal "
                f"({journal_entry.journal_id}) for user ({request.state.user_id})"
            )

    return await journal_representation_parsers[representation]["entry"](
        id=journal_entry.id,
        journal_id=journal_entry.journal_id,
        title=journal_entry.title,
        content=journal_entry.content,
        url=str(request.url).rstrip("/"),
        tags=[],
        created_at=journal_entry.created_at,
        updated_at=journal_entry.updated_at,
        context_url=journal_entry.context_url,
        context_type=journal_entry.context_type,
        context_id=journal_entry.context_id,
        locked_by=None,
    )


# get_journal_permissions_handler operates for api endpoints:
# - get_journal_permissions
# - get_collection_permissions
async def get_journal_permissions_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    holder_ids: str,
    representation: JournalRepresentationTypes,
):
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

    return await journal_representation_parsers[representation]["permissions"](
        journal_id=journal_id, permissions=permissions
    )


# add_journal_scopes_handler operates for api endpoints:
# - add_journal_scopes
# - add_collection_scopes
async def add_journal_scopes_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    create_request: UpdateJournalScopesAPIRequest,
    representation: JournalRepresentationTypes,
):
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
            await journal_representation_parsers[representation]["scope_spec"](
                journal_id=journal_id,
                holder_type=create_request.holder_type,
                holder_id=create_request.holder_id,
                permission=permission,
            )
            for permission in added_permissions
        ]

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

    return await journal_representation_parsers[representation]["scope_specs"](
        scopes=journals_scopes
    )


# search_journal_handler operates for api endpoints:
# - search_journal
# - search_collection
async def search_journal_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    es_client: Elasticsearch,
    background_tasks: BackgroundTasks,
    q: str,
    limit: int,
    offset: int,
    content: bool,
    order: search.ResultsOrder,
    representation: JournalRepresentationTypes,
    filters: Optional[List[str]] = None,
):
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
    if es_index is None:
        total_results, rows = search.search_database(
            db_session, journal_id, search_query, limit, offset, order=order
        )
        max_score: Optional[float] = 1.0

        for entry in rows:
            entry_url = ""
            if representation == JournalRepresentationTypes.JOURNAL:
                entry_url = f"{journal_url}/entries/{str(entry.id)}"
            elif representation == JournalRepresentationTypes.COLLECTION:
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
            if representation == JournalRepresentationTypes.JOURNAL:
                entry_url = f"{journal_url}/entries/{hit['_id']}"
            elif representation == JournalRepresentationTypes.COLLECTION:
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

    response = await journal_representation_parsers[representation]["search_entries"](
        total_results, offset, max_score, next_offset, results
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
