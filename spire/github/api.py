"""
Github App handlers.
"""
import base64
import json
import time
import logging
import dateutil.parser
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    FastAPI,
    Form,
    HTTPException,
    Request,
    Depends,
    BackgroundTasks,
)

import jwt  # type: ignore
import requests
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session

from . import actions
from . import commands
from .events import GITHUB_SELECTORS
from .data import LocustSummaryReport, SummaryResponse, SummaryContentResponse
from .handlers import verify_github_request_p
from .models import GitHubOAuthEvent, GitHubRepo
from ..db import yield_connection_from_env_ctx, yield_connection_from_env
from ..utils.settings import (
    GITHUB_SECRET_B64,
    GITHUB_KEYFILE,
    GITHUB_APP_ID,
    GITHUB_REDIRECT_URL,
)
from ..broodusers import BugoutAuthHTTPError, BugoutAuthUnexpectedResponse

logger = logging.getLogger(__name__)

app = FastAPI(openapi_url=None)

BUGOUT_PARSER = commands.generate_bugout_parser()


def process_authorization_header(bugout_secret_bearer: Optional[str]) -> str:
    if not bugout_secret_bearer:
        raise HTTPException(status_code=403, detail="No authorization header provided")
    bearer = "Bearer "
    if not bugout_secret_bearer.startswith(bearer):
        raise HTTPException(
            status_code=403,
            detail="Invalid token format: we require Authorization headers of the form 'Bearer <token>'",
        )

    return bugout_secret_bearer[len(bearer) :]


def submit_oauth(code: str, installation_id: int) -> Optional[GitHubOAuthEvent]:
    """
    Add Github Token to database.

    :request: {'token': 'v1.token123', expires_at': '2020-10-08T12:15:25Z',
    'permissions': {'metadata': 'read', 'pull_requests': 'write', 'statuses': 'read'},
    'repository_selection': 'all'}
    """
    with yield_connection_from_env_ctx() as db_session:
        current_time = int(time.time())
        payload = {
            "iat": current_time,
            "exp": current_time + 600,
            "iss": GITHUB_APP_ID,
        }
        if GITHUB_SECRET_B64:
            secret = base64.b64decode(GITHUB_SECRET_B64).decode()
        else:
            with open(GITHUB_KEYFILE) as ifp:
                secret = ifp.read()

        jwt_token = jwt.encode(payload, secret, algorithm="RS256")

        access_token_url = (
            f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        )
        headers = {
            "Accept": "application/vnd.github.machine-man-preview+json",
            "Authorization": f"Bearer {jwt_token.decode()}",
        }

        bot_installation = None
        try:
            r = requests.post(access_token_url, headers=headers)
            response_body = r.json()

            # Convert time to proper format
            expiration_time_obj = dateutil.parser.parse(response_body.get("expires_at"))
            expiration_time = expiration_time_obj.strftime("%Y-%m-%d %H:%M:%S.%f")

            query = db_session.query(GitHubOAuthEvent).filter(
                GitHubOAuthEvent.github_installation_id == installation_id
            )
            query.update(
                {
                    GitHubOAuthEvent.access_token: response_body.get("token"),
                    GitHubOAuthEvent.access_token_expire_ts: expiration_time,
                    GitHubOAuthEvent.access_code: code,
                }
            )

            db_session.commit()
            bot_installation = query.first()

            logger.info(
                f"Added or updated github token: {response_body.get('token')} "
                f"for installation id: {installation_id}"
            )

        except Exception as err:
            logger.error(
                f"Warning: Error retrieving GitHub Installation access token\n"
                f"Access token URL: {access_token_url}\n"
                f"JWT: {jwt_token.decode()}\n"
                f"Error: {repr(err)}"
            )

        return bot_installation


