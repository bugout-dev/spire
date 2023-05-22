"""
Slack-related data structures
"""
from typing import Optional
import uuid

from pydantic import BaseModel


class Index(BaseModel):
    """
    Data structure representing an index.
    """

    index_name: str
    index_url: str
    description: Optional[str]
    use_bugout_auth: bool
    use_bugout_client_id: bool


class BroodUser(BaseModel):
    id: uuid.UUID
    username: Optional[str] = None
    email: Optional[str] = None
    token: Optional[uuid.UUID] = None


class BroodGroup(BaseModel):
    id: uuid.UUID
    group_name: Optional[str]
