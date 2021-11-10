"""
Operations with search indices
"""
import argparse
import json
import logging
import textwrap
from typing import Any, Callable, cast, Dict, List, Union
import uuid

import requests
from sqlalchemy.orm import Session

from .data import Index
from .models import SlackIndexConfiguration, SlackOAuthEvent, SlackBugoutUser
from ..db import yield_connection_from_env_ctx
from ..broodusers import get_bugout_user, Existence
from ..utils.settings import BUGOUT_CLIENT_ID_HEADER

logger = logging.getLogger(__name__)


class IndexAlreadyExists(Exception):
    """
    Raised if an index already exists when it wasn't expected to.
    """


def get_default_indices() -> List[Index]:
    """
    Return a list of specifications for the default indices.
    """
    indices = [
        Index(
            index_name="web",
            index_url="https://search.simiotics.com/parasite",
            description="Bugout's public web index.",
            use_bugout_auth=False,
            use_bugout_client_id=True,
        ),
        Index(
            index_name="usage",
            index_url="https://search.simiotics.com/usage",
            description=(
                "(Highly experimental!) Use Bugout to find public examples showing how to use "
                "library methods."
            ),
            use_bugout_auth=False,
            use_bugout_client_id=True,
        ),
    ]

    return indices


def create_team_journal_and_register_index(
    db_session: Session,
    journal_api_url: str,
    bot_installation: SlackOAuthEvent,
) -> Index:
    """
    Creates a team journal and registers the index as a Slack index configuration. This only works
    for authenticated Bugout installations.
    """
    index_name = "journal"
    journal_count = (
        db_session.query(SlackIndexConfiguration)
        .filter(SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id)
        .filter(SlackIndexConfiguration.index_name == index_name)
        .count()
    )
    if journal_count > 0:
        # If Index already exists and configured for workspace before, it means was installed before
        # so just return already configured SlackIndexConfiguration
        slack_index_configuration = (
            db_session.query(SlackIndexConfiguration)
            .filter(SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id)
            .filter(SlackIndexConfiguration.index_name == index_name)
            .first()
        )
        index_configuration = Index(
            index_name=slack_index_configuration.index_name,
            index_url=slack_index_configuration.index_url,
            description=slack_index_configuration.description,
            use_bugout_auth=slack_index_configuration.use_bugout_auth,
            use_bugout_client_id=slack_index_configuration.use_bugout_client_id,
        )
        return index_configuration

    bugout_user = get_bugout_user(
        db_session,
        bot_installation.id,
        throw_on=Existence.DoesNotExist,
    )
    bugout_user = cast(SlackBugoutUser, bugout_user)

    journal_name = "Team journal" + (
        f": {bot_installation.team_name}"
        if bot_installation.team_name is not None
        else ""
    )

    # Create journal request against journal API
    if journal_api_url[-1] != "/":
        journal_api_url += "/"

    logger.info(f"Requesting new journal creation: {journal_api_url}")

    headers = {
        "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}",
    }

    payload = {"name": journal_name}
    r = requests.post(journal_api_url, json=payload, headers=headers, timeout=3)
    r.raise_for_status()
    response = r.json()

    # Register the index under the bot index configurations
    # Note that, at this point, journal_api_url should already have a trailing slash.
    index_url = f"{journal_api_url}{response['id']}/search"
    index = SlackIndexConfiguration(
        slack_oauth_event_id=bot_installation.id,
        index_name=index_name,
        index_url=index_url,
        description=(
            "This is your team journal. You can add entries to it from Slack by reacting to "
            "comments using the :bugout: emoji."
        ),
        use_bugout_auth=True,
        use_bugout_client_id=True,
    )
    db_session.add(index)
    db_session.commit()

    index_configuration = Index(
        index_name=index.index_name,
        index_url=index.index_url,
        description=index.description,
        use_bugout_auth=index.use_bugout_auth,
        use_bugout_client_id=index.use_bugout_client_id,
    )

    return index_configuration


def get_index_by_name(
    db_session: Session,
    bot_installation: SlackOAuthEvent,
    index_name: str,
) -> SlackIndexConfiguration:
    """
    Gets an index by name. Raises an error if the index is not found.
    """
    indices_query = (
        db_session.query(SlackIndexConfiguration)
        .filter(SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id)
        .filter(SlackIndexConfiguration.index_name == index_name)
    )
    return indices_query.one()


def get_installation_indices(
    db_session: Session, bot_installation: SlackOAuthEvent
) -> List[SlackIndexConfiguration]:
    """
    Gets all the indices set up in an installation of the bot.
    """
    indices_query = db_session.query(SlackIndexConfiguration).filter(
        SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id
    )
    return indices_query.all()


def get_installation_indices_by_installation_id(
    db_session: Session, installation_id: Union[str, uuid.UUID]
) -> List[SlackIndexConfiguration]:
    """
    Gets all the indices set up in an installation given on the ID of that installation.
    """
    bot_installation = (
        db_session.query(SlackOAuthEvent)
        .filter(SlackOAuthEvent.id == installation_id)
        .one()
    )
    return get_installation_indices(db_session, bot_installation)


def update_installation_default_indices(
    db_session: Session, bot_installation: SlackOAuthEvent
) -> None:
    """
    Update the default index configurations for a given installation.
    """
    default_indices = get_default_indices()

    indices = (
        db_session.query(SlackIndexConfiguration)
        .filter(SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id)
        .filter(
            SlackIndexConfiguration.index_name.in_(
                [index_spec.index_name for index_spec in default_indices]
            )
        )
    )
    for index in indices:
        db_session.delete(index)
    db_session.commit()

    for default_index in default_indices:
        index_configuration = SlackIndexConfiguration(
            slack_oauth_event_id=bot_installation.id, **default_index.dict()
        )
        db_session.add(index_configuration)
    db_session.commit()


def deconfigure_custom_indices(
    db_session: Session, bot_installation: SlackOAuthEvent
) -> None:
    """
    Removes Slack index configurations for non-default indices.
    """
    default_indices = get_default_indices()
    default_index_names = [index_spec.index_name for index_spec in default_indices]
    indices = get_installation_indices(db_session, bot_installation)
    for index in indices:
        if index.index_name not in default_index_names:
            db_session.delete(index)
    db_session.commit()


def populate_indices_parser(indices_parser: argparse.ArgumentParser) -> None:
    """
    Populates argument parser for the `@bugout indices` command.
    """
    subparsers = indices_parser.add_subparsers(
        title="Index-related subcommands", dest="indices_subcommand"
    )

    list_parser = subparsers.add_parser(
        "list", description="Lists the configured search indices"
    )


def indices_blocks_modifier(
    db_session: Session,
    blocks: List[Dict[str, Any]],
    args: argparse.Namespace,
    team_id: str,
    user_id: str,
    channel_id: str,
    bot_installation: SlackOAuthEvent,
    spire_api_url: str,
):
    """
    Handles @bugout index commands.
    """
    try:
        if args.indices_subcommand == "list":
            indices = get_installation_indices(db_session, bot_installation)

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_These are the search indices configured in your Slack workspace:_",
                    },
                }
            )
            for index in indices:
                index_summary = textwrap.dedent(
                    f"""
                    Index: `{index.index_name}`
                    URL: `{index.index_url}`
                    Requires Bugout token? `{index.use_bugout_auth}`

                    {index.description}
                    """
                )
                blocks.extend(
                    [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": index_summary},
                        },
                        {"type": "divider"},
                    ]
                )

            blocks.extend(
                [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "You can use any of these search indices by typing:\n"
                                "```@bugout search <index_name> <search_query>```"
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "For indices which require a Bugout token, ask your Bugout bot "
                                f"administrator (<@{bot_installation.authed_user_id}>) to set up a "
                                "token using: `@bugout admin register` or `@bugout admin login`."
                            ),
                        },
                    },
                ]
            )
    except Exception as e:
        logger.error(
            f"Error operating on indices for installation id={str(bot_installation.id)}, team_id="
            f"{bot_installation.team_id}, team_name={bot_installation.team_name}:\n"
            f"{repr(e)}"
        )
        return blocks.extend(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            "There was an error operating on the indexes configured for this "
                            "workspace. If this persists, email Neeraj (neeraj@simiotics.com)."
                        ),
                    },
                },
                {"type": "divider"},
            ]
        )


def argparse_handler(inside_function: Callable) -> Callable[[argparse.Namespace], Any]:
    """
    Wraps a function to make it an argparse handler (usable with the args.func(args) pattern).
    Requires that the inside_function not have any purely positional arguments.
    """

    def wrapped_function(args: argparse.Namespace) -> Any:
        return inside_function(**vars(args))

    return wrapped_function


@argparse_handler
def update_all_installations_default_indices(db_session: Session, **kwargs) -> None:
    """
    Updates the default indices for all bot installations in the given database.
    """
    all_installations = db_session.query(SlackOAuthEvent).all()
    for installation in all_installations:
        try:
            update_installation_default_indices(db_session, installation)
        except Exception as e:
            logger.error(
                f"Error updating installation {installation.id} for workspace "
                f"{installation.team_id} ({installation.team_name}):\n{repr(e)}"
            )
            db_session.rollback()

    logger.info("Done")


@argparse_handler
def handle_get_indices(db_session: Session, installation_id: str, **kwargs) -> None:
    """
    Prints indices for the installation specified at command line.
    """
    indices = get_installation_indices_by_installation_id(db_session, installation_id)
    print("indices:")
    for index in indices:
        print(f"  - index_name: {index.index_name}")
        print(f"    index_url: {index.index_url}")
        print(f"    use_bugout_auth: {index.use_bugout_auth}")
        print(f"    use_bugout_client_id: {index.use_bugout_client_id}")


@argparse_handler
def handle_create_journal(
    db_session: Session, journal_api_url: str, installation_id: str, **kwargs
) -> None:
    """
    Creates a team journal and registers the journal index for the given Bugout slack installation.
    """
    bot_installation = (
        db_session.query(SlackOAuthEvent)
        .filter(SlackOAuthEvent.id == installation_id)
        .one()
    )
    index_configuration = create_team_journal_and_register_index(
        db_session, journal_api_url, bot_installation
    )
    print(json.dumps(index_configuration.dict(), indent=2))


@argparse_handler
def handle_deconfigure_custom(
    db_session: Session, installation_id: str, **kwargs
) -> None:
    """
    Handles the deconfigure-custom CLI command.
    """
    bot_installation = (
        db_session.query(SlackOAuthEvent)
        .filter(SlackOAuthEvent.id == installation_id)
        .one()
    )
    deconfigure_custom_indices(db_session, bot_installation)


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Slack index operation CLI")
    subparsers = parser.add_subparsers(title="Commands")

    update_all_parser = subparsers.add_parser(
        "update-all-defaults", description="Update default indices for all workspaces"
    )
    update_all_parser.set_defaults(func=update_all_installations_default_indices)

    get_indices_parser = subparsers.add_parser(
        "get-indices", description="View indices set up in an installation"
    )
    get_indices_parser.add_argument(
        "-i", "--installation-id", required=True, help="ID for the installation"
    )
    get_indices_parser.set_defaults(func=handle_get_indices)

    create_journal_parser = subparsers.add_parser(
        "create-journal", description="Create a team journal for an installation"
    )
    create_journal_parser.add_argument("-j", "--journal-api-url", required=True)
    create_journal_parser.add_argument(
        "-i", "--installation-id", required=True, help="ID for the installation"
    )
    create_journal_parser.set_defaults(func=handle_create_journal)

    deconfigure_custom_parser = subparsers.add_parser(
        "deconfigure-custom",
        description="Remove index configurations for all custom indices",
    )
    deconfigure_custom_parser.add_argument(
        "-i", "--installation-id", required=True, help="ID for the installation"
    )
    deconfigure_custom_parser.set_defaults(func=handle_deconfigure_custom)

    args = parser.parse_args()
    with yield_connection_from_env_ctx() as db_session:
        args.db_session = db_session
        args.func(args)


if __name__ == "__main__":
    main()
