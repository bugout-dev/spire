"""
Handlers for Bugout GitHub CLI
"""
import argparse
from dataclasses import dataclass
from enum import Enum
import json
import logging
import re
import textwrap
from typing import Any, Dict, List, Optional

from locust import render  # type: ignore
from sqlalchemy.orm import Session

from . import actions
from . import calls
from . import checks as bugout_check
from .models import GitHubOAuthEvent, GitHubIssuePR, GitHubLocust
from ..db import yield_connection_from_env_ctx
from ..utils.settings import GITHUB_BOT_USERNAME
from ..utils.bugoutargparse import BugoutGitHubArgumentParser, GitHubArgumentParseError

logger = logging.getLogger(__name__)

CHECKBOX_REGEX = re.compile("^- \[.\] ")


class GitHubTextTokenType(Enum):
    """
    Types of tokens that can be found in the text of a GitHub comment.
    """

    PLAIN = 1
    USER = 2


@dataclass
class GitHubTextToken:
    """
    A token in the text of a GitHub comment
    """

    raw: str
    token_type: GitHubTextTokenType
    token: str
    label: Optional[str] = None


def parse_raw_text(raw_token: str) -> GitHubTextToken:
    """
    Parses raw text from a GitHub comment into a GitHubTextToken object.

    Modified version of parse_raw_text() from slack/commands.py
    """
    if raw_token == "":
        return GitHubTextToken(
            raw=raw_token, token_type=GitHubTextTokenType.PLAIN, token=raw_token
        )

    symbol_signifier = raw_token[0]
    parsed_token = GitHubTextToken(
        raw=raw_token,
        token_type=GitHubTextTokenType.PLAIN,
        token=raw_token,
    )

    if symbol_signifier.startswith("@"):
        parsed_token.token_type = GitHubTextTokenType.USER
        parsed_token.token = raw_token[1:]

    return parsed_token


def generate_bugout_parser() -> BugoutGitHubArgumentParser:
    """
    Locust/BugoutCI parser generator. Handle GitHub Bot mentions.
    """
    logger.info("Generating Bugout Locust argument parser")

    bugout_description = textwrap.dedent(
        """\
        Bugout Locust: semantic layer on top of git issue_pr.
        It emits metadata describing AST-level changes to your code base between git revisions.
        """
    )
    parser = BugoutGitHubArgumentParser(
        prog=f"@{GITHUB_BOT_USERNAME}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=bugout_description,
    )

    subparsers = parser.add_subparsers(title="Commands", dest="command")

    summary_parser = subparsers.add_parser(
        "summarize", description="Locust summary report"
    )
    populate_locust_parser(summary_parser)

    check_parser = subparsers.add_parser(
        "check", description="GitHub Check actions you can take with Bugout"
    )
    bugout_check.populate_check_parser(check_parser)

    return parser


def populate_locust_parser(parser: argparse.ArgumentParser) -> None:
    """
    Populates an argparse ArgumentParser with summary directives.
    """
    parser.set_defaults(func=parser.format_help)
    subparsers = parser.add_subparsers(
        title="Bugout Locust summary commands", dest="summary_command"
    )


async def locust_handler(
    db_session: Session,
    args: argparse.Namespace,
    issue_pr: GitHubIssuePR,
    bot_installation: GitHubOAuthEvent,
    comments_url: str,
) -> str:
    """
    Process summary commands.
    """
    query = db_session.query(GitHubLocust).filter(
        GitHubLocust.issue_pr_id == issue_pr.id
    )
    summary_query = query.filter(GitHubLocust.terminal_hash == issue_pr.terminal_hash)
    summary = summary_query.one_or_none()
    if summary is None:
        raise actions.SummaryNotFound(
            f"No locust summaries for this Pull Request/Issue with {comments_url}"
        )

    # Get previous comments (if response_url not None, it means comment exists on GitHub)
    previous_comments_query = query.filter(GitHubLocust.response_url.isnot(None))
    previous_comments_lst = previous_comments_query.all()
    for previous_comment in previous_comments_lst:
        await calls.remove_comment(
            comment_url=previous_comment.response_url,
            token=bot_installation.access_token,
        )
        if previous_comment != summary:
            previous_comments_query.update(
                {
                    GitHubLocust.response_url: None,
                    GitHubLocust.commented_at: None,
                }
            )

    # Extract summary content
    summary_content = await actions.get_summary_content(
        summary_id=summary.id, summary_type="locust"
    )
    locust_content_html = render.renderers["github"](json.loads(summary_content))

    github_response = await calls.post_comment(
        comments_url, bot_installation.access_token, locust_content_html
    )

    summary_query.update(
        {
            GitHubLocust.response_url: github_response.get("url"),
            GitHubLocust.commented_at: github_response.get("created_at"),
        }
    )

    db_session.commit()

    logger.info(f"Locust report sent to comments_url: {comments_url}")

    return str(locust_content_html)


async def handle_mention(
    installation_id: str,
    response_body: Dict[str, Any],
    bugout_parser: BugoutGitHubArgumentParser,
) -> None:
    """
    Handles a mention of bugout by:
    1. Extracting the @bugout-dev command from the given text;
    2. Handling the @bugout-dev command;
    3. According to command it returns Locust report or process
    GitHub Checks workflow;
    4. Responding to the message.
    """
    github_comment = response_body.get("comment", {})
    comment_val = str(github_comment.get("body", ""))
    github_repo_id = int(response_body.get("repository", {}).get("id"))
    comments_url = response_body.get("issue", {}).get("comments_url", "")

    with yield_connection_from_env_ctx() as db_session:
        query = db_session.query(GitHubOAuthEvent).filter(
            GitHubOAuthEvent.github_installation_id == installation_id
        )
        bot_installation: Optional[GitHubOAuthEvent] = query.first()
        if bot_installation is None:
            logger.error(
                f"Did not find active installation of @bugout for installation_id: {installation_id}"
            )
            return

        try:
            issue_pr = await actions.get_issue_pr(db_session, comments_url=comments_url)
        except Exception as e:
            logger.error("Did not find issue_pr")
            return
        repo = await actions.get_repo(
            db_session, github_repo_id=github_repo_id, event_id=bot_installation.id
        )
        if repo is None:
            logger.error("Did not find repository in database")
            return

        lines = comment_val.split("\n")
        invocations: List[List[str]] = []

        for line in lines:
            raw_tokens = line.split()
            tokens = [parse_raw_text(raw_token) for raw_token in raw_tokens]
            bot_mention_indices: List[int] = [
                index
                for index, token in enumerate(tokens)
                if token.token_type == GitHubTextTokenType.USER
                and token.token == GITHUB_BOT_USERNAME
            ]
            # On each line, only process the final mention as issuing a command to the GitHub
            # This allows users to discuss the behaviour of the Slackbot and issue a command on the
            # same line.
            if len(bot_mention_indices) > 0:
                raw_args: List[str] = [
                    token.raw for token in tokens[bot_mention_indices[-1] + 1 :]
                ]
                invocations.append(raw_args)

        for invocation in invocations:
            proceed = True
            try:
                args = bugout_parser.parse_args(invocation)
            except GitHubArgumentParseError as e:
                proceed = False
                logger.info("No recognizable commands found")

            if not proceed:
                continue

            if args.command == "check":
                comment_user = github_comment.get("user", {}).get("login", "")

                checkbox_lines = list(filter(CHECKBOX_REGEX.match, lines))
                checkbox_status = True if len(checkbox_lines) > 0 else False

                try:
                    check = await actions.get_check(db_session, issue_pr_id=issue_pr.id)

                    await bugout_check.checkbox_checker(
                        db_session=db_session,
                        args=args,
                        lines=lines,
                        check=check,
                        bot_installation=bot_installation,
                        comment_user=comment_user,
                        checkbox=checkbox_status,
                    )
                except Exception as e:
                    logger.error(f"ERROR processing check command -- {str(e)}")

            if args.command == "summarize":
                # Extract last one summary and delete previous reports
                try:

                    await locust_handler(
                        db_session=db_session,
                        args=args,
                        issue_pr=issue_pr,
                        bot_installation=bot_installation,
                        comments_url=comments_url,
                    )
                except Exception as e:
                    logger.error(f"Error due sending locust report -- {str(e)}")

        # Generate entry summary and publish to journal
        if github_comment.get("user").get("type") != "Bot":
            summary_str, summary_obj = await actions.process_summary(
                db_session, bot_installation, repo, issue_pr
            )
            entry_id = await actions.publish_summary_as_entry(
                db_session=db_session,
                bot_installation_id=bot_installation.id,
                issue_pr=issue_pr,
                content=summary_str,
                context_id="summary",
                summary=summary_obj,
            )
            if issue_pr.entry_id != entry_id:
                await actions.update_issue_pr(
                    db_session,
                    repo.id,
                    comments_url,
                    entry_id=entry_id,
                )
