"""
Handlers for Bugout Slack CLI
"""
import argparse
import json
import logging
import os
import textwrap
from typing import Any, cast, Dict, List, Optional
import urllib
import urllib.parse

import requests
from sqlalchemy.orm import Session

from . import admin as slack_admin
from . import indices as slack_indices
from .models import SlackOAuthEvent, SlackMention, SlackBugoutUser
from .parse import SlackTextTokenType, parse_raw_text
from .handlers import HTMLToText, InstallationNotFound
from .. import db
from ..broodusers import get_bugout_user, BugoutUserNotFound, Existence
from ..utils.settings import BUGOUT_CLIENT_ID_HEADER

logger = logging.getLogger(__name__)


SLACK_MAX_BLOCK_LENGTH = 2900
SLACK_MESSAGE_CONTINUATION = "..."


class SlackArgumentParseError(Exception):
    """
    Raised when there is an error parsing arguments for a CLI invocation from Slack.
    """


class CustomHelpAction(argparse._HelpAction):
    """
    Custom argparse action that handles -h and --help flags in Bugout Slack argument parsers.

    This is part of the dirty hack to get around the annoying exit behaviour of argparse. The other
    part of this is the custom ArgumentParser subclass we use (defined below).
    """

    def __init__(
        self,
        option_strings,
        dest=argparse.SUPPRESS,
        default=argparse.SUPPRESS,
        help=None,
    ):
        super().__init__(option_strings, dest, default, help)

    def __call__(self, parser, namespace, values, option_string=None):
        raise SlackArgumentParseError(parser.format_help())


class BugoutSlackArgumentParser(argparse.ArgumentParser):
    """
    Parser for CLI invocations via Slack
    """

    def error(self, message):
        message_with_usage = f"{self.format_usage()}\n{message}"
        raise SlackArgumentParseError(message_with_usage)

    def register(self, registry_name, value, object):
        registry = self._registries.setdefault(registry_name, {})
        if value == "help":
            registry[value] = CustomHelpAction
        else:
            registry[value] = object


def generate_bugout_parser() -> BugoutSlackArgumentParser:
    logger.info("Generating Bugout Slack argument parser")

    bugout_description = textwrap.dedent(
        """\
        Bugout: The Search Engine for Programmers

        Welcome to Bugout. You got here by sending a message to @bugout. @bugout helps you execute Bugout search queries directly from your Slack workspace.

        @bugout is a command-line tool with Slack as its command line. Everything you know about CLIs applies.

        Try a web search:
            $ @bugout search web how to exit vim

        If you have any questions or comments, please reach out to Neeraj, the creator of Bugout, at neeraj@simiotics.com.
        """
    )
    parser = BugoutSlackArgumentParser(
        prog="@bugout",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=bugout_description,
    )

    parser.add_argument(
        "-n",
        "--nothread",
        action="store_true",
        help="Set this flag if you do not want @bugout to use threads",
    )
    subparsers = parser.add_subparsers(title="Commands", dest="command")

    search_parser = subparsers.add_parser(
        "search", description="Perform a Bugout search against an available index"
    )
    search_parser.add_argument(
        "index",
        help="Name of index to search against (view available indices with `@bugout indices list`)",
    )
    search_parser.add_argument(
        "-b",
        "--browser",
        action="store_true",
        help=(
            "Set this flag if you would like @bugout to give you a link to view your search results"
            " in your browser"
        ),
    )
    search_parser.add_argument("query", nargs="+", help="Bugout search query")

    indices_parser = subparsers.add_parser(
        "indices", description="Information about the available indices"
    )
    slack_indices.populate_indices_parser(indices_parser)

    admin_parser = subparsers.add_parser(
        "admin", description="Administrative actions you can take with Bugout"
    )
    slack_admin.populate_admin_parser(admin_parser)

    return parser


async def search_blocks_modifier(
    db_session: Session,
    blocks: List[Dict[str, Any]],
    args: argparse.Namespace,
    team_id: str,
    user_id: str,
    bot_installation: SlackOAuthEvent,
    channel_id: Optional[str] = None,
):
    """
    Modifies Slack message blocks array to present appropriate output back to Slack users on a
    Bugout search.
    """
    query_string = " ".join(args.query)
    query_string_urlencoded = urllib.parse.quote_plus(query_string)
    client_id = f"slack-{team_id}-{user_id}"

    bugout_web_url = os.environ.get("BUGOUT_WEB_URL")
    if bugout_web_url is not None:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{bugout_web_url}/?clientID={client_id}&q={query_string_urlencoded}&auto=search|View results in your browser>",
                },
            }
        )
    elif args.browser:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "Your @bugout backend is not configured to connect to a Bugout "
                        f"web instance.\nContact <@{bot_installation.user_id}> to fix "
                        "this problem.",
                    ),
                },
            }
        )

    if not args.browser:
        available_indices = slack_indices.get_installation_indices(
            db_session, bot_installation
        )
        available_index_mapping = {
            available_index.index_name: available_index
            for available_index in available_indices
        }

        blocks.append({"type": "divider"})

        if args.index not in available_index_mapping:
            return blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"There is no available index named {args.index}. Choose from one of: "
                            f"{', '.join(available_index_mapping)}"
                        ),
                    },
                }
            )

        specified_index = available_index_mapping[args.index]
        headers: Dict[str, str] = {}
        if specified_index.use_bugout_client_id:
            # TODO(neeraj): Change this to BUGOUT_CLIENT_ID_HEADER once you've updated parasite and
            # usage backends to live in Spire.
            headers[BUGOUT_CLIENT_ID_HEADER] = client_id

        if specified_index.use_bugout_auth:
            try:
                bugout_user = get_bugout_user(
                    db_session,
                    bot_installation.id,
                    throw_on=Existence.DoesNotExist,
                )
            except BugoutUserNotFound:
                return blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"Index ({specified_index.index_name}) requires your @bugout "
                                "installation to be authenticated. Ask your @bugout administrator "
                                f"(<@{bot_installation.authed_user_id}>) to authenticate using: "
                                "`@bugout admin register` or `@bugout admin login`."
                            ),
                        },
                    }
                )

            bugout_user = cast(SlackBugoutUser, bugout_user)
            headers["Authorization"] = f"Bearer {bugout_user.bugout_access_token}"

        logger.info(f"Executing search against: {specified_index.index_url}")
        r = requests.get(
            specified_index.index_url,
            params={"q": query_string},
            headers=headers,
            timeout=5,
        )
        r.raise_for_status()
        bugout_response = r.json()
        results = bugout_response.get("results", [])
        num_results = len(results)

        if not results:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "Sorry, I found no results for your query.",
                    },
                }
            )

        # TODO(neeraj): This is the quick and hacky solution to different result formats from
        # different search engines. Find a more elegant solution to this SOON.
        if args.index == "journal":
            for i, result in enumerate(results):
                entry_number = i + 1
                rendered_result = (
                    f"*Title:* {result['title']}\n"
                    f"*Tags:* {', '.join(result['tags'])}\n"
                    f"{result['content']}"
                )
                if len(rendered_result) > SLACK_MAX_BLOCK_LENGTH:
                    rendered_result = (
                        rendered_result[
                            : max(
                                0,
                                SLACK_MAX_BLOCK_LENGTH
                                - len(SLACK_MESSAGE_CONTINUATION),
                            )
                        ]
                        + SLACK_MESSAGE_CONTINUATION
                    )
                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": rendered_result},
                    }
                )
                if entry_number < num_results:
                    blocks.append({"type": "divider"})
        else:
            html_to_text = HTMLToText()

            for i, result in enumerate(results):
                entry_number = i + 1
                result_url = result.get("url", "")
                raw_result_name = result.get("name", "")
                raw_result_snippet = result.get("snippet", "")

                html_to_text.reset()
                html_to_text.feed(raw_result_name)
                html_to_text.close()
                result_name = html_to_text.generate()

                html_to_text.reset()
                html_to_text.feed(raw_result_snippet)
                html_to_text.close()
                result_snippet = html_to_text.generate()

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{result_url}>\n{result_name}\n```{result_snippet}```",
                        },
                    }
                )
                if entry_number < num_results:
                    blocks.append({"type": "divider"})


