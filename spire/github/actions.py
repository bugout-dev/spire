from datetime import datetime
import json
import logging
from typing import Any, cast, Dict, List, Optional, Tuple
import uuid

import boto3
from concurrent.futures import ThreadPoolExecutor
from locust import render  # type: ignore
from sqlalchemy.orm import Session

from . import calls
from .data import (
    LocustSummaryReport,
    EntrySummaryReport,
    EntrySummaryCommitReport,
    EntrySummaryCommentsReport,
)
from .models import (
    GitHubOAuthEvent,
    GitHubBugoutUser,
    GitHubRepo,
    GitHubIssuePR,
    GitHubCheck,
    GitHubCheckNotes,
    GitHubLocust,
    GithubIndexConfiguration,
)
from ..indices import create_team_journal_and_register_index
from ..utils.settings import (
    GITHUB_BOT_USERNAME,
    GITHUB_SUMMARY_BUCKET,
    GITHUB_SUMMARY_PREFIX,
    INSTALLATION_TOKEN,
    BOT_INSTALLATION_TOKEN_HEADER,
    SPIRE_API_URL,
    THREAD_WORKERS,
)
from ..broodusers import (
    bugout_api,
    process_group_in_journal_holders,
    Method,
    BugoutAPICallFailed,
)

logger = logging.getLogger(__name__)


class InvalidInstallationSpec(ValueError):
    """
    Raised when an invalid installation query is specified.
    """


class InvalidRepoSpec(ValueError):
    """
    Raised when an invalid repository query is specified.
    """


class InvalidIssuePRSpec(ValueError):
    """
    Raised when an invalid pull request/issue query is specified.
    """


class InvalidCheckSpec(ValueError):
    """
    Raised when an invalid check query is specified.
    """


class BugoutSecretIncorrect(ValueError):
    """
    Raised on actions that involve Bugout Secret which is incorrect.
    """


class InstallationNotFound(Exception):
    """
    Raised on actions that involve installation which are not present in the database.
    """


class RepoNotFound(Exception):
    """
    Raised on actions that involve repository which are not present in the database.
    """


class IssuePRNotFound(Exception):
    """
    Raised on actions that involve pull request/issue which are not present in the database.
    """


class SummaryNotFound(Exception):
    """
    Raised on actions that involve summary which are not present in the database.
    """


class CheckNotFound(Exception):
    """
    Raised on actions that involve check which are not present in the database.
    """


class BugoutSecretNotFound(Exception):
    """
    Raised on actions that involve Bugout Secret which is not present in the database.
    """


class S3CallFailed(Exception):
    """
    Raised when data processing at AWS S3 failed.
    """


async def add_repo(
    db_session: Session,
    event_id: uuid.UUID,
    github_repo_id: int,
    github_repo_name: str,
    github_repo_url: str,
    private: bool,
    default_branch: str,
) -> GitHubRepo:
    """
    Adds repository to database for provided organization.
    # TODO(kompotkot): Add exceptions and check existing repos
    """
    repo = GitHubRepo(
        event_id=event_id,
        github_repo_id=github_repo_id,
        github_repo_name=github_repo_name,
        github_repo_url=github_repo_url,
        private=private,
        default_branch=default_branch,
    )
    db_session.add(repo)
    db_session.commit()
    return repo


async def add_repo_list(
    db_session: Session, bot_installation: GitHubOAuthEvent
) -> None:
    """
    Add list of repositories of specified organization to database.

    # TODO(kompotkot): Trigger update organizations repositories
    # if already exist for this accuont
    """
    repos: List[Dict[str, Any]] = await calls.get_org_repos(
        bot_installation.access_token
    )
    for repo in repos:
        try:
            await add_repo(
                db_session=db_session,
                event_id=bot_installation.id,
                github_repo_id=cast(int, repo["id"]),
                github_repo_name=cast(str, repo["name"]),
                github_repo_url=cast(str, repo["url"]),
                private=cast(bool, repo["private"]),
                default_branch=cast(str, repo.get("default_branch", "")),
            )
        except Exception as e:
            logger.warning(
                f"Could not add repo {repo} for installation id: {bot_installation.id} -- {e} "
            )


