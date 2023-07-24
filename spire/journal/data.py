"""
Journal-related data structures
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from pydantic import BaseModel, Extra, Field, root_validator

from .models import HolderType


class JournalScopes(Enum):
    READ = "journals.read"
    UPDATE = "journals.update"
    DELETE = "journals.delete"


class JournalEntryScopes(Enum):
    CREATE = "journals.entries.create"
    READ = "journals.entries.read"
    UPDATE = "journals.entries.update"
    DELETE = "journals.entries.delete"


class JournalTypes(Enum):
    DEFAULT = "default"
    HUMBUG = "humbug"


class EntryUpdateTagActions(Enum):
    ignore = "ignore"
    replace = "replace"
    merge = "merge"


class TimeScale(Enum):
    year = "year"
    month = "month"
    week = "week"
    day = "day"


class StatsTypes(Enum):
    errors = "errors"
    stats = "stats"
    session = "session"
    client = "client"


class RuleActions(Enum):
    remove = "remove"
    unlock = "unlock"


class EntryRepresentationTypes(Enum):
    ENTRY = "entry"
    ENTITY = "entity"


class CreateJournalAPIRequest(BaseModel):
    # group_id is Optional to have possibility send null via update update_journal()
    name: str
    group_id: Optional[str] = None
    journal_type: JournalTypes = JournalTypes.DEFAULT


class CreateJournalRequest(BaseModel):
    bugout_user_id: str
    name: str
    search_index: Optional[str] = None


class JournalResponse(BaseModel):
    id: uuid.UUID
    bugout_user_id: str
    holder_ids: Set[str] = Field(default_factory=set)
    name: str
    created_at: datetime
    updated_at: datetime


class ListJournalsResponse(BaseModel):
    journals: List[JournalResponse]


class UpdateJournalSpec(BaseModel):
    holder_id: Optional[str] = None
    name: Optional[str] = None


class JournalEntryIds(BaseModel):
    entries: List[uuid.UUID] = Field(default_factory=list)


class JournalSpec(BaseModel):
    id: Optional[uuid.UUID] = None
    bugout_user_id: Optional[str] = None
    holder_ids: Optional[Set[str]] = None
    name: Optional[str] = None


class CreateJournalEntryRequest(BaseModel):
    journal_spec: JournalSpec
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    context_url: Optional[str] = None
    context_id: Optional[str] = None
    context_type: Optional[str] = None
    created_at: Optional[datetime] = None


class JournalEntryContent(BaseModel):
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    context_url: Optional[str] = None
    context_id: Optional[str] = None
    context_type: Optional[str] = None
    created_at: Optional[datetime] = None
    locked_by: Optional[str] = None


class JournalEntryListContent(BaseModel):
    entries: List[JournalEntryContent] = Field(default_factory=list)


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    journal_url: Optional[str] = None
    content_url: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    context_url: Optional[str] = None
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    locked_by: Optional[str] = None


class JournalStatisticsResponse(BaseModel):
    num_of_entries: Dict[str, Optional[int]]
    journal_statistics: Optional[Union[str, Dict[str, Any]]] = None
    journal_errors_statistics: Optional[
        str
    ] = None  # if set just Optional[str] return exception
    journal_users_statistics: Optional[str] = None


class DronesStatisticsResponce(BaseModel):
    modified_since: datetime
    journal_statistics: List[Dict[str, str]]


class JournalStatisticsSpecs(BaseModel):
    entries_hour: Optional[bool] = None
    entries_day: Optional[bool] = None
    entries_week: Optional[bool] = None
    entries_month: Optional[bool] = None
    entries_total: Optional[bool] = None
    most_used_tags: Optional[bool] = None


class UpdateStatsRequest(BaseModel):
    stats_version: int
    stats_type: List[str] = Field(default_factory=list)
    timescale: List[str] = Field(default_factory=list)
    push_to_bucket: Optional[bool] = True


class ListJournalEntriesResponse(BaseModel):
    entries: List[JournalEntryResponse]


class CreateJournalEntryTagRequest(BaseModel):
    journal_entry_id: uuid.UUID
    tags: List[str] = Field(default_factory=list)


class CreateEntriesTagsRequest(BaseModel):
    entries: List[CreateJournalEntryTagRequest] = Field(default_factory=list)


class CreateJournalEntryTagsAPIRequest(BaseModel):
    tags: List[str] = Field(default_factory=list)


class DeleteJournalEntryTagAPIRequest(BaseModel):
    tag: str


class DeleteJournalEntriesByTagsAPIRequest(BaseModel):
    tags: List[str] = Field(default_factory=list)


class JournalEntryTagsResponse(BaseModel):
    journal_id: uuid.UUID
    entry_id: uuid.UUID
    tags: List[str] = Field(default_factory=list)


class JournalsEntriesTagsResponse(BaseModel):
    entries: List[JournalEntryTagsResponse] = Field(default_factory=list)


class JournalEntriesByTagsDeletionResponse(BaseModel):
    journal_id: uuid.UUID
    num_deleted: int
    tags: List[str] = Field(default_factory=list)


class JournalEntriesBySearchDeletionResponse(BaseModel):
    journal_id: uuid.UUID
    num_deleted: int
    search_query: str


class JournalSearchResult(BaseModel):
    entry_url: str
    content_url: str
    title: str
    content: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    score: float
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None


class JournalScopeSpec(BaseModel):
    journal_id: uuid.UUID
    holder_type: HolderType
    holder_id: str
    permission: str


class ListJournalScopeSpec(BaseModel):
    scopes: List[JournalScopeSpec]


class ScopeResponse(BaseModel):
    api: str
    scope: str
    description: str


class ListScopesResponse(BaseModel):
    scopes: List[ScopeResponse]


class JournalScopesAPIRequest(BaseModel):
    api: str


class UpdateJournalScopesAPIRequest(BaseModel):
    holder_type: str
    holder_id: str
    permissions: List[str]


class JournalPermission(BaseModel):
    holder_type: HolderType
    holder_id: str
    permissions: List[str] = Field(default_factory=list)


class JournalPermissionsResponse(BaseModel):
    journal_id: uuid.UUID
    permissions: List[JournalPermission]


class ContextSpec(BaseModel):
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None


class JournalTTLRuleResponse(BaseModel):
    id: int
    journal_id: Optional[uuid.UUID] = None
    name: str
    conditions: Dict[str, Any]
    action: RuleActions
    active: bool
    created_at: datetime


class JournalTTLRulesListResponse(BaseModel):
    rules: List[JournalTTLRuleResponse] = Field(default_factory=list)


class DeletingQuery(BaseModel):
    search_query: str


class TagUsage(BaseModel):
    tag: str
    count: int


# Entity representation
class Entity(BaseModel, extra=Extra.allow):
    address: str
    blockchain: str
    title: str

    context_url: Optional[str] = None
    context_id: Optional[str] = None
    context_type: Optional[str] = None
    created_at: Optional[datetime] = None

    required_fields: List[Dict[str, Union[str, bool, int, list]]] = Field(
        default_factory=list
    )

    extra: Dict[str, Any]

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        all_required_field_names = {
            field.alias for field in cls.__fields__.values() if field.alias != "extra"
        }

        extra: Dict[str, Any] = {}
        for field_name in list(values):
            if field_name not in all_required_field_names:
                extra[field_name] = values.pop(field_name)
        values["extra"] = extra
        return values


class EntityList(BaseModel):
    entities: List[Entity] = Field(default_factory=list)


class EntityResponse(BaseModel):
    id: uuid.UUID
    journal_id: uuid.UUID
    journal_url: Optional[str] = None
    content_url: Optional[str] = None
    address: Optional[str] = None
    blockchain: Optional[str] = None
    title: Optional[str] = None

    required_fields: Optional[List[Dict[str, Any]]] = None
    secondary_fields: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    locked_by: Optional[str] = None


class EntitiesResponse(BaseModel):
    entities: List[EntityResponse] = Field(default_factory=list)


class JournalSearchResultAsEntity(BaseModel):
    id: str
    journal_id: str
    entity_url: str
    title: str
    address: str
    blockchain: str
    required_fields: List[Dict[str, Any]] = Field(default_factory=list)
    secondary_fields: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    score: float


class JournalSearchResultsResponse(BaseModel):
    total_results: int
    offset: int
    next_offset: Optional[int]
    max_score: float
    results: List[Union[JournalSearchResult, JournalSearchResultAsEntity]] = Field(
        default_factory=list
    )
