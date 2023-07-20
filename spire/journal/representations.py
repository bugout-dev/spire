"""
Manual journal parser depends on representations.

Avoided pydantic modifications to save unique cases support, FastAPI response_model compatibility.
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, cast
from uuid import UUID

from web3 import Web3

from .data import (
    CollectionPermissionsResponse,
    CollectionScopeSpec,
    CollectionSearchResponse,
    CollectionSearchResult,
    EntitiesResponse,
    Entity,
    EntityCollectionResponse,
    EntityCollectionsResponse,
    EntityResponse,
    JournalEntryResponse,
    JournalPermission,
    JournalPermissionsResponse,
    JournalRepresentationTypes,
    JournalResponse,
    JournalScopeSpec,
    JournalSearchResult,
    JournalSearchResultsResponse,
    ListCollectionScopeSpec,
    ListJournalEntriesResponse,
    ListJournalScopeSpec,
    ListJournalsResponse,
)
from .models import HolderType, Journal

logger = logging.getLogger(__name__)


# enforce_same_args is a decorator to make sure parser functions have similar arguments
# TODO(kompotkot): Write factory function to generate signatures for paris of functions
def enforce_same_args(func: Callable):
    required_args = func.__code__.co_varnames[: func.__code__.co_argcount]

    def wrapper(*args, **kwargs):
        arg_names = list(required_args)
        for arg in args:
            try:
                arg_names.remove(arg)
            except ValueError:
                raise ValueError(f"Unexpected argument: {arg}")
        for kwarg in kwargs.keys():
            try:
                arg_names.remove(kwarg)
            except ValueError:
                raise ValueError(f"Unexpected argument: {kwarg}")
        if arg_names:
            raise ValueError(f"Missing arguments: {arg_names}")

        return func(*args, **kwargs)

    return wrapper


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
    title = f"{create_entity.title}"
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
async def parse_journal_model(
    journal: Journal, holder_ids: Set[str]
) -> JournalResponse:
    return JournalResponse(
        id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids=holder_ids,
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


async def parse_journals_model(journals: List[JournalResponse]) -> ListJournalsResponse:
    return ListJournalsResponse(journals=journals)


async def parse_journal_model_collection(
    journal: Journal, holder_ids: Set[str]
) -> EntityCollectionResponse:
    return EntityCollectionResponse(
        collection_id=journal.id,
        bugout_user_id=journal.bugout_user_id,
        holder_ids=holder_ids,
        name=journal.name,
        created_at=journal.created_at,
        updated_at=journal.updated_at,
    )


async def parse_journals_model_collection(
    journals: List[EntityCollectionResponse],
) -> EntityCollectionsResponse:
    return EntityCollectionsResponse(collections=journals)


# Entry parsers
@enforce_same_args
async def parse_entry_model(
    id: UUID,
    journal_id: UUID,
    title: Optional[str] = None,
    content: Optional[str] = None,
    url: Optional[str] = None,
    tags: List[str] = [],
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    context_url: Optional[str] = None,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    locked_by: Optional[str] = None,
) -> JournalEntryResponse:
    return JournalEntryResponse(
        id=id,
        journal_url="/".join(url.split("/")[:-2]) if url is not None else None,
        content_url=f"{url}/content" if url is not None else None,
        title=title,
        content=content,
        tags=tags,
        created_at=created_at,
        updated_at=updated_at,
        context_url=context_url,
        context_type=context_type,
        context_id=context_id,
        locked_by=locked_by,
    )


async def parse_entries_model(
    entries: List[JournalEntryResponse],
) -> ListJournalEntriesResponse:
    return ListJournalEntriesResponse(entries=entries)


@enforce_same_args
async def parse_entry_model_collection(
    id: UUID,
    journal_id: UUID,
    title: Optional[str] = None,
    content: Optional[str] = None,
    url: Optional[str] = None,
    tags: List[str] = [],
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    context_url: Optional[str] = None,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    locked_by: Optional[str] = None,
) -> EntityResponse:
    address, blockchain, required_fields = parse_entry_tags_to_entity_fields(tags=tags)

    secondary_fieds = {}
    try:
        secondary_fieds = json.loads(content) if content is not None else {}
    except Exception as err:
        secondary_fieds = {"JSONDecodeError": "unable to parse as JSON"}

    return EntityResponse(
        id=id,
        collection_id=journal_id,
        collection_url="/".join(url.split("/")[:-2]) if url is not None else None,
        content_url=f"{url}/content" if url is not None else None,
        address=address,
        blockchain=blockchain,
        title=" - ".join(title.split(" - ")[1:]),
        required_fields=required_fields,
        secondary_fields=secondary_fieds,
        created_at=created_at,
        updated_at=updated_at,
        locked_by=locked_by,
    )


async def parse_entries_model_collection(
    entries: List[EntityResponse],
) -> EntitiesResponse:
    return EntitiesResponse(entities=entries)


# Permission parsers
async def parse_permissions_model(
    journal_id: UUID, permissions: List[JournalPermission]
) -> JournalPermissionsResponse:
    return JournalPermissionsResponse(journal_id=journal_id, permissions=permissions)


async def parse_permissions_model_collection(
    journal_id: UUID, permissions: List[JournalPermission]
) -> CollectionPermissionsResponse:
    return CollectionPermissionsResponse(
        collection_id=journal_id, permissions=permissions
    )


async def parse_scope_spec_model(
    journal_id: UUID, holder_type: HolderType, holder_id: str, permission: str
) -> JournalScopeSpec:
    return JournalScopeSpec(
        journal_id=journal_id,
        holder_type=holder_type,
        holder_id=holder_id,
        permission=permission,
    )


async def parse_scope_specs_model(scopes: JournalScopeSpec) -> JournalScopeSpec:
    return ListJournalScopeSpec(scopes=scopes)


async def parse_scope_spec_model_collection(
    journal_id: UUID, holder_type: HolderType, holder_id: str, permission: str
) -> JournalScopeSpec:
    return CollectionScopeSpec(
        collection_id=journal_id,
        holder_type=holder_type,
        holder_id=holder_id,
        permission=permission,
    )


async def parse_scope_specs_model_collection(
    scopes: CollectionScopeSpec,
) -> ListCollectionScopeSpec:
    return ListCollectionScopeSpec(scopes=scopes)


# Search entry parsers
async def parse_search_entry_model(
    entry_id: str,
    journal_id: str,
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


async def parse_search_entry_model_collection(
    entry_id: str,
    journal_id: str,
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
) -> CollectionSearchResult:
    address, blockchain, required_fields = parse_entry_tags_to_entity_fields(tags=tags)

    return CollectionSearchResult(
        id=entry_id,
        collection_id=journal_id,
        entity_url=entry_url,
        content_url=content_url,
        title=" - ".join(title.split(" - ")[1:]),
        address=address,
        blockchain=blockchain,
        required_fields=required_fields,
        secondary_fields=json.loads(content) if content is not None else {},
        created_at=created_at,
        updated_at=updated_at,
        score=score,
    )


async def parse_search_entries_model_collection(
    total_results: int,
    offset: int,
    max_score: float,
    next_offset: Optional[int] = None,
    results: List[EntityResponse] = [],
) -> CollectionSearchResponse:
    return CollectionSearchResponse(
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
        "permissions": parse_permissions_model,
        "scope_spec": parse_scope_spec_model,
        "scope_specs": parse_scope_specs_model,
        "search_entry": parse_search_entry_model,
        "search_entries": parse_search_entries_model,
    },
    JournalRepresentationTypes.COLLECTION: {
        "journal": parse_journal_model_collection,
        "journals": parse_journals_model_collection,
        "entry": parse_entry_model_collection,
        "entries": parse_entries_model_collection,
        "permissions": parse_permissions_model_collection,
        "scope_spec": parse_scope_spec_model_collection,
        "scope_specs": parse_scope_specs_model_collection,
        "search_entry": parse_search_entry_model_collection,
        "search_entries": parse_search_entries_model_collection,
    },
}