async def handle_mention(
    team_id: str,
    user_id: str,
    channel_id: str,
    text: str,
    thread_ts: Optional[str],
    bugout_parser: BugoutSlackArgumentParser,
    spire_api_url: str,
) -> None:
    """
    Handles a mention of bugout by:
    1. Checking that it is authorized to respond with a search (if not, it will post a friendly
       message in slack)
    2. Extracting the @bugout command from the given text.
    3. Handling the @bugout command
    4. Responding to the message with an explicit mention of the user with the given ID (if
       thread_ts is specified, responds in that thread).
    """
    with db.yield_connection_from_env_ctx() as db_session:
        query = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        )

        bot_installation: Optional[SlackOAuthEvent] = query.first()
        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        if user_id == bot_installation.bot_user_id:
            return None

        lines = text.split("\n")
        invocations: List[List[str]] = []
        for line in lines:
            raw_tokens = line.split()
            tokens = [parse_raw_text(raw_token) for raw_token in raw_tokens]
            bot_mention_indices: List[int] = [
                index
                for index, token in enumerate(tokens)
                if token.token_type == SlackTextTokenType.USER
                and token.token == bot_installation.bot_user_id
            ]
            # On each line, only process the final mention as issuing a command to the Slackbot
            # This allows users to discuss the behaviour of the Slackbot and issue a command on the
            # same line.
            if len(bot_mention_indices) > 0:
                raw_args: List[str] = [
                    token.raw for token in tokens[bot_mention_indices[-1] + 1 :]
                ]
                invocations.append(raw_args)

        for invocation in invocations:
            invocation_text = "@bugout " + " ".join(invocation)
            blocks: List[Dict[str, Any]] = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Bugout",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Query:\n```{invocation_text}```",
                    },
                },
                {"type": "divider"},
            ]
            payload = {
                "token": bot_installation.bot_access_token,
                "text": "Bugout response",
                "channel": channel_id,
            }

            proceed = True
            try:
                args = bugout_parser.parse_args(invocation)
            except SlackArgumentParseError as e:
                proceed = False
                if thread_ts:
                    payload["thread_ts"] = thread_ts

                blocks.append(
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"```{str(e)}```"},
                    }
                )

            if proceed:
                if thread_ts and (not args.nothread):
                    payload["thread_ts"] = thread_ts

                if args.command is None:
                    blocks.append(
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"```{bugout_parser.format_help()}```",
                            },
                        }
                    )
                elif args.command == "indices":
                    slack_indices.indices_blocks_modifier(
                        db_session,
                        blocks,
                        args,
                        team_id,
                        user_id,
                        channel_id,
                        bot_installation,
                        spire_api_url,
                    )
                elif args.command == "admin":
                    try:
                        await slack_admin.admin_handler(
                            blocks,
                            args,
                            team_id,
                            user_id,
                            channel_id,
                            spire_api_url,
                            bot_installation,
                        )
                    except Exception as e:
                        logger.error(f"ERROR processing admin command -- {str(e)}")
                        blocks.append(
                            {
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": "Something went wrong handling your request. I am very sorry.",
                                },
                            }
                        )
                elif args.command == "search":
                    await search_blocks_modifier(
                        db_session,
                        blocks,
                        args,
                        team_id,
                        user_id,
                        bot_installation,
                        channel_id,
                    )

            payload["blocks"] = json.dumps(blocks)
            responded = True
            try:
                r = requests.post(
                    "https://api.slack.com/api/chat.postMessage",
                    data=payload,
                    timeout=3,
                )
                r.raise_for_status()
            except requests.HTTPError as e:
                responded = False

            slack_response = r.json()
            if not slack_response.get("ok"):
                if slack_response.get("error"):
                    logger.error(
                        f"Error return response to slack {slack_response.get('error')}."
                    )
                responded = False

            slack_mention = SlackMention(
                slack_oauth_event_id=bot_installation.id,
                team_id=team_id,
                user_id=user_id,
                channel_id=channel_id,
                invocation=invocation_text,
                thread_ts=thread_ts,
                responded=responded,
            )
            db_session.add(slack_mention)

        db_session.commit()
