"""
Manual journal parser depends on representations.
"""

import json
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from .data import (
    EntitiesResponse,
    EntityCollectionResponse,
    EntityCollectionsResponse,
    EntityResponse,
    JournalEntryResponse,
    JournalRepresentationTypes,
    JournalResponse,
    ListJournalEntriesResponse,
    ListJournalsResponse,
)
from .models import Journal, JournalEntry


# Journal parsers
async def parse_journal_model(journal: Journal) -> JournalResponse:
    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids=journal.holders_ids,
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


async def parse_journals_model(journals: List[JournalResponse]) -> ListJournalsResponse:
    return ListJournalsResponse(journals=journals)


async def parse_journal_model_entity(journal: Journal) -> EntityCollectionResponse:
    return EntityCollectionResponse(
        collection_id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids=journal.holders_ids,
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


async def parse_journals_model_entity(
    journals: List[EntityCollectionResponse],
) -> EntityCollectionsResponse:
    return EntityCollectionsResponse(collections=journals)


# Entry parsers
async def parse_entry_model(
    entry: JournalEntry,
    journal_id: UUID,
    journal_url: Optional[str] = None,
    tags: List[str] = [],
) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=entry.id,
        journal_url=journal_url,
        title=entry.title,
        content=entry.content,
        tags=tags,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        context_url=entry.context_url,
        context_type=entry.context_type,
        context_id=entry.context_id,
    )


async def parse_entries_model(
    entries: List[JournalEntryResponse],
) -> ListJournalEntriesResponse:
    return ListJournalEntriesResponse(entries=entries)


async def parse_entry_model_entity(
    entry: JournalEntry,
    journal_id: UUID,
    journal_url: Optional[str] = None,
    tags: List[str] = [],
) -> EntityResponse:
    address: Optional[str] = None
    blockchain: Optional[str] = None
    required_fields: List[Dict[str, Any]] = []

    for tag in tags:
        if tag.startswith("address:"):
            address = tag[len("address:") :]
            continue
        elif tag.startswith("blockchain:"):
            blockchain = tag[len("blockchain:") :]
            continue
        field_and_val = tag.split(":")
        required_fields.append(
            {"".join(field_and_val[:1]): ":".join(field_and_val[1:])}
        )

    return EntityResponse(
        entity_id=entry.id,
        collection_id=journal_id,
        address=address,
        blockchain=blockchain,
        name=" - ".join(entry.title.split(" - ")[1:]),
        required_fields=required_fields,
        secondary_fields=json.loads(entry.content) if entry.content is not None else {},
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


async def parse_entries_model_entity(
    entries: List[EntityResponse],
) -> EntitiesResponse:
    return EntitiesResponse(entities=entries)


journal_representation_parsers: Dict[
    JournalRepresentationTypes, Dict[str, Callable]
] = {
    JournalRepresentationTypes.JOURNAL: {
        "journal": parse_journal_model,
        "journals": parse_journals_model,
        "entry": parse_entry_model,
        "entries": parse_entries_model,
    },
    JournalRepresentationTypes.ENTITY: {
        "journal": parse_journal_model_entity,
        "journals": parse_journals_model_entity,
        "entry": parse_entry_model_entity,
        "entries": parse_entries_model_entity,
    },
}
