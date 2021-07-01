"""
SQLAlchemy models for journal-related tables.
"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Column,
    DateTime,
    String,
    MetaData,
)

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


class DefaultJournal(Base):  # type: ignore
    __tablename__ = "preferences_default_journals"

    user_id = Column(String, primary_key=True)
    journal_id = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )
