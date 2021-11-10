"""
Database models for Github App.
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


class GitHubOAuthEvent(Base):  # type: ignore
    """
    account_id - organization GitHub id;
    installation_id - number of bot installation provided by GitHub;
    access_code and access_token - tokens from bot maintenance page;
    bugout_holder_id - connection to Brood model;
    bugout_secret - each GitHub organization should add into GitHub secrets this token
    and call it BUGOUT_SECRET.
    """

    __tablename__ = "github_oauth_events"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    github_account_id = Column(Integer, nullable=False, unique=True)
    github_installation_id = Column(Integer, nullable=False, unique=True)
    github_installation_url = Column(String, nullable=False, unique=True)

    access_code = Column(String)
    access_token = Column(String)
    access_token_expire_ts = Column(DateTime(timezone=True))

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


class GitHubBugoutUser(Base):  # type: ignore
    __tablename__ = "github_bugout_users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_oauth_events.id",
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


class GitHubRepo(Base):  # type: ignore
    """
    List of all organization repositories.

    Links with summaries related to.
    """

    __tablename__ = "github_repos"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_oauth_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    github_repo_id = Column(Integer, nullable=False)
    github_repo_name = Column(String, nullable=False)
    github_repo_url = Column(String, nullable=False)
    private = Column(Boolean, nullable=False)
    default_branch = Column(String, nullable=False)


class GitHubIssuePR(Base):  # type: ignore
    """
    Contains GitHub Issues and Pull Requests for installations.

    MutableDict JSONB docs:
    https://docs.sqlalchemy.org/en/14/orm/extensions/mutable.html
    """

    __tablename__ = "github_issues_prs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    repo_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_repos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_oauth_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    comments_url = Column(String, nullable=True)
    terminal_hash = Column(String, nullable=True)  # Nullable if Issue
    branch = Column(String, nullable=True)
    entry_id = Column(String, nullable=True)


class GitHubCheck(Base):  # type: ignore
    """
    Repository check results after commits in Pull Requests.

    Docs:
    https://docs.github.com/en/free-pro-team@latest/rest/reference/checks#create-a-check-run
    """

    __tablename__ = "github_checks"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    issue_pr_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_issues_prs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    repo_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_repos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_oauth_events.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    github_check_id = Column(String, nullable=False)
    github_check_name = Column(String, nullable=False)
    github_status = Column(String, nullable=True)
    github_conclusion = Column(String, nullable=True)


class GitHubCheckNotes(Base):  # type: ignore
    """
    Contains commands from comments args mentions.
    """

    __tablename__ = "github_check_notes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    check_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_checks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    note = Column(String, nullable=False)
    created_by = Column(String, nullable=False)
    accepted = Column(Boolean, default=False, nullable=False)
    accepted_by = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=utcnow(),
        onupdate=utcnow(),
        nullable=False,
    )


class GitHubLocust(Base):  # type: ignore
    """
    Contains Locust summaries stored in AWS S3.
    """

    __tablename__ = "github_locusts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        unique=True,
        nullable=False,
    )
    issue_pr_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_issues_prs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    terminal_hash = Column(String, nullable=False)
    s3_uri = Column(String, nullable=True)

    response_url = Column(String, nullable=True)
    commented_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=utcnow(), nullable=False
    )


class GithubIndexConfiguration(Base):  # type: ignore
    __tablename__ = "github_index_configurations"

    github_oauth_event_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "github_oauth_events.id",
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
            "github_oauth_event_id",
            "index_name",
        ),
    )
