from datetime import datetime

from spire.humbug.models import Base
from typing import List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, Field


class HumbugEventDependencies(BaseModel):
    group_id: UUID
    journal_id: UUID
    journal_name: str
    user_id: UUID
    access_token_id: UUID


class HumbugIntegrationResponse(BaseModel):
    id: UUID
    group_id: UUID
    journal_id: UUID
    journal_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class HumbugIntegrationListResponse(BaseModel):
    integrations: List[HumbugIntegrationResponse] = Field(default_factory=list)


class HumbugTokenResponse(BaseModel):
    restricted_token_id: UUID
    app_name: str
    app_version: str
    store_ip: bool


class HumbugTokenListResponse(BaseModel):
    user_id: UUID
    humbug_id: UUID
    tokens: List[HumbugTokenResponse] = Field(default_factory=list)


class HumbugReport(BaseModel):
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[datetime]


class HumbugCreateReportTask(BaseModel):
    report: HumbugReport
    bugout_token: UUID
