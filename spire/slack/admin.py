"""
Slackbot administration directives
"""
import argparse
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session

from ..db import yield_connection_from_env_ctx
from .models import SlackOAuthEvent, SlackBugoutUser
from .data import BroodUser
from .indices import create_team_journal_and_register_index
from ..broodusers import (
    Existence,
    Method,
    bugout_api,
    get_bugout_user,
    process_group_in_journal_holders,
    BugoutUserFound,
)
from ..utils.settings import (
    SPIRE_API_URL,
    INSTALLATION_TOKEN,
    BOT_INSTALLATION_TOKEN_HEADER,
)

logger = logging.getLogger(__name__)


class BugoutAuthConfigurationError(ValueError):
    """
    Raised when Bugout bot tries to authenticate using a Bugout authentication server, but no
    such server is specified.
    """


class BugoutAdminForbidden(Exception):
    """
    Raised when a non-admin user attempts to take an admin action.
    """


def auth_url_from_env() -> str:
    """
    Retrieves Bugout authentication server URL from the BUGOUT_AUTH_URL environment variable.
    """
    bugout_auth_url = os.environ.get("BUGOUT_AUTH_URL")
    if bugout_auth_url is None:
        raise BugoutAuthConfigurationError(
            "BUGOUT_AUTH_URL environment variable not set"
        )
    bugout_auth_url = bugout_auth_url.rstrip("/")
    return bugout_auth_url


COMMAND_AUTHORIZE = "authorize"
COMMAND_REVOKE = "revoke"
COMMAND_STATUS = "status"


def populate_admin_parser(parser: argparse.ArgumentParser) -> None:
    """
    Populates an argparse ArgumentParser with administration directives.
    """
    parser.set_defaults(func=parser.format_help)
    subparsers = parser.add_subparsers(
        title="Administrative commands", dest="admin_command"
    )

    login_parser = subparsers.add_parser(
        COMMAND_AUTHORIZE,
        description="Authorize user at Slack workspace to use Bugout account by providing an username",
    )
    login_parser.add_argument("username", help="Bugout account username")

    revoke_parser = subparsers.add_parser(
        COMMAND_REVOKE,
        description="Revoke user access at Slack workspace to use Bugout username",
    )
    revoke_parser.add_argument("username", help="Bugout account username")

    status_parser = subparsers.add_parser(
        COMMAND_STATUS, description="Check the authentication status of @bugout"
    )


def authorize_bot_installation(
    db_session: Session,
    bot_installation: SlackOAuthEvent,
    bugout_auth_url: str,
) -> SlackBugoutUser:
    """
    Authorize a bot installation, checks if current_slack_bugout_user exists then return it.

    If the user does not exist, a new one is created with credentials:
    username: {bot_installation.team_name}-{bot_installation.team_id}
    email: {bot_installation.team_name}-{bot_installation.team_id}@bugout.dev
    password: randomly generated uuid4

    User creates group, journal and add group in journal holders.
    """
    query = db_session.query(SlackBugoutUser).filter(
        SlackBugoutUser.slack_oauth_event_id == bot_installation.id
    )
    current_slack_bugout_user = query.one_or_none()

    if not current_slack_bugout_user:
        # Create new Bugout user and generate token with Brood API
        generated_password: str = str(uuid.uuid4())
        username = f"{bot_installation.team_name}-{bot_installation.team_id}"
        email = f"{bot_installation.team_name}-{bot_installation.team_id}@bugout.dev"

        headers = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}
        bugout_user = bugout_api.create_user(
            username, email, generated_password, headers=headers
        )
        bugout_user_token = bugout_api.create_token(username, generated_password)

        slack_bugout_user = SlackBugoutUser(
            slack_oauth_event_id=bot_installation.id,
            bugout_user_id=bugout_user.id,
            bugout_access_token=bugout_user_token.id,
        )
        db_session.add(slack_bugout_user)
    else:
        # If connection between Slack Workspace and slack_installation user already exists,
        # if bot was installed before - use those SlackBugoutUser.
        slack_bugout_user = current_slack_bugout_user

    db_session.commit()

    # Generate journal and configure index
    journal_api_url = f"{SPIRE_API_URL.rstrip('/')}/journals/"
    index_configuration = create_team_journal_and_register_index(
        db_session, journal_api_url, bot_installation
    )
    journal_id = index_configuration.index_url.rstrip("/").split("/")[-2]

    # Create Brood group and add group in bugout holders list
    group_name = f"Slack team: {bot_installation.team_name if bot_installation.team_name is not None else ''}"
    bugout_group = bugout_api.create_group(
        slack_bugout_user.bugout_access_token, group_name
    )
    query.update({SlackBugoutUser.bugout_group_id: bugout_group.id})
    db_session.commit()

    process_group_in_journal_holders(
        Method.post,
        journal_id,
        journal_api_url,
        slack_bugout_user.bugout_access_token,
        bugout_group.id,
        bot_installation,
    )

    return slack_bugout_user


