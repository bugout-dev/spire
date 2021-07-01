"""
Check slack installations
"""
import argparse
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from ..db import yield_connection_from_env_ctx
from .models import SlackOAuthEvent


def list_installations(db_session: Session, workspace: Optional[str] = None) -> None:
    """
    Prints the Bugout slackbot installations in the given database to screen.

    If workspace is provided, it is expected to be a Slack team ID and is used as a filter to return
    only the installation for the given team ID if it exists.
    """
    query = db_session.query(SlackOAuthEvent)
    if workspace is not None:
        query = query.filter(SlackOAuthEvent.team_id == workspace)

    installations = query.all()

    print("Installations:")
    for installation in installations:
        print(f"  - team_name: {installation.team_name}")
        print(f"    id: {str(installation.id)}")
        print(f"    team_id: {installation.team_id}")
        print(f"    bot_user_id: {installation.bot_user_id}")
        print(f"    created_at: {installation.created_at}")


def wipe_installation(db_session: Session, workspace: Optional[str]) -> None:
    if workspace is None:
        raise ValueError("Please specify a workspace to wipe")

    bot_installation = (
        db_session.query(SlackOAuthEvent)
        .filter(SlackOAuthEvent.team_id == workspace)
        .one()
    )

    db_session.delete(bot_installation)
    db_session.commit()

    print("Wiped:")
    print(f" - id: {bot_installation.id}")
    print(f"   team_id: {workspace}")
    print(
        '   message: "You may have to manually delete the team journal for this workspace"'
    )


def main() -> None:
    commands: Dict[str, Callable[[Session, Optional[str]], None]] = {
        "list": list_installations,
        "wipe": wipe_installation,
    }
    parser = argparse.ArgumentParser(
        description="Administrative actions for Bugout Slack installations"
    )
    parser.add_argument("command", choices=commands)
    parser.add_argument("--workspace", "-w", default=None, help="Slack team ID")

    args = parser.parse_args()

    with yield_connection_from_env_ctx() as db_session:
        commands[args.command](db_session, args.workspace)


if __name__ == "__main__":
    main()
