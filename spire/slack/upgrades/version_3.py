import argparse
import logging

from sqlalchemy.orm import Session

from ...db import yield_connection_from_env_ctx
from ..models import SlackOAuthEvent
from . import scopes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scope_string = "commands"
required_scopes = scopes.parse_scopes(scope_string)


def upgrade_one(
    db_session: Session, bot_installation: SlackOAuthEvent
) -> SlackOAuthEvent:
    assert bot_installation.version == 2
    bot_installation = scopes.check_scopes(bot_installation, required_scopes)
    bot_installation.version = 3
    db_session.add(bot_installation)
    db_session.commit()
    return bot_installation


def main(args: argparse.Namespace) -> None:
    with yield_connection_from_env_ctx() as db_session:
        query = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.version == 2)
            .filter(SlackOAuthEvent.deleted is not False)
        )
        if args.workspace is not None:
            query = query.filter(SlackOAuthEvent.team_id == args.workspace)
        installations_for_upgrade = query.all()

        for bot_installation in installations_for_upgrade:
            logger.info(
                f"Upgrading installation {bot_installation.id} for team {bot_installation.team_id} "
                f"({bot_installation.team_name}) to version 3"
            )

            try:
                upgrade_one(db_session, bot_installation)
            except scopes.InsufficientSlackScopes as e:
                logger.error(repr(e))

        logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set up fresh installations of the @bugout slack bot"
    )
    parser.add_argument(
        "-w",
        "--workspace",
        required=False,
        type=str,
        default=None,
        help="ID for the bot installation",
    )
    args = parser.parse_args()
    main(args)
