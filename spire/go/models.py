"""
SQLAlchemy models for permalink routes tables.
"""
import uuid

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, ForeignKey, String, MetaData, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from brood.models import utcnow
from sqlalchemy.sql.sqltypes import Boolean

"""
Naming conventions doc
https://docs.sqlalchemy.org/en/13/core/constraints.html#configuring-constraint-naming-conventions
"""
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)


class PermalinkJournal(Base):  # type: ignore
    __tablename__ = "permalink_journals"

    journal_id = Column(
        UUID(as_uuid=True), primary_key=True, unique=True, nullable=False
    )
    permalink = Column(String, unique=True, nullable=False)
    public = Column(Boolean, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class PermalinkJournalEntry(Base):  # type: ignore
    __tablename__ = "permalink_journal_entries"
    __table_args__ = (UniqueConstraint("journal_id", "permalink"),)

    entry_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False)
    journal_id = Column(UUID(as_uuid=True), nullable=False)
    permalink = Column(String, unique=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )
