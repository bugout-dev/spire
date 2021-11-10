"""
Processing github webhooks depends on envent type and action.
"""
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union
import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import actions
from . import calls
from . import checks
from .models import GitHubOAuthEvent, GitHubRepo
from ..db import yield_connection_from_env_ctx
from ..utils.settings import GITHUB_BOT_USERNAME

logger = logging.getLogger(__name__)


async def bot_installation_handler(
    db_session: Session,
    response_body: Dict[str, Any],
    create_installation: bool = False,
) -> GitHubOAuthEvent:
    """
    Get bot_installation for webhook call, if doesn't exist create new one when
    provided argument create with True value.
    """
    installation_response = response_body.get("installation", {})
    github_installation_id = installation_response.get("id", int())
    installation_url = installation_response.get("account", {}).get("html_url", "")
    account = installation_response.get("account", {})
    account_id = account.get("id", int())

    query = db_session.query(GitHubOAuthEvent).filter(
        or_(
            GitHubOAuthEvent.github_installation_id == github_installation_id,
            GitHubOAuthEvent.github_account_id == account_id,
        )
    )
    bot_installation = query.one_or_none()
    if bot_installation is None:
        if create_installation is True:
            new_bot_installation = GitHubOAuthEvent(
                github_account_id=account_id,
                github_installation_id=github_installation_id,
                github_installation_url=installation_url,
            )
            db_session.add(new_bot_installation)
            db_session.commit()
            bot_installation = query.first()
        else:
            raise actions.InstallationNotFound(
                f"Installation not found for {installation_url}"
            )
    return bot_installation


async def github_installation_created(response_body: Dict[str, Any]) -> None:
    """
    Handle new installations of GitHub Bugout Bot and re-installations.
    Automatically generate user, group and journal via authorizing workflow.
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(
                db_session, response_body, create_installation=True
            )
            if bot_installation.deleted == True:
                db_session.query(GitHubOAuthEvent).filter(
                    GitHubOAuthEvent.id == bot_installation.id
                ).update(
                    {
                        GitHubOAuthEvent.github_installation_id: github_installation_id,
                        GitHubOAuthEvent.deleted: False,
                    }
                )
                db_session.commit()

            actions.authorize_bot_installation(db_session, bot_installation)
        except Exception as e:
            logger.error(repr(e))
            raise actions.InstallationNotFound(
                f"Error due installaion creation for github_installation_id: {github_installation_id}"
            )


async def github_installation_deleted(response_body: Dict[str, Any]) -> None:
    """
    Handling removal of a GitHub Bugout Bot from repository.
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(db_session, response_body)
            await actions.handle_app_uninstall(db_session, bot_installation)
        except Exception as e:
            logger.error(repr(e))
            logger.error(
                f"Error deleting GitHub installation of github_installation_id: {github_installation_id}"
            )


async def github_process_repo(
    db_session,
    response_body: Dict[str, Any],
    event_id: uuid.UUID,
) -> GitHubRepo:
    """
    Check if repo does not exists, it creates new one for bot_installation.
    """
    pull_request_obj = response_body.get("pull_request", {})
    github_repo_id = pull_request_obj.get("head").get("repo").get("id")
    repo = await actions.get_repo(
        db_session, github_repo_id=github_repo_id, event_id=event_id
    )
    if repo is None:
        github_repo_name = pull_request_obj.get("head").get("repo").get("name")
        github_repo_url = pull_request_obj.get("head").get("repo").get("html_url")
        github_repo_private = pull_request_obj.get("head").get("repo").get("private")
        github_repo_default_branch = (
            pull_request_obj.get("head").get("repo").get("default_branch")
        )

        repo = await actions.add_repo(
            db_session,
            event_id,
            github_repo_id,
            github_repo_name,
            github_repo_url,
            github_repo_private,
            github_repo_default_branch,
        )
        logger.info(f"New repo was added for bot_installation: {event_id}")

    return repo


