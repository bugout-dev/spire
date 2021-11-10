"""
"""
import hashlib
import hmac
from html.parser import HTMLParser
import logging
import os
from typing import Any, cast, Dict
import urllib
import urllib.parse

from fastapi import Request
from sqlalchemy.orm import Session

from . import admin
from .data import BroodUser
from .models import (
    SlackOAuthEvent,
    SlackIndexConfiguration,
    SlackBugoutUser,
)
from ..broodusers import Method, bugout_api, process_group_in_journal_holders

logger = logging.getLogger(__name__)

BUGOUT_SCOPES = [
    "app_mentions:read",
    "channels:read",
    "chat:write",
    "emoji:read",
    "groups:read",
    "groups:write",
    "im:history",
    "im:read",
    "im:write",
    "links:read",
    "mpim:read",
    "mpim:write",
    "reactions:read",
    "users.profile:read",
]


class InstallationNotFound(Exception):
    """
    Raised when a handler requires @bugout to be installed in a Slack workspace but the installation
    is not found.
    """


class SlackParseError(Exception):
    """
    Raised when there is an error parsing a Slack message.
    """


class SlackPostMessageError(Exception):
    """
    Raised when there is an error posting a message to Slack.
    """


class HTMLToText(HTMLParser):
    """
    Converts (even parentless) HTML into raw text. This is used when displaying results containing
    HTML enrichments to users in Slack.
    TODO(neeraj): Should this be handled by the index server?
    """

    def __init__(self):
        self.tokens = []
        super().__init__()

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.tokens.append("\n")

    def handle_endtag(self, tag):
        if tag == "p":
            self.tokens.append("\n")

    def handle_data(self, data):
        self.tokens.append(data)

    def generate(self):
        return " ".join(self.tokens)

    def reset(self):
        self.tokens = []
        super().reset()


async def verify_slack_request_p(request: Request) -> bool:
    """
    Verifies the request as per Slack's instructions:
    https://api.slack.com/authentication/verifying-requests-from-slack

    There is a reference implementation available as part of the slack-events-api package:
    https://github.com/slackapi/python-slack-events-api/blob/9e36236a7488f54cad0d76ec8d2366a43283e2cc/slackeventsapi/server.py#L50
    The reason we didn't directly use that package is that we have to handle FastAPI (actually
    Starlette) requests, not Flask requests.
    """
    BUGOUT_SLACK_SIGNING_SECRET = os.environ.get("BUGOUT_SLACK_SIGNING_SECRET")
    if BUGOUT_SLACK_SIGNING_SECRET is None:
        raise ValueError(
            "Could not verify request: BUGOUT_SLACK_SIGNING_SECRET environment variable not set"
        )
    signing_secret = str.encode(BUGOUT_SLACK_SIGNING_SECRET)

    slack_signature = request.headers["X-Slack-Signature"]

    version = "v0"
    timestamp = request.headers["X-Slack-Request-Timestamp"]
    body_bytes = await request.body()
    req = str.encode(f"{version}:{timestamp}:") + body_bytes
    req_digest = hmac.new(signing_secret, req, hashlib.sha256).hexdigest()
    request_hash = f"v0={req_digest}"

    return hmac.compare_digest(request_hash, slack_signature)


def authorize_url(
    redirect_uri: str = "http://spire.bugout.dev:7475/slack/oauth",
) -> str:
    """
    Creates authorization URL as per Slack OAuth instructions:
    https://api.slack.com/authentication/oauth-v2
    """
    client_id = os.environ.get("BUGOUT_SLACK_CLIENT_ID")

    if client_id is None:
        raise ValueError(
            "Could not create Authorization URL: BUGOUT_SLACK_CLIENT_ID not set"
        )
    quoted_client_id = urllib.parse.quote_plus(client_id)
    client_id_section = f"client_id={quoted_client_id}"

    quoted_redirect_uri = urllib.parse.quote_plus(redirect_uri)
    redirect_uri_section = f"redirect_uri={quoted_redirect_uri}"

    quoted_scopes = urllib.parse.quote_plus(",".join(BUGOUT_SCOPES))
    scope_section = f"scope={quoted_scopes}"

    url = f"https://slack.com/oauth/v2/authorize?{client_id_section}&{scope_section}&{redirect_uri_section}"

    return url


async def handle_app_uninstall(
    db_session: Session, team_id: str, spire_api_url: str
) -> None:
    """
    Handles uninstall of app from workspace by marking SlackOAuthEvent as deleted, removing groups
    and it's ids from journal permissions pertaining to that workspace from internal database.

    BroodUser, SlackBugoutUser, index configuration with journal is saved.
    """
    query = db_session.query(SlackOAuthEvent).filter(SlackOAuthEvent.team_id == team_id)

    oauth_event = query.one()
    oauth_event.deleted = True
    db_session.add(oauth_event)
    db_session.commit()

    # Receive user, his token and groups he belongs to
    installation_user_query = db_session.query(SlackBugoutUser).filter(
        SlackBugoutUser.slack_oauth_event_id == oauth_event.id
    )
    installation_user = installation_user_query.first()

    # Extract journal_id from SlackIndexConfiguration and delete holders from this group
    installation_journal = (
        db_session.query(SlackIndexConfiguration)
        .filter(SlackIndexConfiguration.slack_oauth_event_id == oauth_event.id)
        .filter(SlackIndexConfiguration.index_name == "journal")
        .first()
    )
    journal_id = installation_journal.index_url.rstrip("/").split("/")[-2]

    journal_api_url = spire_api_url + "/journals/"
    process_group_in_journal_holders(
        method=Method.delete,
        journal_id=journal_id,
        journal_api_url=journal_api_url,
        access_token=installation_user.bugout_access_token,
        group_id=installation_user.bugout_group_id,
        bot_installation=oauth_event,
    )
    bugout_api.delete_group(
        installation_user.bugout_access_token, installation_user.bugout_group_id
    )
    installation_user_query.update({SlackBugoutUser.bugout_group_id: None})
    db_session.commit()

    logger.info(
        f"Uninstallation process for bot_installation: {oauth_event.id} complete"
    )


def handle_url_verification(item: Dict[str, Any]) -> str:
    """
    Handles a Slack url_verification request:
    https://api.slack.com/events/url_verification
    """
    challenge = item.get("challenge")
    if challenge is None:
        raise ValueError("No challenge in Slack URL verification request")
    cast(str, challenge)
    return challenge