@app.get("/oauth")
async def github_oauth_handler(
    code: str,
    installation_id: int,
    background_tasks: BackgroundTasks,
    setup_action: str,
    db_session: Session = Depends(yield_connection_from_env),
) -> RedirectResponse:
    """
    Request during Github App installation in repository.

    :request: GET /github/oauth?code=123&installation_id=123&setup_action=install
    """

    logger.info(
        f"Triggered GitHub oauth event with setup action: {setup_action} "
        f"and installation: {installation_id}"
    )
    if setup_action == "install":
        bot_installation = submit_oauth(code, installation_id)

        if bot_installation is not None:
            # Extract all possible repos for organization and add them to database
            background_tasks.add_task(
                actions.add_repo_list, db_session, bot_installation
            )

    return RedirectResponse(url=GITHUB_REDIRECT_URL)


@app.post("/webhook")
async def github_webhook_handler(
    request: Request,
    background_tasks: BackgroundTasks,
) -> None:
    """
    Handler of all installations, uninstallations and any actions with our GitHub App.

    All open, reopen, close, add commit respond from GitHub to us:
    'x-github-event': 'pull_request'
    """
    response_body = await request.json()

    verified = await verify_github_request_p(request)
    if not verified:
        logger.error("Could not verify GitHub signature")
        raise HTTPException(status_code=400, detail="Improper GitHub signature")

    github_event_type = request.headers["x-github-event"]
    github_installation_id = response_body.get("installation", {}).get("id", int())
    action = response_body.get("action", "")

    if github_event_type == "installation":
        selector = GITHUB_SELECTORS.get(f"{github_event_type}_{action}")
        if selector is not None:
            background_tasks.add_task(selector, response_body)
            logger.info(f"Installation {github_installation_id} was {action}")

    elif github_event_type == "installation_repositories":
        logger.info(f"New repo was added for installation: {github_installation_id}")

    elif github_event_type == "pull_request":
        selector = GITHUB_SELECTORS.get(f"{github_event_type}_{action}")
        if selector is not None:
            background_tasks.add_task(selector, response_body)
            logger.info(
                f"Pull Request was {action} for installation: {github_installation_id}"
            )

    elif github_event_type == "issue_comment":
        # Handle comment in Issue / Pull Request
        if action == "created" or "edited":

            background_tasks.add_task(
                commands.handle_mention,
                github_installation_id,
                response_body,
                BUGOUT_PARSER,
            )

    elif github_event_type == "check_run":
        selector = GITHUB_SELECTORS.get(f"{github_event_type}")
        if selector is not None:
            background_tasks.add_task(selector, response_body)

    else:
        logger.info(f"Unhandled event: {github_event_type} with action: {action}")


@app.post("/summary")
async def locust_summary_handler(
    request: Request,
    summary: LocustSummaryReport,
    db_session: Session = Depends(yield_connection_from_env),
) -> None:
    """
    Receive locust summary report and save it to DB and S3.
    """
    logger.info(
        f"Received locust summary with terminal_hash: {summary.terminal_hash} "
        f"and comments_url: {summary.comments_url}"
    )

    bugout_secret = process_authorization_header(request.headers.get("authorization"))

    try:
        issue_pr = await actions.get_issue_pr(
            db_session=db_session,
            comments_url=summary.comments_url,
            terminal_hash=summary.terminal_hash,
        )

        await actions.process_secret(db_session, bugout_secret, issue_pr.event_id)
        await actions.store_locust(db_session, summary, issue_pr)

        bot_installation = (
            db_session.query(GitHubOAuthEvent)
            .filter(GitHubOAuthEvent.id == issue_pr.event_id)
            .first()
        )
        repo = (
            db_session.query(GitHubRepo)
            .filter(GitHubRepo.id == issue_pr.repo_id)
            .first()
        )

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
                summary.comments_url,
                entry_id=entry_id,
            )

    except actions.IssuePRNotFound:
        logger.error(f"Issue or PR not found for comments_url: {summary.comments_url}")
        raise HTTPException(status_code=404)
    except actions.BugoutSecretIncorrect:
        logger.error(f"Bugout Secret is incorrect")
        raise HTTPException(status_code=403)
    except actions.S3CallFailed:
        logger.error("Error due processing Locust summary")
        raise HTTPException(status_code=500)
    except BugoutAuthHTTPError:
        logger.error("Provided bugout secret is incorrect")
        raise HTTPException(status_code=404)
    except BugoutAuthUnexpectedResponse:
        logger.error("Unexpecting authorization response")
        raise HTTPException(status_code=404)