async def get_repo(
    db_session: Session,
    repo_id: Optional[uuid.UUID] = None,
    github_repo_id: Optional[int] = None,
    event_id: Optional[uuid.UUID] = None,
) -> Optional[GitHubRepo]:
    """
    Returns repository according with provoded arguments.
    If repo not found, return None.
    """
    if repo_id is None and github_repo_id is None and event_id is None:
        raise InvalidRepoSpec(
            "In order to get repository repo_id or at least "
            "github_repo_id parameter should be specified"
        )

    query = db_session.query(GitHubRepo)
    if repo_id is not None:
        query = query.filter(GitHubRepo.id == repo_id)
    if github_repo_id is not None:
        query = query.filter(GitHubRepo.github_repo_id == github_repo_id)
    if event_id is not None:
        query = query.filter(GitHubRepo.event_id == event_id)

    repo = query.one_or_none()
    return repo


async def get_issue_pr(
    db_session: Session,
    issue_pr_id: Optional[uuid.UUID] = None,
    comments_url: Optional[str] = None,
    terminal_hash: Optional[str] = None,
) -> GitHubIssuePR:
    """
    Validates Bugout Secret to make sure organization has access to requested PR/Issue.
    Return Issue or Pull request from database.
    """
    if issue_pr_id is None and comments_url is None and terminal_hash is None:
        raise InvalidIssuePRSpec(
            "In order to get dif issue_pr_id, terminal_hash or at least comments_url parameter should be specified"
        )
    query = db_session.query(GitHubIssuePR)
    if issue_pr_id is not None:
        query = query.filter(GitHubIssuePR.id == issue_pr_id)
    if comments_url is not None:
        query = query.filter(GitHubIssuePR.comments_url == comments_url)
    if terminal_hash is not None:
        query = query.filter(GitHubIssuePR.terminal_hash == terminal_hash)

    issue_pr = query.one_or_none()
    if issue_pr is None:
        raise IssuePRNotFound(f"Did not find issue_pr")

    return issue_pr


async def add_issue_pr(
    db_session: Session,
    repo_id: uuid.UUID,
    event_id: uuid.UUID,
    comments_url: str,
    terminal_hash: str,
    branch: str,
) -> GitHubIssuePR:
    """
    Adds new Pull Request or Issue.
    """
    issue_pr = GitHubIssuePR(
        repo_id=repo_id,
        event_id=event_id,
        terminal_hash=terminal_hash,
        comments_url=comments_url,
        branch=branch,
    )
    db_session.add(issue_pr)
    db_session.commit()

    return issue_pr


async def update_issue_pr(
    db_session: Session,
    repo_id: uuid.UUID,
    comments_url: str,
    terminal_hash: Optional[str] = None,
    entry_id: Optional[str] = None,
    comments: Optional[Dict[str, Any]] = None,
) -> GitHubIssuePR:
    """
    Handle Pull Request or Issue hash update.

    At start we work with head hash and update head in GitHubIssuePR after each commit.
    """
    query = (
        db_session.query(GitHubIssuePR)
        .filter(GitHubIssuePR.repo_id == repo_id)
        .filter(GitHubIssuePR.comments_url == comments_url)
    )
    if terminal_hash is not None:
        query.update({GitHubIssuePR.terminal_hash: terminal_hash})
    if entry_id is not None:
        query.update({GitHubIssuePR.entry_id: entry_id})
    if comments is not None:
        query.update({GitHubIssuePR.comments: comments})
    db_session.commit()

    issue_pr = query.first()

    return issue_pr


async def delete_issue_pr(
    db_session: Session, repo_id: uuid.UUID, comments_url: str
) -> None:
    """
    Handle Pull Request or Issue deletion.
    """
    query = (
        db_session.query(GitHubIssuePR)
        .filter(GitHubIssuePR.repo_id == repo_id)
        .filter(GitHubIssuePR.comments_url == comments_url)
    )
    query.delete()
    db_session.commit()


async def get_check(
    db_session: Session,
    issue_pr_id: Optional[uuid.UUID] = None,
    check_id: Optional[str] = None,
) -> GitHubCheck:
    """
    Returns GitHub Check from database.
    """
    if check_id is None and issue_pr_id is None:
        raise InvalidCheckSpec(
            "In order to process Check Run check_id or at least issue_pr parameter should be specified"
        )

    query = db_session.query(GitHubCheck)
    if check_id is not None:
        query = query.filter(GitHubCheck.github_check_id == check_id)
    if issue_pr_id is not None:
        query = query.filter(GitHubCheck.issue_pr_id == issue_pr_id)

    check = query.one_or_none()
    if check is None:
        raise CheckNotFound(
            f"Did not find check with id: {check_id} or issue_pr_id: {issue_pr_id}"
        )

    return check


async def create_check(
    db_session: Session,
    bot_installation: GitHubOAuthEvent,
    repo: GitHubRepo,
    issue_pr: GitHubIssuePR,
) -> GitHubCheck:
    """
    Process request which creating Check at GitHub and adding it to database.

    We set github_status to None to be able mark this check as completed when
    because GitHub response us back with same check.
    """
    check_response = await calls.create_check_request(
        bot_installation.github_installation_url,
        repo.github_repo_name,
        bot_installation.access_token,
        GITHUB_BOT_USERNAME,
        issue_pr.terminal_hash,
    )
    repo_check = GitHubCheck(
        issue_pr_id=issue_pr.id,
        repo_id=repo.id,
        event_id=bot_installation.id,
        github_check_id=check_response.get("id"),
        github_check_name=GITHUB_BOT_USERNAME,
    )
    db_session.add(repo_check)
    db_session.commit()

    return repo_check


async def update_check(
    db_session: Session,
    check: GitHubCheck,
    github_conclusion: str,
    github_status: str = "completed",
    entry_id: Optional[uuid.UUID] = None,
) -> None:
    """
    Updates GitHub conclusion and status and entry_id if provided.
    """
    query = db_session.query(GitHubCheck).filter(GitHubCheck.id == check.id)
    query.update(
        {
            GitHubCheck.github_status: github_status,
            GitHubCheck.github_conclusion: github_conclusion,
        }
    )
    if entry_id is not None:
        query.update({GitHubCheck.entry_id: entry_id})

    db_session.commit()


async def get_check_notes(
    db_session: Session,
    check_id: uuid.UUID,
    accepted: Optional[bool] = None,
    note: Optional[str] = None,
) -> List[GitHubCheckNotes]:
    """
    Returns check notes according with provided field "accepted".
    """
    query = db_session.query(GitHubCheckNotes).filter(
        GitHubCheckNotes.check_id == check_id
    )
    if accepted is not None:
        query = query.filter(GitHubCheckNotes.accepted == accepted)
    if note is not None:
        query = query.filter(GitHubCheckNotes.note == note)

    check_notes = query.all()

    return check_notes


async def add_check_note(
    db_session, check_id: uuid.UUID, note: str, created_by: str
) -> GitHubCheckNotes:
    """
    Creates additional check note.
    """
    check_note = GitHubCheckNotes(check_id=check_id, note=note, created_by=created_by)
    db_session.add(check_note)
    db_session.commit()

    return check_note


async def update_check_notes(
    db_session: Session,
    check_id: uuid.UUID,
    note: str,
    accepted: bool,
    accepted_by: Optional[str] = None,
) -> None:
    """
    Updates conclusion of check note. If Check accepted,
    user (accepted_by) should be provided.
    """
    query = (
        db_session.query(GitHubCheckNotes)
        .filter(GitHubCheckNotes.check_id == check_id)
        .filter(GitHubCheckNotes.note == note)
    )
    if accepted is True:
        query.update(
            {
                GitHubCheckNotes.accepted: accepted,
                GitHubCheckNotes.accepted_by: accepted_by,
            }
        )
    else:
        query.update(
            {
                GitHubCheckNotes.accepted: accepted,
                GitHubCheckNotes.accepted_by: None,
            }
        )
    db_session.commit()


async def get_locust_summary(
    db_session: Session,
    summary_id: Optional[uuid.UUID] = None,
    issue_pr_id: Optional[uuid.UUID] = None,
    terminal_hash: Optional[str] = None,
) -> Optional[GitHubLocust]:
    """
    Returns Locust summary obj from database by provided summary_id.
    """
    query = db_session.query(GitHubLocust)

    if summary_id is not None:
        query = query.filter(GitHubLocust.id == summary_id)
    if issue_pr_id is not None and terminal_hash is not None:
        query = query.filter(
            GitHubLocust.issue_pr_id == issue_pr_id,
            GitHubLocust.terminal_hash == terminal_hash,
        )
    summary = query.one_or_none()
    return summary


async def get_summary_content(summary_id: uuid.UUID, summary_type: str) -> str:
    """
    Extract summary content from S3 by summary_id.

    Docs:
    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.get_object
    """
    result_key = f"{GITHUB_SUMMARY_PREFIX}/{summary_type}/{summary_id}.json"
    try:
        s3 = boto3.client("s3")
        s3_object = s3.get_object(Bucket=GITHUB_SUMMARY_BUCKET, Key=result_key)[
            "Body"
        ].read()
        summary_content = json.loads(s3_object)
    except Exception as e:
        logger.error(f"Error occurred due data extraction from AWS S3, error: {str(e)}")
        raise S3CallFailed("Data extraction from AWS S3 failed")

    return summary_content


async def publish_summary_as_entry(
    db_session: Session,
    bot_installation_id: uuid.UUID,
    issue_pr,
    content: Any,
    context_id: str,
    summary: EntrySummaryReport,
) -> Any:
    """
    Publish summary from locust or checks to Bugout entry.
    If entry were deleted from journal it creates new one.
    """
    repo_pr_list = issue_pr.comments_url.rstrip("/").split("/")[4:-1]
    orgranization = repo_pr_list[0]
    repository = repo_pr_list[1]
    issue_number = repo_pr_list[3]
    context_url = f"https://github.com/{'/'.join(repo_pr_list)}"
    tags = [
        orgranization,
        repository,
        issue_number,
        context_id,
        "github",
        "pull_request",
        issue_pr.branch,
        "autogenerated",
    ]
    title = f"PR #{issue_number} on {orgranization}/{repository}: {summary.title}"

    index_configuration = (
        db_session.query(GithubIndexConfiguration)
        .filter(GithubIndexConfiguration.github_oauth_event_id == bot_installation_id)
        .first()
    )
    journal_id = index_configuration.index_url.rstrip("/").split("/")[-2]
    bugout_user = (
        db_session.query(GitHubBugoutUser)
        .filter(GitHubBugoutUser.event_id == bot_installation_id)
        .first()
    )
    try:
        entry = bugout_api.get_entry(
            token=bugout_user.bugout_access_token,
            journal_id=journal_id,
            entry_id=issue_pr.entry_id,
        )
        bugout_api.update_entry_content(
            token=bugout_user.bugout_access_token,
            journal_id=journal_id,
            entry_id=entry.id,
            title=title,
            content=content,
        )
    except Exception as e:
        logger.error(
            f"Failed receiving entry with id: {issue_pr.entry_id}, creating new one"
        )
        entry = bugout_api.create_entry(
            token=bugout_user.bugout_access_token,
            journal_id=journal_id,
            title=title,
            content=content,
            tags=tags,
            context_url=context_url,
            context_id=context_id,
            context_type="github",
        )
    logger.info(
        f"GitHub summary stored as entry with id: {issue_pr.entry_id} to journal with id: {journal_id}"
    )
    return entry.id


async def store_locust(
    db_session: Session, summary: LocustSummaryReport, issue_pr: GitHubIssuePR
) -> None:
    """
    Store Locust summary at journal entry, database and AWS S3.
    """
    if GITHUB_SUMMARY_BUCKET is None:
        logger.warning(
            "AWS_S3_JOURNAL_SEARCH_RESULTS_BUCKET environment variable not defined, skipping storage of search results"
        )
        raise S3CallFailed("Write to AWS S3 failed")

    summary_id = uuid.uuid4()
    s3_url = f"s3://{GITHUB_SUMMARY_BUCKET}/{GITHUB_SUMMARY_PREFIX}/locust/{str(summary_id)}.json"

    # Store in Postgres
    summary_obj = GitHubLocust(
        id=summary_id,
        issue_pr_id=issue_pr.id,
        s3_uri=s3_url,
        terminal_hash=summary.terminal_hash,
    )
    db_session.add(summary_obj)
    db_session.commit()

    # Store in S3
    result_bytes = json.dumps(summary.json()).encode("utf-8")
    result_key = f"{GITHUB_SUMMARY_PREFIX}/locust/{summary_id}.json"
    s3 = boto3.client("s3")
    s3.put_object(
        Body=result_bytes,
        Bucket=GITHUB_SUMMARY_BUCKET,
        Key=result_key,
        ContentType="application/json",
        Metadata={"type": "locust"},
    )
    logger.info(
        f"Summary stored at s3://{GITHUB_SUMMARY_BUCKET}/{GITHUB_SUMMARY_PREFIX}/locust/{str(summary_id)}.json"
    )


def authorize_bot_installation(db_session: Session, bot_installation: GitHubOAuthEvent):
    """
    Authorize a bot installation, checks if current_github_bugout_user exists then return it.

    If the user does not exist, a new one is created with credentials:
    username: <org name>-<org account id>
    email: <org name>-<org account id>@bugout.dev
    password: randomly generated uuid4

    User creates group and add group in journal holders.
    """
    bugout_user_query = db_session.query(GitHubBugoutUser).filter(
        GitHubBugoutUser.event_id == bot_installation.id
    )
    current_github_bugout_user = bugout_user_query.one_or_none()

    org_name = bot_installation.github_installation_url.rstrip("/").split("/")[-1]

    if not current_github_bugout_user:
        # Create new Bugout user and generate token with Brood API
        generated_password: str = str(uuid.uuid4())

        username = f"{org_name}-{bot_installation.github_account_id}"
        email = f"{org_name}-{bot_installation.github_account_id}@bugout.dev"

        headers = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}
        bugout_user = bugout_api.create_user(
            username, email, generated_password, headers=headers
        )
        bugout_user_token = bugout_api.create_token(username, generated_password)

        github_bugout_user = GitHubBugoutUser(
            event_id=bot_installation.id,
            bugout_user_id=bugout_user.id,
            bugout_access_token=bugout_user_token.id,
        )
        db_session.add(github_bugout_user)
    else:
        # If connection between GitHub Organization and github_installation user already exists,
        # if bot was installed before - use those GitHubBugoutUser.
        github_bugout_user = current_github_bugout_user

    db_session.commit()

    # Create Brood group
    group_name = f"GitHub team: {org_name}-{bot_installation.github_account_id}"
    group = bugout_api.create_group(github_bugout_user.bugout_access_token, group_name)

    bugout_user_query.update({GitHubBugoutUser.bugout_group_id: group.id})
    db_session.commit()
    logger.info(f"Created group with id: {group.id} for github team.")

    # Generate journal and configure index
    journal_api_url = f"{SPIRE_API_URL.rstrip('/')}/journals/"
    index_configuration = create_team_journal_and_register_index(
        db_session, journal_api_url, bot_installation
    )
    journal_id = index_configuration.index_url.rstrip("/").split("/")[-2]
    logger.info(f"Created journal with id: {journal_id} for github team.")

    process_group_in_journal_holders(
        Method.post,
        journal_id,
        journal_api_url,
        github_bugout_user.bugout_access_token,
        group.id,
        bot_installation,
    )