async def admin_handler(
    blocks: List[Dict[str, Any]],
    args: argparse.Namespace,
    team_id: str,
    user_id: str,
    channel_id: str,
    spire_api_url: str,
    bot_installation: SlackOAuthEvent,
):
    """
    Handles admin actions in @bugout bot invocations.

    Mutates the given Slack message blocks based on result of admin action.
    """
    with yield_connection_from_env_ctx() as db_session:
        bugout_auth_url = auth_url_from_env()

        if args.admin_command is None:
            help_message = args.func()
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"```{help_message}```"},
                }
            )
        elif user_id != bot_installation.authed_user_id:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "You are not authorized to use these commands. Contact "
                            f"<@{bot_installation.authed_user_id}> if you would like to change "
                            f"administrative settings. If <@{bot_installation.authed_user_id}> is"
                            "unavailable, reach out to Neeraj (neeraj@simiotics.com)."
                        ),
                    },
                }
            )
        elif args.admin_command == COMMAND_AUTHORIZE:
            try:
                slack_bugout_user = get_bugout_user(
                    db_session,
                    bot_installation.id,
                    throw_on=Existence.DoesNotExist,
                )
                bugout_user = (
                    db_session.query(SlackBugoutUser)
                    .filter(SlackBugoutUser.slack_oauth_event_id == bot_installation.id)
                    .one()
                )

                bugout_api.set_user_group(
                    token=bugout_user.bugout_access_token,
                    group_id=bugout_user.bugout_group_id,
                    user_type="member",
                    username=args.username,
                )

            except BugoutUserFound as e:
                logger.error(repr(e))
                return blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "It seems you have already associated a Bugout account with this "
                                "slack workspace. Contact Neeraj (neeraj@simiotics.com) if "
                                "something is wrong and you would like to fix it."
                            ),
                        },
                    }
                )

            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Authorization granted"},
                }
            )
        elif args.admin_command == COMMAND_REVOKE:
            try:
                slack_bugout_user = get_bugout_user(
                    db_session,
                    bot_installation.id,
                    throw_on=Existence.DoesNotExist,
                )
                bugout_user = (
                    db_session.query(SlackBugoutUser)
                    .filter(SlackBugoutUser.slack_oauth_event_id == bot_installation.id)
                    .one()
                )

                bugout_api.delete_user_group(
                    token=bugout_user.bugout_access_token,
                    group_id=bugout_user.bugout_group_id,
                    username=args.username,
                )

            except BugoutUserFound as e:
                logger.error(repr(e))
                return blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "It seems you have already associated a Bugout account with this "
                                "slack workspace. Contact Neeraj (neeraj@simiotics.com) if "
                                "something is wrong and you would like to fix it."
                            ),
                        },
                    }
                )
            blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "User authorization revoked"},
                }
            )
        elif args.admin_command == COMMAND_STATUS:
            bugout_user = get_bugout_user(db_session, bot_installation.id)
            if bugout_user is None:
                return blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "```Status: Unauthenticated```\nRegister an account at "
                                "https://alpha.bugout.dev, copy the API key in your user page, and "
                                "enter it here using `@bugout admin authorize <key>`."
                            ),
                        },
                    }
                )

            try:
                slack_bugout_user = get_bugout_user(
                    db_session,
                    bot_installation.id,
                    throw_on=Existence.DoesNotExist,
                )
                bugout_user = BroodUser(
                    id=slack_bugout_user.bugout_user_id,
                    token=slack_bugout_user.bugout_access_token,
                )
                bugout_user_groups = bugout_api.get_user_groups(bugout_user.token)

            except BugoutUserFound as e:
                logger.error(repr(e))
                return blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "It seems you have already associated a Bugout account with this "
                                "slack workspace. Contact Neeraj (neeraj@simiotics.com) if "
                                "something is wrong and you would like to fix it."
                            ),
                        },
                    }
                )
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"```Status: Authenticated\n"
                            f"Groups: {', '.join([group.group_name for group in bugout_user_groups.groups if group.group_name is not None])}\n```"
                        ),
                    },
                }
            )
