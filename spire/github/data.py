from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class LocustSummaryReport(BaseModel):
    locust: List[Dict[str, Any]]
    refs: Dict[str, Any]
    comments_url: str
    terminal_hash: str


class EntrySummaryCommentsReport(BaseModel):
    id: int
    message: str
    author: str
    direct_url: str
    timestamp: datetime


class EntrySummaryCommitReport(BaseModel):
    sha: str
    message: str
    author: str
    direct_url: str
    timestamp: datetime


class EntrySummaryReport(BaseModel):
    """
    Summary for Bugout journal entry.
    """

    title: Optional[str] = None
    body: Optional[str] = None
    checks: Optional[str] = None
    comments: List[EntrySummaryCommentsReport] = Field(default_factory=list)
    commits: List[EntrySummaryCommitReport] = Field(default_factory=list)


class SummaryResponse(BaseModel):
    id: uuid.UUID
    issue_pr_id: uuid.UUID
    comments_url: str
    terminal_hash: str
    response_url: Optional[str]
    commented_at: Optional[datetime]
    created_at: datetime


class SummaryContentResponse(BaseModel):
    id: uuid.UUID
    issue_pr_id: uuid.UUID
    summary: Dict[str, Any]
    created_at: datetime
    commented_at: Optional[datetime]
