import argparse
import logging

from sqlalchemy.orm import Session

from .. import admin
from ..models import SlackOAuthEvent
from ...db import yield_connection_from_env_ctx
from ...broodusers import get_bugout_user, Existence


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def upgrade_one(
    db_session: Session, bot_installation: SlackOAuthEvent, bugout_token: str
) -> SlackOAuthEvent:
    get_bugout_user(db_session, bot_installation.id, throw_on=Existence.Exists)
    bugout_auth_url = admin.auth_url_from_env()
    admin.authorize_bot_installation(db_session, bot_installation, bugout_auth_url)
    return bot_installation


def main(args: argparse.Namespace) -> None:
    with yield_connection_from_env_ctx() as db_session:
        query = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.version == 2)
            .filter(SlackOAuthEvent.deleted is not False)
            .filter(SlackOAuthEvent.team_id == args.workspace)
        )
        bot_installation = query.one()

        logger.info(
            f"Authorizing installation {bot_installation.id} for team {bot_installation.team_id}"
            f" ({bot_installation.team_name})"
        )

        try:
            upgrade_one(db_session, bot_installation, args.token)
        except Exception as e:
            logger.error(
                f"Error authorizing installation {bot_installation.id} for team "
                f"{bot_installation.team_id} ({bot_installation.team_name})"
            )
            logger.error(repr(e))

        logger.info("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Authorize a @bugout slack installation to act as a Bugout user"
    )
    parser.add_argument(
        "-w",
        "--workspace",
        required=True,
        type=str,
        help="ID for the bot installation",
    )
    parser.add_argument(
        "-t", "--token", required=True, type=str, help="Bugout authentication token"
    )
    args = parser.parse_args()
    main(args)
