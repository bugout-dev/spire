import argparse
import logging

from sqlalchemy.orm import Session

from ...db import yield_connection_from_env_ctx
from ..indices import update_installation_default_indices
from ..models import SlackOAuthEvent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade_one(
    db_session: Session, bot_installation: SlackOAuthEvent
) -> SlackOAuthEvent:
    update_installation_default_indices(db_session, bot_installation)
    bot_installation.version = 2
    db_session.add(bot_installation)
    db_session.commit()
    return bot_installation


def main(args: argparse.Namespace) -> None:
    with yield_connection_from_env_ctx() as db_session:
        query = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.version == 1)
            .filter(SlackOAuthEvent.deleted is not False)
        )
        if args.workspace is not None:
            query = query.filter(SlackOAuthEvent.team_id == args.workspace)
        installations_for_upgrade = query.all()

        for bot_installation in installations_for_upgrade:
            logger.info(
                f"Upgrading installation {bot_installation.id} for team {bot_installation.team_id} "
                f"({bot_installation.team_name}) to version 2"
            )
            upgrade_one(db_session, bot_installation)

        logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set up default search indices for fresh @bugout slack installations"
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
