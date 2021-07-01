"""
Journal-related data structures
"""
from datetime import datetime

from pydantic import BaseModel, Field


class DefaultJournal(BaseModel):
    id: str