async def handle_app_uninstall(
    db_session: Session, bot_installation: GitHubOAuthEvent
) -> None:
    """
    Handles uninstall of app from GitHub organization by marking GitHubOAuthEvent as
    deleted, removing groups and it's ids from journal permissions.

    BroodUser, GitHubBugoutUser, GithubIndexConfiguration and Journal is saved.
    """
    if bot_installation is None:
        raise InvalidInstallationSpec(
            "In order to uninstall installation bot_installation should be exist"
        )

    db_session.query(GitHubOAuthEvent).filter(
        GitHubOAuthEvent.id == bot_installation.id
    ).update({GitHubOAuthEvent.deleted: True})

    # Clear repos
    # TODO(kompotkot): Rewrite it to save repos
    repos = (
        db_session.query(GitHubRepo)
        .filter(GitHubRepo.event_id == bot_installation.id)
        .all()
    )
    for repo in repos:
        db_session.delete(repo)

    db_session.commit()

    # Clear installation group
    installation_user_query = db_session.query(GitHubBugoutUser).filter(
        GitHubBugoutUser.event_id == bot_installation.id
    )
    installation_user = installation_user_query.one()

    bugout_api.delete_group(
        installation_user.bugout_access_token,
        installation_user.bugout_group_id,
    )
    installation_user_query.update({GitHubBugoutUser.bugout_group_id: None})
    db_session.commit()


async def process_secret(
    db_session: Session, bugout_secret: str, bot_installation_id: uuid.UUID
) -> None:
    """
    Validates Bugout Secret to make sure organization has access to requested PR/Issue.
    Return Issue or Pull request from database.
    """
    if not bugout_secret:
        raise BugoutSecretIncorrect("Bugout Secret is incorrect")
    try:
        user = bugout_api.get_user(bugout_secret)
    except Exception as e:
        logger.info(f"Provided incorrect Bugout Secret")
        raise BugoutSecretIncorrect(
            f"Did not find user with provided token as Bugout Secret"
        )

    installation_user = (
        db_session.query(GitHubBugoutUser)
        .filter(GitHubBugoutUser.event_id == bot_installation_id)
        .first()
    )

    try:
        # If bugout user does not belong to installation group, add bugout user to group
        bugout_api.set_user_group(
            token=installation_user.bugout_access_token,
            group_id=installation_user.bugout_group_id,
            user_type="owner",
            username=user.username,
        )
        logger.info(f"Added user with id: {user.id} to GitHub team group")
    except Exception as e:
        logger.info(repr(e))
        raise BugoutAPICallFailed(
            f"Failed to set user at group for installation id: {bot_installation_id}"
        )


async def render_check_details(
    accepted_notes: List[GitHubCheckNotes], failed_notes: List[GitHubCheckNotes]
) -> str:
    """
    Forms a response block for GitHub check's Detail page.
    """
    summary_str = ""

    if len(accepted_notes) > 0:
        summary_str += "**Accepted checks:** \n"
        summary_str += "\n".join(
            [
                f"- [x] {check_note.note} *accepted by @{check_note.accepted_by}*"
                for check_note in accepted_notes
            ]
        )

    if len(failed_notes) > 0:
        if len(accepted_notes) > 0:
            summary_str += "\n\n"

        summary_str += "**Required checks:** \n"
        summary_str += "\n".join(
            [
                f"- [ ] {check_note.note} *created by @{check_note.created_by}*"
                for check_note in failed_notes
            ]
        )

    return summary_str


def add_commits_to_summary(
    token: str,
    org_name: str,
    repo_name: str,
    pull_number: int,
) -> List[EntrySummaryCommitReport]:
    """
    Extract commits from GitHub Pull Request and update summary.
    """
    pr_commits: List[Any] = calls.get_pr_commits(
        repo_name=repo_name,
        org_name=org_name,
        token=token,
        pull_number=pull_number,
    )

    summary_commits = []
    for github_commit in pr_commits:
        commit_sha = github_commit.get("sha")
        commit_message = github_commit.get("commit").get("message")
        commit_author = github_commit.get("commit").get("author").get("name")
        commit_direct_url = github_commit.get("html_url")
        timestamp_raw = github_commit.get("commit").get("author").get("date")
        commit_timestamp = datetime.strptime(timestamp_raw[:-1], "%Y-%m-%dT%H:%M:%S")
        summary_commits.append(
            EntrySummaryCommitReport(
                sha=commit_sha,
                message=commit_message,
                author=commit_author,
                direct_url=commit_direct_url,
                timestamp=commit_timestamp,
            )
        )
    return summary_commits


