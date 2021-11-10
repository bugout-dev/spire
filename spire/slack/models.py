"""
Database models for Spire slack integration
"""

import uuid

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    MetaData,
    PrimaryKeyConstraint,
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


class SlackOAuthEvent(Base):  # type: ignore
    __tablename__ = "slack_oauth_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    bot_access_token = Column(String, nullable=False)
    bot_scope = Column(String, nullable=False)
    bot_user_id = Column(String, nullable=False)
    team_id = Column(String, nullable=False)
    team_name = Column(String, nullable=True)
    enterprise_id = Column(String, nullable=True)
    enterprise_name = Column(String, nullable=True)
    user_access_token = Column(String, nullable=True)
    authed_user_id = Column(String, nullable=True)
    authed_user_scope = Column(String, nullable=True)
    version = Column(Integer, nullable=False, default=0)
    deleted = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class SlackMention(Base):  # type: ignore
    __tablename__ = "slack_mentions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    slack_oauth_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "slack_oauth_events.id",
            name="fk_slack_mentions_slack_oauth_events_id",
            ondelete="CASCADE",
        ),
    )
    team_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=False)
    invocation = Column(String, nullable=False)
    thread_ts = Column(String, nullable=True)
    responded = Column(Boolean)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class SlackBugoutUser(Base):  # type: ignore
    __tablename__ = "slack_bugout_users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    slack_oauth_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "slack_oauth_events.id",
            name="fk_slack_bugout_users_slack_oauth_events_id",
            ondelete="CASCADE",
        ),
    )
    bugout_user_id = Column(String, nullable=False)
    bugout_group_id = Column(String, nullable=True)
    bugout_access_token = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class SlackIndexConfiguration(Base):  # type: ignore
    __tablename__ = "slack_index_configurations"

    slack_oauth_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "slack_oauth_events.id",
            name="fk_slack_bugout_users_slack_oauth_events_id",
            ondelete="CASCADE",
        ),
    )
    index_name = Column(String, nullable=False)
    index_url = Column(String, nullable=False)
    description = Column(String, nullable=True)
    use_bugout_auth = Column(Boolean, nullable=False)
    use_bugout_client_id = Column(Boolean, nullable=False)
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
        PrimaryKeyConstraint(
            "slack_oauth_event_id",
            "index_name",
            name="pk_slack_index_configurations",
        ),
    )
