"""
Spire GitHub CLI.
Script callable from systemd.

python -m spire.github.cli update
python -m spire.github.cli activate -i <uuid>
"""
import argparse
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional
import uuid

from sqlalchemy.orm import Session

from . import actions
from .api import submit_oauth
from .models import GitHubOAuthEvent
from ..db import SessionLocal


def get_installation(args: argparse.Namespace) -> None:
    """
    Get the GitHub App installations in the given database to screen.
    If url or installation id is provided, it is expected to be a GitHub organization URL
    and is used as a filter to return only the installation for the given organization if it exists.
    """
    session = SessionLocal()
    try:
        query = session.query(GitHubOAuthEvent)
        if args.url is not None:
            query = query.filter(GitHubOAuthEvent.github_installation_url == args.url)
        if args.github_id is not None:
            query = query.filter(
                GitHubOAuthEvent.github_installation_id == args.github_id
            )
        if args.id is not None:
            query = query.filter(GitHubOAuthEvent.id == args.id)

        bot_installations = query.all()

        if len(bot_installations) == 0:
            raise actions.InstallationNotFound("No installations found")

        for bot_installation in bot_installations:
            print(f"Installation with event id: {str(bot_installation.id)}")
            print(
                f"{' ' * 4}github installation id: {str(bot_installation.github_installation_id)}"
            )
            print(
                f"{' ' * 4}github installation url: {str(bot_installation.github_installation_url)}"
            )
            print(
                f"{' ' * 4}github account id: {str(bot_installation.github_account_id)}"
            )
            print(
                f"{' ' * 4}access token expire in: {str(bot_installation.access_token_expire_ts - datetime.now(timezone.utc))}"
            )
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def update_installation(args: argparse.Namespace) -> None:
    """
    Updates the GitHub App installations in the given database.
    If url or id is provided, it is expected to be a GitHub organization URL.
    """
    session = SessionLocal()
    try:
        query = session.query(GitHubOAuthEvent)
        if args.id is not None:
            query = query.filter(GitHubOAuthEvent.id == args.id)
        bot_installations = query.filter(
            GitHubOAuthEvent.access_token_expire_ts - timedelta(minutes=5)
            <= datetime.utcnow()
        ).all()
        if len(bot_installations) == 0:
            raise actions.InstallationNotFound("No installations to update")

        for bot_installation in bot_installations:
            submit_oauth(
                bot_installation.access_code, bot_installation.github_installation_id
            )
            print(
                f"Updated token for installation with github_account_id: {str(bot_installation.github_account_id)}"
            )
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Administrative actions for Bugout GitHub API"
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = parser.add_subparsers(description="GitHub commands")

    # GitHub app installations module
    parser_installations = subcommands.add_parser(
        "installations", description="GitHub app installations"
    )
    parser_installations.set_defaults(func=lambda _: parser_installations.print_help())
    subcommands_installations = parser_installations.add_subparsers(
        description="GitHub app installations commands"
    )
    parser_installations_get = subcommands_installations.add_parser(
        "get", description="Get installations"
    )
    parser_installations_get.add_argument(
        "-i", "--id", help="GitHub event installation ID"
    )
    parser_installations_get.add_argument(
        "-g", "--github_id", help="GitHub organisation ID"
    )
    parser_installations_get.add_argument("-u", "--url", help="GitHub organisation URL")
    parser_installations_get.set_defaults(func=get_installation)

    parser_installations_update = subcommands_installations.add_parser(
        "update", description="Update installations"
    )
    parser_installations_update.add_argument(
        "-i", "--id", help="GitHub event installation ID"
    )
    parser_installations_update.set_defaults(func=update_installation)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
