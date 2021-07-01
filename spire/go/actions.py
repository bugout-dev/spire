import logging
import string
from typing import Any, Dict, List, Tuple, Optional, Union
from uuid import UUID

from sqlalchemy.orm import Session

from .data import RecordType
from .models import PermalinkJournal, PermalinkJournalEntry
from ..broodusers import bugout_api

logger = logging.getLogger(__name__)


class JournalPermalinkExists(Exception):
    """
    Permalink for journal exception already set.
    """


class JournalPermalinkNotFound(Exception):
    """
    Raised on actions that involve permalink journals which are not present in the database.
    """


class JournalEntryPermalinkNotFound(Exception):
    """
    Raised on actions that involve permalink journal entries which are not present in the database.
    """


class JournalPermalinkBadSymbols(ValueError):
    """
    Raised on action when permalink contains not allowed symbols.
    """


allowed_permalink_symbols = (
    list("-_ ")
    + list(string.ascii_lowercase)
    + list(string.ascii_uppercase)
    + list(string.digits)
)


def clean_permalink(permalink: str):
    correct_symbols = all(e in allowed_permalink_symbols for e in permalink)
    if not correct_symbols:
        raise JournalPermalinkBadSymbols("Bad symbols was used in permalink")
    permalink_clean = permalink.lower().replace(" ", "_")
    return permalink_clean


def ensure_permalink_string(permalink: str) -> bool:
    """
    Check if provided permalink is not uuid.
    """
    permalink_string = True
    try:
        UUID(permalink)
        permalink_string = False
    except ValueError:
        permalink_string = True

    return permalink_string


async def extract_permalink(
    db_session, record_type: RecordType, permalink
) -> Tuple[Union[str, UUID], Optional[bool]]:
    if record_type == RecordType.journal:
        record = await get_journal_permalink(db_session, permalink=permalink)
        if record is None:
            raise JournalPermalinkNotFound(
                "There is no journal with provided permalink",
            )
        record_id = record.journal_id
        record_public = record.public

    elif record_type == RecordType.entry:
        record = await get_entry_permalink(db_session, permalink=permalink)
        if record is None:
            raise JournalEntryPermalinkNotFound(
                "There is no entry with provided permalink",
            )
        record_id = record.entry_id
        record_public = None

    return record_id, record_public


async def get_journal_permalink(
    db_session: Session,
    journal_id: Optional[UUID] = None,
    permalink: Optional[str] = None,
) -> Optional[PermalinkJournal]:
    """
    Return journal permalink record with provided permalink or journal_id.
    """
    query = db_session.query(PermalinkJournal)

    if permalink is not None:
        query = query.filter(PermalinkJournal.permalink == permalink)
    if journal_id is not None:
        query = query.filter(PermalinkJournal.journal_id == journal_id)

    journal_permalink = query.one_or_none()

    return journal_permalink


async def get_entry_permalink(
    db_session: Session,
    permalink: Optional[str] = None,
    journal_id: Optional[UUID] = None,
) -> Optional[PermalinkJournalEntry]:
    """
    Return journal entry with provided entry permalink.
    """
    query = db_session.query(PermalinkJournalEntry)
    if permalink is not None:
        query = query.filter(PermalinkJournalEntry.permalink == permalink)
    if journal_id is not None:
        query = query.filter(PermalinkJournalEntry.journal_id == journal_id)

    entry_permalink = query.one_or_none()

    return entry_permalink


async def set_journal_permalink(
    db_session: Session, journal_id: UUID, permalink: str
) -> PermalinkJournal:
    """
    Set journal permalink if it is doesn't exists.
    """
    journal_permalink = await get_journal_permalink(db_session, journal_id=journal_id)
    if journal_permalink is not None:
        raise JournalPermalinkExists("Journal permalink already exists")

    journal_public = bugout_api.check_journal_public(journal_id=journal_id)

    permalink_clean = clean_permalink(permalink)
    journal_permalink = PermalinkJournal(
        journal_id=journal_id, permalink=permalink_clean, public=journal_public
    )
    db_session.add(journal_permalink)
    db_session.commit()

    return journal_permalink


async def revoke_journal_permalink(
    db_session: Session, journal_id: UUID
) -> PermalinkJournal:
    journal_permalink = (
        db_session.query(PermalinkJournal)
        .filter(PermalinkJournal.journal_id == journal_id)
        .one_or_none()
    )
    if journal_permalink is None:
        raise JournalPermalinkNotFound("There is no permalink for provided journal id")

    db_session.delete(journal_permalink)
    db_session.commit()

    return journal_permalink