def add_comments_to_summary(
    token: str,
    org_name: str,
    repo_name: str,
    pull_number: int,
) -> List[EntrySummaryCommentsReport]:
    """
    Extract comments from GitHub Pull Request or Issue and update summary.
    """
    pr_comments: List[Any] = calls.get_pr_comments(
        repo_name=repo_name,
        org_name=org_name,
        token=token,
        pull_number=pull_number,
    )

    summary_comments = []
    for github_comment in pr_comments:
        comment_user_type = github_comment.get("user").get("type")
        if comment_user_type == "Bot":
            continue
        comment_id = github_comment.get("id")
        comment_message = github_comment.get("body")
        comment_author = github_comment.get("user").get("login")
        comment_direct_url = github_comment.get("html_url")
        timestamp_raw = github_comment.get("created_at")
        comment_timestamp = datetime.strptime(timestamp_raw[:-1], "%Y-%m-%dT%H:%M:%S")
        summary_comments.append(
            EntrySummaryCommentsReport(
                id=comment_id,
                message=comment_message,
                author=comment_author,
                direct_url=comment_direct_url,
                timestamp=comment_timestamp,
            )
        )

    return summary_comments


async def process_summary(
    db_session: Session,
    bot_installation: GitHubOAuthEvent,
    repo: GitHubRepo,
    issue_pr: GitHubIssuePR,
) -> Tuple[str, EntrySummaryReport]:
    """
    Extract from Pull Request title, description, commits,
    comments. Retrieve check notes from database and add locust.
    Prepare and render markdown for journal entry.
    """
    pull_number = int(issue_pr.comments_url.rstrip("/").split("/")[-2])
    organization = bot_installation.github_installation_url.rstrip("/").split("/")[-1]
    repository = repo.github_repo_name

    repo_pr_list = issue_pr.comments_url.rstrip("/").split("/")[4:-1]
    context_url = f"https://github.com/{'/'.join(repo_pr_list)}"

    with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
        f_pr_info = executor.submit(
            calls.get_pr_info,
            repository,
            organization,
            bot_installation.access_token,
            pull_number,
        )
        f_summary_commits = executor.submit(
            add_commits_to_summary,
            bot_installation.access_token,
            organization,
            repository,
            pull_number,
        )
        f_summary_comments = executor.submit(
            add_comments_to_summary,
            bot_installation.access_token,
            organization,
            repository,
            pull_number,
        )
        pr_info, summary_commits, summary_comments = (
            f_pr_info.result(),
            f_summary_commits.result(),
            f_summary_comments.result(),
        )

    summary = EntrySummaryReport(
        title=pr_info.get("title"),
        body=pr_info.get("body"),
        comments=summary_comments,
        commits=summary_commits,
    )

    check = await get_check(db_session, issue_pr.id)
    failed_notes = await get_check_notes(db_session, check.id, False)
    accepted_notes = await get_check_notes(db_session, check.id, True)
    summary_checks = await render_check_details(accepted_notes, failed_notes)

    summary_str = ""

    # Header
    summary_str += f"# Pull Request on [{organization}/{repository}]({context_url}): {summary.title}\n"
    summary_str += f"{summary.body}\n"

    # Requirements (Checks)
    summary_str += "\n## Requirements\n"
    summary_str += summary_checks

    # Commits
    summary_str += "\n## Commits\n"
    for commit in summary.commits:
        summary_str += f"\n[Pushed commit {commit.sha[:7]} by {commit.author}]({commit.direct_url}):\n"
        summary_str += f"```bash\n"
        summary_str += f"{commit.message}\n"
        summary_str += f"```\n"

    # Conversation
    summary_str += "\n## Conversation\n"
    for comment in summary.comments:
        summary_str += f"\n[Commented by {comment.author} message {comment.id}]({comment.direct_url}):\n"
        summary_str += f"{comment.message}\n"

    # Locust summary
    locust_summary = await get_locust_summary(
        db_session, issue_pr_id=issue_pr.id, terminal_hash=issue_pr.terminal_hash
    )
    if locust_summary is not None:
        locust_summary_content = await get_summary_content(locust_summary.id, "locust")
        locust_content_html = render.renderers["html-github"](
            json.loads(locust_summary_content)
        )
        summary_str += f"\n{locust_content_html}"

    return summary_str, summary
