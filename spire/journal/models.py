"""
SQLAlchemy models for journal-related tables.
"""
import uuid
from enum import Enum, unique

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as PgEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    MetaData,
    PrimaryKeyConstraint,
    VARCHAR,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB, UUID

from brood.models import utcnow

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


@unique
class HolderType(Enum):
    user = "user"
    group = "group"


class Journal(Base):  # type: ignore
    __tablename__ = "journals"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    bugout_user_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    version_id = Column(Integer, nullable=False)
    search_index = Column(String, nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "bugout_user_id", "name", name="uc_journals_bugout_user_id_name"
        ),
    )
    permissions = relationship(
        "JournalPermissions", cascade="all, delete, delete-orphan"
    )

    __mapper_args__ = {"version_id_col": version_id}


class JournalEntry(Base):  # type: ignore
    __tablename__ = "journal_entries"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "journals.id", name="fk_journal_entries_journals_id", ondelete="CASCADE"
        ),
    )
    title = Column(String, nullable=True)
    content = Column(String, nullable=False)

    context_id = Column(String, nullable=True)
    context_url = Column(String, nullable=True)
    context_type = Column(String, server_default="bugout", nullable=False)

    version_id = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
        index=True,
    )

    tags = relationship(
        "JournalEntryTag", cascade="all, delete, delete-orphan", lazy=True
    )

    __mapper_args__ = {"version_id_col": version_id}


class JournalEntryLock(Base):  # type: ignore
    __tablename__ = "journal_entry_locks"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "journal_entries.id",
            ondelete="CASCADE",
        ),
        unique=True,
    )
    locked_by = Column(
        String,
        nullable=False,
        index=True,
    )
    locked_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
        index=True,
    )


class JournalEntryTag(Base):  # type: ignore
    __tablename__ = "journal_entry_tags"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    journal_entry_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "journal_entries.id",
            name="fk_journal_entry_tags_journal_entries_id",
            ondelete="CASCADE",
        ),
    )
    tag = Column(String, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "journal_entry_id", "tag", name="uc_journal_entry_tags_journal_entry_id_tag"
        ),
    )


class JournalPermissions(Base):  # type: ignore
    """
    Journal-permission model.

    holder_type: user/group
    holder_id: user_id/group_id
    permission: read/update/delete
    """

    __tablename__ = "journal_permissions"
    __table_args__ = (
        PrimaryKeyConstraint("holder_type", "journal_id", "holder_id", "permission"),
    )

    holder_type = Column(PgEnum(HolderType, name="holder_type"), nullable=False)
    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "journals.id", name="fk_journal_permissions_journals_id", ondelete="CASCADE"
        ),
        nullable=False,
    )
    holder_id = Column(String, nullable=False)
    permission = Column(
        String,
        ForeignKey(
            "spire_oauth_scopes.scope",
            name="fk_journal_permissions_spire_oauth_scopes_scope",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
    )


class SpireOAuthScopes(Base):  # type: ignore
    """
    api - /slack, /journals, etc.
    scope - journals.update, etc.
    description - “journals.update grants holders permission to create and
    delete entries in a journal as well as to update information about the journal itself
    """

    __tablename__ = "spire_oauth_scopes"
    __table_args__ = (PrimaryKeyConstraint("api", "scope"),)

    api = Column(String, nullable=False)
    scope = Column(String, nullable=False, unique=True)
    description = Column(String, nullable=False)


class JournalTTL(Base):  # type: ignore
    """
    Rules applied to journal entries and executed by drone.

    name - Short name of rule
    conditions:
        - tags - List of tags to entries apply
        - created_at - Action based on created_at entry timestamp
        - updated_at - Action based on updated_at entry timestamp
    action - delete, touch, add tag, etc.
    """

    __tablename__ = "journal_ttls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    journal_id = Column(
        UUID(as_uuid=True),
        ForeignKey("journals.id", ondelete="CASCADE"),
        nullable=True,
    )
    name = Column(VARCHAR(256), nullable=False)
    conditions = Column(JSONB, nullable=False)
    action = Column(VARCHAR(1024), nullable=False)
    active = Column(Boolean, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
