import argparse
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import actions
from . import calls
from .models import (
    GitHubOAuthEvent,
    GitHubRepo,
    GitHubIssuePR,
    GitHubCheck,
)
from ..utils.settings import GITHUB_BOT_USERNAME
from ..utils.bugoutargparse import BugoutGitHubArgumentParser

logger = logging.getLogger(__name__)

COMMAND_REQUIRE = "require"
COMMAND_ACCEPT = "accept"


def populate_check_parser(parser: argparse.ArgumentParser) -> None:
    """
    Populates an argparse ArgumentParser with check directives.
    """
    parser.set_defaults(func=parser.format_help)
    subparsers = parser.add_subparsers(
        title="Bugout CI Check commands", dest="check_command"
    )

    require_parser = subparsers.add_parser(
        COMMAND_REQUIRE,
        description="Blocks the branch's check until the requested action is performed and accept",
    )
    require_parser.add_argument(
        "note", nargs="*", help="Name or short description of the check block"
    )

    accept_parser = subparsers.add_parser(
        COMMAND_ACCEPT,
        description="Unblocks the branch's check",
    )
    accept_parser.add_argument(
        "note", nargs="*", help="Name or short description of the check block"
    )


async def regenerate_check(
    db_session: Session,
    bot_installation: GitHubOAuthEvent,
    repo: GitHubRepo,
    issue_pr: GitHubIssuePR,
) -> None:
    """
    During posting new commits (NOT comments) GitHub removes old checks and we should
    regenerate new check with old check_notes and same conclusion(Failed or Succes).
    Also, we regenerate GitHub Check Detail page with current status.
    """
    query = db_session.query(GitHubCheck).filter(GitHubCheck.issue_pr_id == issue_pr.id)
    check = query.first()

    # Create new GitHub Check
    check_response = await calls.create_check_request(
        bot_installation.github_installation_url,
        repo.github_repo_name,
        bot_installation.access_token,
        GITHUB_BOT_USERNAME,
        issue_pr.terminal_hash,
    )
    query.update(
        {
            GitHubCheck.github_check_id: check_response.get("id"),
        }
    )
    db_session.commit()

    failed_notes = await actions.get_check_notes(db_session, check.id, False)
    accepted_notes = await actions.get_check_notes(db_session, check.id, True)

    summary = await actions.render_check_details(accepted_notes, failed_notes)

    org_name = bot_installation.github_installation_url.rstrip("/").split("/")[-1]

    # Update status of newly created Check
    await calls.update_check_run_request(
        check_id=check.github_check_id,
        repo_name=repo.github_repo_name,
        org_name=org_name,
        token=bot_installation.access_token,
        check_name=GITHUB_BOT_USERNAME,
        status="completed",
        conclusion=check.github_conclusion,
        summary=summary,
    )

    await actions.update_check(db_session, check, check.github_conclusion)


async def check_handler(
    db_session: Session,
    args: argparse.Namespace,
    check: GitHubCheck,
    bot_installation: GitHubOAuthEvent,
    comment_user: str,
) -> str:
    """
    Process Check CI commands is obtained from GitHub Pull Request comments.
    """
    note_str = " ".join(args.note)

    existing_notes = await actions.get_check_notes(db_session, check.id, note=note_str)

    if args.check_command == COMMAND_REQUIRE:
        conclusion = "failure"
        if len(existing_notes) == 0:
            await actions.add_check_note(db_session, check.id, note_str, comment_user)
        else:
            await actions.update_check_notes(db_session, check.id, note_str, False)

    elif args.check_command == COMMAND_ACCEPT:
        conclusion = "success"
        await actions.update_check_notes(
            db_session, check.id, note_str, True, comment_user
        )

    failed_notes = await actions.get_check_notes(db_session, check.id, False)
    accepted_notes = await actions.get_check_notes(db_session, check.id, True)

    # Depends of failed_notes len we let GitHub know Checks conclusion
    if len(failed_notes) == 0:
        conclusion = "success"
    else:
        conclusion = "failure"

    summary = await actions.render_check_details(accepted_notes, failed_notes)

    org_name = bot_installation.github_installation_url.rstrip("/").split("/")[-1]
    repo = await actions.get_repo(db_session, repo_id=check.repo_id)
    if repo is None:
        raise actions.RepoNotFound("Repository not found")

    await calls.update_check_run_request(
        check_id=check.github_check_id,
        repo_name=repo.github_repo_name,
        org_name=org_name,
        token=bot_installation.access_token,
        check_name=GITHUB_BOT_USERNAME,
        status="completed",
        conclusion=conclusion,
        summary=summary,
    )

    await actions.update_check(db_session, check, conclusion)

    return summary


async def checkbox_checker(
    db_session: Session,
    args: argparse.Namespace,
    lines: List[str],
    check: GitHubCheck,
    bot_installation: GitHubOAuthEvent,
    comment_user: str,
    checkbox: bool = False,
) -> str:
    """
    Process GitHub checkboxes in markdown comment.
    If checkboxes inside comment we parse this lines and
    generate our own Namespace for argparse and call with it
    check_handler.

    If we recieve simple CLI command, just call it with args.
    """
    if checkbox:
        summary = ""
        for raw_line in lines:
            line = raw_line.strip()
            note = ""
            check_command = ""
            manual_args = None

            if line.startswith("- [x] "):
                note = line.split("- [x] ")[-1]
                check_command = COMMAND_ACCEPT
            elif line.startswith("- [ ] "):
                note = line.split("- [ ] ")[-1]
                check_command = COMMAND_REQUIRE

            if note:
                manual_args = argparse.Namespace(
                    check_command=check_command,
                    command=BugoutGitHubArgumentParser,
                    note=[note],
                )
                summary = await check_handler(
                    db_session=db_session,
                    args=manual_args,
                    check=check,
                    bot_installation=bot_installation,
                    comment_user=comment_user,
                )

    # Simple CLI handler
    else:
        summary = await check_handler(
            db_session=db_session,
            args=args,
            check=check,
            bot_installation=bot_installation,
            comment_user=comment_user,
        )

    return summary
