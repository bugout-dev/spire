import logging
from typing import Any, Dict, List, Set, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from .models import PublicJournal, PublicUser

logger = logging.getLogger(__name__)


class PublicJournalNotFound(Exception):
    """
    Raised on actions that involve public journals which are not present in the database.
    """


class PublicUserNotFound(Exception):
    """
    Raised on actions that involve public user which are not present in the database.
    """


async def get_public_journal(db_session: Session, journal_id: UUID) -> PublicJournal:
    """
    Return public journal with provided id.
    """
    journal = (
        db_session.query(PublicJournal)
        .filter(PublicJournal.journal_id == journal_id)
        .one_or_none()
    )
    if journal is None:
        raise PublicJournalNotFound(f"Did not find journals with id: {journal_id}")

    return journal


async def get_public_user(db_session: Session, user_id: UUID) -> PublicUser:
    """
    Search for public user in database.
    """
    public_user = (
        db_session.query(PublicUser).filter(PublicUser.user_id == user_id).one_or_none()
    )
    if public_user is None:
        raise PublicUserNotFound("Public user not found")

    return public_user
