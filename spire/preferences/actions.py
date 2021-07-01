import logging
from typing import Optional

from .errors import PreferenceLocked
from .models import DefaultJournal

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import NoResultFound

logger = logging.getLogger(__name__)


def default_journal_get(session: Session, user_id: str) -> Optional[DefaultJournal]:
    return (
        session.query(DefaultJournal)
        .filter(DefaultJournal.user_id == user_id)
        .one_or_none()
    )


def default_journal_upsert(session: Session, user_id: str, journal_id: str) -> None:
    try:
        current_default_journal = (
            session.query(DefaultJournal)
            .filter(DefaultJournal.user_id == user_id)
            .with_for_update(nowait=True, skip_locked=False)
            .one_or_none()
        )
    except OperationalError as e:
        session.rollback()
        raise PreferenceLocked(repr(e))

    if current_default_journal is None:
        default_journal = DefaultJournal(user_id=user_id, journal_id=journal_id)
        session.add(default_journal)
    else:
        current_default_journal.journal_id = journal_id
    session.commit()


def default_journal_delete(session: Session, user_id: str) -> None:
    try:
        default_journal = (
            session.query(DefaultJournal)
            .filter(DefaultJournal.user_id == user_id)
            .with_for_update(nowait=True, skip_locked=False)
            .one()
        )
        session.delete(default_journal)
        session.commit()
    except NoResultFound:
        pass
    except OperationalError as e:
        session.rollback()
        raise PreferenceLocked(repr(e))
