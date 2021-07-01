"""
According with BUG-132 was added table GitHubBugoutUser.
It requires additional script to generate BugoutUser for existing installations
after database migration.
"""
import argparse
import uuid

from ..models import GitHubOAuthEvent, GitHubBugoutUser
from ...broodusers import bugout_api
from ...db import yield_connection_from_env_ctx
from ...utils.settings import INSTALLATION_TOKEN, BOT_INSTALLATION_TOKEN_HEADER


def main(args: argparse.Namespace) -> None:
    if args.run:
        print("Starting upgrade")
        with yield_connection_from_env_ctx() as db_session:

            bot_installations = db_session.query(GitHubOAuthEvent).all()

            for bot_installation in bot_installations:
                user_installation = (
                    db_session.query(GitHubBugoutUser)
                    .filter(GitHubBugoutUser.event_id == bot_installation.id)
                    .one_or_none()
                )
                if user_installation is not None:
                    continue

                org_name = bot_installation.github_installation_url.rstrip("/").split(
                    "/"
                )[-1]

                # Create Brood user
                generated_password: str = str(uuid.uuid4())

                username = f"{org_name}-{bot_installation.github_account_id}"
                email = f"{org_name}-{bot_installation.github_account_id}@bugout.dev"

                headers = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}
                bugout_user = bugout_api.create_user(
                    username, email, generated_password, headers=headers
                )
                bugout_user_token = bugout_api.create_token(
                    username, generated_password
                )

                installation_user = GitHubBugoutUser(
                    event_id=bot_installation.id,
                    bugout_user_id=bugout_user.id,
                    bugout_access_token=bugout_user_token.id,
                )

                db_session.add(installation_user)
                db_session.commit()

                installation_group_name = (
                    f"Team group: {org_name}-{bot_installation.github_account_id}"
                )
                # TODO(kompotkot): Add group id to SlackBugoutUser

                if bot_installation.deleted is False:
                    bugout_api.create_group(
                        installation_user.bugout_access_token, installation_group_name
                    )

                print(
                    f"Installation {bot_installation.github_installation_id} complete."
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Bugout user and group for installations"
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    parser.add_argument("run", help="Start upgrade existing installations")
    args = parser.parse_args()
    main(args)
