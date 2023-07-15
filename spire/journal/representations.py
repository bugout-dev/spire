"""
Manual journal parser depends on representations.

Avoided pydantic modifications to save unique cases support, FastAPI response_model compatibility.
"""

import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, cast
from uuid import UUID

from web3 import Web3

from .data import (
    EntitiesResponse,
    Entity,
    EntityCollectionResponse,
    EntityCollectionsResponse,
    EntityResponse,
    EntitySearchResponse,
    JournalEntryResponse,
    JournalRepresentationTypes,
    JournalResponse,
    JournalSearchResult,
    JournalSearchResultsResponse,
    ListJournalEntriesResponse,
    ListJournalsResponse,
)
from .models import Journal, JournalEntry

logger = logging.getLogger(__name__)


def parse_entry_tags_to_entity_fields(
    tags: List[str],
) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """
    Convert Bugout entry to entity response.
    """
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

    return address, blockchain, required_fields


def parse_entity_to_entry(
    create_entity: Entity,
) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    Parse Entity create request structure to Bugout journal scheme.
    """
    title = f"{create_entity.name}"
    tags: List[str] = []
    content: Dict[str, Any] = {}

    for field, vals in create_entity._iter():
        if field == "address":
            try:
                address = Web3.toChecksumAddress(cast(str, vals))
            except Exception:
                logger.info(f"Unknown type of web3 address {vals}")
                address = vals
            title = f"{address} - {title}"
            tags.append(f"{field}:{address}")

        elif field == "blockchain":
            tags.append(f"{field}:{vals}")

        elif field == "required_fields":
            required_fields = []
            for val in vals:
                for f, v in val.items():
                    if isinstance(v, list):
                        for vl in v:
                            if len(f) >= 128 and len(vl) >= 128:
                                logger.warn(f"Too long key:value {f}:{vl}")
                                continue
                            required_fields.append(f"{str(f)}:{str(vl)}")
                    else:
                        if len(f) >= 128 and len(vl) >= 128:
                            logger.warn(f"Too long key:value {f}:{vl}")
                            continue
                        required_fields.append(f"{f}:{v}")

            tags.extend(required_fields)

        elif field == "extra":
            for k, v in vals.items():
                content[k] = v

    return title, tags, content


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
    locked_by: Optional[str] = None,
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
        locked_by=locked_by,
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
    locked_by: Optional[str] = None,
) -> EntityResponse:
    address, blockchain, required_fields = parse_entry_tags_to_entity_fields(tags=tags)

    secondary_fieds = {}
    try:
        secondary_fieds = json.loads(entry.content) if entry.content is not None else {}
    except Exception as err:
        secondary_fieds = {"JSONDecodeError": "unable to parse as JSON"}

    return EntityResponse(
        entity_id=entry.id,
        collection_id=journal_id,
        address=address,
        blockchain=blockchain,
        name=" - ".join(entry.title.split(" - ")[1:]),
        required_fields=required_fields,
        secondary_fields=secondary_fieds,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        locked_by=locked_by,
    )


async def parse_entries_model_entity(
    entries: List[EntityResponse],
) -> EntitiesResponse:
    return EntitiesResponse(entities=entries)


# Search entry parsers
async def parse_search_entry_model(
    entry_id: str,
    collection_id: str,
    entry_url: str,
    content_url: str,
    title: str,
    tags: List[str],
    created_at: str,
    updated_at: str,
    score: float,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_url: Optional[str] = None,
    content: Optional[str] = None,
) -> JournalSearchResult:
    return JournalSearchResult(
        entry_url=entry_url,
        content_url=content_url,
        title=title,
        content=content,
        tags=tags,
        created_at=created_at,
        updated_at=updated_at,
        score=score,
        context_type=context_type,
        context_id=context_id,
        context_url=context_url,
    )


async def parse_search_entries_model(
    total_results: int,
    offset: int,
    max_score: float,
    next_offset: Optional[int] = None,
    results: List[JournalSearchResult] = [],
) -> JournalSearchResultsResponse:
    return JournalSearchResultsResponse(
        total_results=total_results,
        offset=offset,
        next_offset=next_offset,
        max_score=max_score,
        results=results,
    )


async def parse_search_entry_model_entity(
    entry_id: str,
    collection_id: str,
    entry_url: str,
    content_url: str,
    title: str,
    tags: List[str],
    created_at: str,
    updated_at: str,
    score: float,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_url: Optional[str] = None,
    content: Optional[str] = None,
) -> EntityResponse:
    address, blockchain, required_fields = parse_entry_tags_to_entity_fields(tags=tags)

    return EntityResponse(
        entity_id=entry_id,
        collection_id=collection_id,
        address=address,
        blockchain=blockchain,
        name=" - ".join(title.split(" - ")[1:]),
        required_fields=required_fields,
        secondary_fields=json.loads(content) if content is not None else {},
        created_at=created_at,
        updated_at=updated_at,
    )


async def parse_search_entries_model_entity(
    total_results: int,
    offset: int,
    max_score: float,
    next_offset: Optional[int] = None,
    results: List[EntityResponse] = [],
) -> EntitySearchResponse:
    return EntitySearchResponse(
        total_results=total_results,
        offset=offset,
        next_offset=next_offset,
        max_score=max_score,
        results=results,
    )


journal_representation_parsers: Dict[
    JournalRepresentationTypes, Dict[str, Callable]
] = {
    JournalRepresentationTypes.JOURNAL: {
        "journal": parse_journal_model,
        "journals": parse_journals_model,
        "entry": parse_entry_model,
        "entries": parse_entries_model,
        "search_entry": parse_search_entry_model,
        "search_entries": parse_search_entries_model,
    },
    JournalRepresentationTypes.ENTITY: {
        "journal": parse_journal_model_entity,
        "journals": parse_journals_model_entity,
        "entry": parse_entry_model_entity,
        "entries": parse_entries_model_entity,
        "search_entry": parse_search_entry_model_entity,
        "search_entries": parse_search_entries_model_entity,
    },
}
