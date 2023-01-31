import logging
from uuid import UUID

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


def create_public_journal(
    db_session: Session, journal_id: UUID, user_id: UUID
) -> PublicJournal:
    public_journal = PublicJournal(
        journal_id=journal_id,
        user_id=user_id,
    )
    db_session.add(public_journal)
    db_session.commit()

    return public_journal


def get_public_journal(db_session: Session, journal_id: UUID) -> PublicJournal:
    """
    Return public journal with provided id.
    """
    public_journal = (
        db_session.query(PublicJournal)
        .filter(PublicJournal.journal_id == journal_id)
        .one_or_none()
    )
    if public_journal is None:
        raise PublicJournalNotFound(f"Public journal with id: {journal_id} not found")

    return public_journal


def delete_public_journal(
    db_session: Session, public_journal: PublicJournal
) -> PublicJournal:
    db_session.delete(public_journal)
    db_session.commit()

    return public_journal


def get_public_user(db_session: Session, user_id: UUID) -> PublicUser:
    """
    Search for public user in database.
    """
    public_user = (
        db_session.query(PublicUser).filter(PublicUser.user_id == user_id).one_or_none()
    )
    if public_user is None:
        raise PublicUserNotFound("Public user not found")

    return public_user
