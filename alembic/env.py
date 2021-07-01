from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# Original: target_metadata = None
from spire.go.models import Base as GoBase
from spire.journal.models import Base as JournalBase
from spire.slack.models import Base as SlackBase
from spire.github.models import Base as GitHubBase
from spire.preferences.models import Base as PreferencesBase
from spire.humbug.models import Base as HumbugBase
from spire.public.models import Base as PublicBase

target_metadata = (
    GoBase.metadata,
    SlackBase.metadata,
    JournalBase.metadata,
    GitHubBase.metadata,
    PreferencesBase.metadata,
    HumbugBase.metadata,
    PublicBase.metadata,
)

# include_symbol to prevent alembic from messing with non-Spire tables
from spire.go.models import PermalinkJournal, PermalinkJournalEntry
from spire.journal.models import (
    Journal,
    JournalEntryTag,
    JournalEntry,
    JournalPermissions,
    SpireOAuthScopes,
)
from spire.preferences.models import DefaultJournal
from spire.slack.models import (
    SlackOAuthEvent,
    SlackMention,
    SlackBugoutUser,
    SlackIndexConfiguration,
)
from spire.github.models import (
    GitHubOAuthEvent,
    GitHubBugoutUser,
    GitHubRepo,
    GitHubIssuePR,
    GitHubCheck,
    GitHubCheckNotes,
    GitHubLocust,
    GithubIndexConfiguration,
)
from spire.humbug.models import HumbugEvent, HumbugBugoutUser, HumbugBugoutUserToken
from spire.public.models import PublicJournal, PublicUser


def include_symbol(tablename, schema):
    return tablename in {
        PermalinkJournal.__tablename__,
        PermalinkJournalEntry.__tablename__,
        SlackOAuthEvent.__tablename__,
        SlackMention.__tablename__,
        SlackBugoutUser.__tablename__,
        SlackIndexConfiguration.__tablename__,
        Journal.__tablename__,
        JournalEntry.__tablename__,
        JournalEntryTag.__tablename__,
        JournalPermissions.__tablename__,
        SpireOAuthScopes.__tablename__,
        GitHubOAuthEvent.__tablename__,
        GitHubBugoutUser.__tablename__,
        GitHubRepo.__tablename__,
        GitHubIssuePR.__tablename__,
        GitHubCheck.__tablename__,
        GitHubCheckNotes.__tablename__,
        GitHubLocust.__tablename__,
        GithubIndexConfiguration.__tablename__,
        DefaultJournal.__tablename__,
        HumbugEvent.__tablename__,
        HumbugBugoutUser.__tablename__,
        HumbugBugoutUserToken.__tablename__,
        PublicJournal.__tablename__,
        PublicUser.__tablename__,
    }


# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="spire_alembic_version",
        include_symbol=include_symbol,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="spire_alembic_version",
            include_symbol=include_symbol,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
