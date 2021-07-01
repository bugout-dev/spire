"""
SQLAlchemy models for public routes tables.
"""
import uuid

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    MetaData,
)
from sqlalchemy.dialects.postgresql import UUID

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


class PublicJournal(Base):  # type: ignore
    __tablename__ = "public_journals"

    journal_id = Column(
        UUID(as_uuid=True), primary_key=True, unique=True, nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("public_users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class PublicUser(Base):  # type: ignore
    """
    Public user which control public journal.
    """

    __tablename__ = "public_users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, unique=True, nullable=False)
    access_token_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    restricted_token_id = Column(
        UUID(as_uuid=True), primary_key=True, unique=True, nullable=False
    )
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )
