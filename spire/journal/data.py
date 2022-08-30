"""
Journal-related data structures
"""
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Set, Dict, Union
import uuid

from pydantic import BaseModel, Field

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


class CreateJournalAPIRequest(BaseModel):
    # group_id is Optional to have possibility send null via update update_journal()
    name: str
    group_id: Optional[str]
    journal_type: JournalTypes = JournalTypes.DEFAULT


class CreateJournalRequest(BaseModel):
    bugout_user_id: str
    name: str
    search_index: Optional[str]


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
    holder_id: Optional[str]
    name: Optional[str]


class JournalEntryIds(BaseModel):
    entries: List[uuid.UUID] = Field(default_factory=list)


class JournalSpec(BaseModel):
    id: Optional[uuid.UUID]
    bugout_user_id: Optional[str]
    holder_ids: Optional[Set[str]]
    name: Optional[str]


class CreateJournalEntryRequest(BaseModel):
    journal_spec: JournalSpec
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    context_url: Optional[str]
    context_id: Optional[str]
    context_type: Optional[str]
    created_at: Optional[datetime]


class JournalEntryContent(BaseModel):
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    context_url: Optional[str]
    context_id: Optional[str]
    context_type: Optional[str]
    created_at: Optional[datetime]
    locked_by: Optional[str]


class JournalEntryListContent(BaseModel):
    entries: List[JournalEntryContent] = Field(default_factory=list)


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    journal_url: Optional[str]
    content_url: Optional[str]
    title: Optional[str]
    content: Optional[str]
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    context_url: Optional[str]
    context_type: Optional[str]
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
    entries_hour: Optional[bool]
    entries_day: Optional[bool]
    entries_week: Optional[bool]
    entries_month: Optional[bool]
    entries_total: Optional[bool]
    most_used_tags: Optional[bool]


class UpdateStatsRequest(BaseModel):
    stats_version: int
    stats_type: List[str] = []
    timescale: List[str] = []
    push_to_bucket: Optional[bool] = True


class ListJournalEntriesResponse(BaseModel):
    entries: List[JournalEntryResponse]


class CreateJournalEntryTagRequest(BaseModel):
    journal_entry_id: uuid.UUID
    tags: List[str]


class CreateJournalEntryTagsAPIRequest(BaseModel):
    tags: List[str]


class DeleteJournalEntryTagAPIRequest(BaseModel):
    tag: str


class DeleteJournalEntriesByTagsAPIRequest(BaseModel):
    tags: List[str] = Field(default_factory=list)


class JournalEntryTagsResponse(BaseModel):
    journal_id: uuid.UUID
    entry_id: uuid.UUID
    tags: List[str]


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
    content: Optional[str]
    tags: List[str]
    created_at: str
    updated_at: str
    score: float
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None


class JournalSearchResultsResponse(BaseModel):
    total_results: int
    offset: int
    next_offset: Optional[int]
    max_score: float
    results: List[JournalSearchResult]


class JournalPermissionsSpec(BaseModel):
    journal_id: uuid.UUID
    holder_type: HolderType
    holder_id: str
    permission: str


class ListJournalScopeSpec(BaseModel):
    scopes: List[JournalPermissionsSpec]


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
    permission_list: List[str]


class JournalPermission(BaseModel):
    holder_type: HolderType
    holder_id: str
    permissions: List[str]


class JournalPermissionsResponse(BaseModel):
    journal_id: uuid.UUID
    permissions: List[JournalPermission]


class ContextSpec(BaseModel):
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None


class JournalTTLRuleResponse(BaseModel):
    id: int
    journal_id: Optional[uuid.UUID]
    name: str
    conditions: Dict[str, Any]
    action: RuleActions
    active: bool
    created_at: datetime


class JournalTTLRulesListResponse(BaseModel):
    rules: List[JournalTTLRuleResponse] = Field(default_factory=list)


class DeletingQuery(BaseModel):
    search_query: str
