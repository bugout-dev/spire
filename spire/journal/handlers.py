import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Union
from uuid import UUID

from elasticsearch import Elasticsearch
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from . import actions, search
from .data import (
    ContextSpec,
    CreateJournalEntryRequest,
    CreateJournalEntryTagRequest,
    EntitiesResponse,
    Entity,
    EntityResponse,
    EntryRepresentationTypes,
    EntryUpdateTagActions,
    JournalEntryContent,
    JournalEntryListContent,
    JournalEntryResponse,
    JournalEntryScopes,
    JournalSpec,
    ListJournalEntriesResponse,
)
from .models import JournalEntryTag
from .representations import journal_representation_parsers, parse_entity_to_entry

logger = logging.getLogger(__name__)


# create_journal_entry_handler operates for api endpoints:
# - create_journal_entry
# - create_journal_entity
async def create_journal_entry_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    create_request: Union[JournalEntryContent, Entity],
    es_client: Elasticsearch,
    representation: EntryRepresentationTypes,
) -> Union[JournalEntryResponse, EntityResponse]:
    journal = actions.ensure_journal_permission(
        db_session,
        request.state.user_id,
        request.state.user_group_id_list,
        journal_id,
        {JournalEntryScopes.CREATE},
    )
    journal_spec = JournalSpec(id=journal_id, bugout_user_id=request.state.user_id)

    tags: List[str]
    if representation == EntryRepresentationTypes.ENTRY:
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
    elif representation == EntryRepresentationTypes.ENTITY:
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
        logger.error(
            f"Unsupported {EntryRepresentationTypes.ENTRY.value} representation type"
        )
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
# - create_journal_entities_pack
async def create_journal_entries_pack_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    create_request: Union[JournalEntryListContent, Entity],
    es_client: Elasticsearch,
    representation: EntryRepresentationTypes,
) -> Union[ListJournalEntriesResponse, EntitiesResponse]:
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
        entries_response = await actions.create_journal_entries_pack(
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
        search.bulk_create_entries(
            es_client, es_index, journal_id, entries_response.entries
        )

    if representation != EntryRepresentationTypes.ENTRY:
        parsed_entries = []
        for e in entries_response.entries:
            obj = await journal_representation_parsers[representation]["entry"](
                id=e.id,
                journal_id=journal_id,
                title=e.title,
                content=e.content,
                url=str(request.url).rstrip("/"),
                tags=e.tags,
                created_at=e.created_at,
                updated_at=e.updated_at,
                context_url=e.context_url,
                context_type=e.context_type,
                context_id=e.context_id,
                locked_by=e.locked_by,
            )
            parsed_entries.append(obj)
        return await journal_representation_parsers[representation]["entries"](
            parsed_entries
        )
    else:
        return entries_response


# get_entries_handler operates for api endpoints:
# - get_entries
# - get_entities
async def get_entries_handler(
    db_session: Session,
    request: Request,
    journal_id: UUID,
    limit: int,
    offset: int,
    representation: EntryRepresentationTypes,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_url: Optional[str] = None,
) -> Union[ListJournalEntriesResponse, EntitiesResponse]:
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
    representation: EntryRepresentationTypes,
) -> Union[JournalEntryResponse, EntityResponse]:
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
    representation: EntryRepresentationTypes,
    tags_action: EntryUpdateTagActions = EntryUpdateTagActions.merge,
) -> Union[JournalEntryContent, EntityResponse]:
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
    if representation == EntryRepresentationTypes.ENTRY:
        title = update_request.title
        content = update_request.content
        tags = update_request.tags
    elif representation == EntryRepresentationTypes.ENTITY:
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
    representation: EntryRepresentationTypes,
) -> Union[JournalEntryResponse, EntityResponse]:
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