async def github_pull_request_opened(response_body: Dict[str, Any]) -> None:
    """
    Process opened and reopened Pull Request.
    To check draft status use: pull_request_obj.get("draft") == False/True

    Docs: https://docs.github.com/en/free-pro-team@latest/developers/apps/identifying-and-authorizing-users-for-github-apps#handling-a-revoked-github-app-authorization
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    pull_request_obj = response_body.get("pull_request", {})
    comments_url = pull_request_obj.get("comments_url")
    terminal_hash = pull_request_obj.get("head").get("sha")
    branch_name = pull_request_obj.get("head").get("ref")

    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(db_session, response_body)
            repo = await github_process_repo(
                db_session, response_body, bot_installation.id
            )
            issue_pr = await actions.add_issue_pr(
                db_session=db_session,
                repo_id=repo.id,
                event_id=bot_installation.id,
                comments_url=comments_url,
                terminal_hash=terminal_hash,
                branch=branch_name,
            )
            await actions.create_check(db_session, bot_installation, repo, issue_pr)

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

        except Exception as e:
            logger.error(repr(e))
            logger.error(
                f"Error due opening new pull request for github_installation_id: {github_installation_id}"
            )


async def github_pull_request_synchronize(response_body: Dict[str, Any]) -> None:
    """
    Handle additional commit in GitHub Pull Request.
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    pull_request_obj = response_body.get("pull_request", {})
    comments_url = pull_request_obj.get("comments_url")
    terminal_hash = pull_request_obj.get("head").get("sha")

    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(db_session, response_body)
            repo = await github_process_repo(
                db_session, response_body, bot_installation.id
            )
            issue_pr = await actions.update_issue_pr(
                db_session, repo.id, comments_url, terminal_hash
            )
            await checks.regenerate_check(db_session, bot_installation, repo, issue_pr)

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
        except Exception as e:
            logger.error(repr(e))
            logger.error(
                f"Error processing new commit in pull request for github_installation_id: {github_installation_id}"
            )


async def github_pull_request_closed(response_body: Dict[str, Any]) -> None:
    """
    Process close action for GitHub Pull Request.
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    pull_request_obj = response_body.get("pull_request", {})
    comments_url = pull_request_obj.get("comments_url")

    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(db_session, response_body)
            repo = await github_process_repo(
                db_session, response_body, bot_installation.id
            )
            await actions.delete_issue_pr(db_session, repo.id, comments_url)
        except Exception as e:
            logger.error(repr(e))
            logger.error(
                f"Error due closing pull request for github_installation_id: {github_installation_id}"
            )


async def github_check_run(response_body: Dict[str, Any]) -> None:
    """
    GitHub handler of checks from Pull Requests and Issues.
    """
    github_installation_id = response_body.get("installation", {}).get("id", int())
    check_run = response_body.get("check_run", {})
    check_name = check_run.get("name", "")
    check_id = str(check_run.get("id", ""))
    check_status = check_run.get("status", "")
    check_conclusion = check_run.get("conclusion", "")

    with yield_connection_from_env_ctx() as db_session:
        try:
            bot_installation = await bot_installation_handler(db_session, response_body)
            org_name = bot_installation.github_installation_url.rstrip("/").split("/")[
                -1
            ]
            if check_name == GITHUB_BOT_USERNAME and check_status != "completed":
                logger.info(
                    f"Triggered check_run: {check_name} with id: {check_id}, "
                    f"status: {check_status}, conclusion: {check_conclusion}"
                )

                check = await actions.get_check(db_session, check_id=check_id)
                repo = await actions.get_repo(db_session, repo_id=check.repo_id)
                if repo is None:
                    raise actions.RepoNotFound(
                        f"Repository did not found for installation: {bot_installation.id}"
                    )

                if check.github_status is None:
                    # GitHub send Check's statuses and we need to handle
                    # which one from us, which one we should leave and etc.
                    await calls.update_check_run_request(
                        check_id=check_id,
                        repo_name=repo.github_repo_name,
                        org_name=org_name,
                        token=bot_installation.access_token,
                        check_name=GITHUB_BOT_USERNAME,
                        status="completed",
                        conclusion="success",
                    )
        except Exception as e:
            logger.error(repr(e))
            logger.error(
                f"Error updating check for github_installation_id: {github_installation_id}"
            )


# Make sure that keys of this dict used as github_event_type and action fields where necessary.
GITHUB_SELECTORS: Dict[
    str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Union[None, Dict[str, Any]]]]
] = {
    "installation_created": github_installation_created,
    "installation_deleted": github_installation_deleted,
    "pull_request_opened": github_pull_request_opened,
    "pull_request_reopened": github_pull_request_opened,
    "pull_request_closed": github_pull_request_closed,
    "pull_request_synchronize": github_pull_request_synchronize,
    "check_run": github_check_run,
}
