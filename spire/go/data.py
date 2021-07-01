from datetime import datetime
from enum import Enum
from spire.humbug.models import Base
from typing import List, Optional, Set
from uuid import UUID

from pydantic import BaseModel, Field


class RecordType(Enum):
    journal = "journal"
    entry = "entry"


class PermalinkJournalResponse(BaseModel):
    journal_id: UUID
    permalink: str
    public: bool
