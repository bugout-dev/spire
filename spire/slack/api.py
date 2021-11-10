import logging
import json
import os
from typing import Any, Dict

from fastapi import (
    FastAPI,
    Body,
    Request,
    Response,
    Depends,
    BackgroundTasks,
    HTTPException,
)

import requests
from starlette.responses import RedirectResponse
from sqlalchemy.orm import Session

from .. import db
from .handlers import (
    handle_app_uninstall,
    handle_url_verification,
    verify_slack_request_p,
)
from . import admin
from . import interactions
from . import commands
from .models import SlackOAuthEvent
from .upgrades.auto import upgrade_handlers
from . import reactions

logger = logging.getLogger(__name__)

app = FastAPI(openapi_url=None)


BUGOUT_INDICES = {
    "web": "https://search.simiotics.com/parasite",
    "usage": "https://search.simiotics.com/usage",
}
DEFAULT_BUGOUT_INDEX = "web"
BUGOUT_PARSER = commands.generate_bugout_parser()

BUGOUT_OAUTH_COMPLETION_URL = os.getenv(
    "BUGOUT_OAUTH_COMPLETION_URL", "https://bugout.dev"
)


class SlackAPIError(Exception):
    """
    Raised if there is an error from the Slack API.
    """


def submit_oauth_code(code: str) -> None:
    """
    Handle workspace installation and re-installation.
    """
    with db.yield_connection_from_env_ctx() as db_session:
        client_id = os.environ.get("BUGOUT_SLACK_CLIENT_ID")
        if client_id is None:
            raise ValueError("BUGOUT_SLACK_CLIENT_ID environment variable not set")

        client_secret = os.environ.get("BUGOUT_SLACK_CLIENT_SECRET")
        if client_secret is None:
            raise ValueError("BUGOUT_SLACK_CLIENT_SECRET environment variable not set")

        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        slack_oauth_v2_access_url = "https://slack.com/api/oauth.v2.access"

        r = requests.post(slack_oauth_v2_access_url, data=payload)
        r.raise_for_status()
        response_body = r.json()

        if response_body.get("ok") is not True:
            SlackAPIError("Got erroneous response from /oauth.v2.access")

        team = response_body.get("team", {})
        if team is None:
            team = {}

        enterprise = response_body.get("enterprise", {})
        if enterprise is None:
            enterprise = {}

        authed_user = response_body.get("authed_user", {})
        if authed_user is None:
            authed_user = {}

        query = db_session.query(SlackOAuthEvent).filter(
            SlackOAuthEvent.team_id == team.get("id")
        )
        existing_event = query.one_or_none()

        slack_oauth_event = SlackOAuthEvent(
            bot_access_token=response_body.get("access_token"),
            bot_scope=response_body.get("scope"),
            bot_user_id=response_body.get("bot_user_id"),
            team_id=team.get("id"),
            team_name=team.get("name"),
            enterprise_id=enterprise.get("id"),
            enterprise_name=enterprise.get("name"),
            user_access_token=authed_user.get("access_token"),
            authed_user_id=authed_user.get("id"),
            authed_user_scope=authed_user.get("scope"),
            version=0,
        )

        # TODO(kompotkot): To work with user oauth use token_type

        if existing_event is not None:
            logger.info(f"Updating existing installation: {str(existing_event.id)}")
            existing_event.bot_access_token = slack_oauth_event.bot_access_token
            existing_event.bot_scope = slack_oauth_event.bot_scope
            existing_event.team_name = slack_oauth_event.team_name
            existing_event.user_access_token = slack_oauth_event.user_access_token
            existing_event.authed_user_id = slack_oauth_event.authed_user_id
            existing_event.authed_user_scope = slack_oauth_event.authed_user_scope
            existing_event.deleted = False
            db_session.add(existing_event)
            logger.info(
                f"Added scopes to installation ({str(existing_event.id)}): "
                f"{existing_event.bot_scope}"
            )
        else:
            db_session.add(slack_oauth_event)

        db_session.commit()

        bot_installation = slack_oauth_event
        if existing_event is not None:
            bot_installation = existing_event

        installation_id = str(bot_installation.id)

        # Automatically generate user, group, journal and configure index
        bugout_auth_url = admin.auth_url_from_env()
        try:
            admin.authorize_bot_installation(
                db_session, bot_installation, bugout_auth_url
            )
        except Exception as e:
            logger.error(f"Error authorizing bot installation {installation_id}")
            logger.error(repr(e))

        # Automatically upgrade installation to most recent version that it is possible to upgrade
        # to
        current_version = bot_installation.version
        logger.info(f"Attempting automatic upgrade of installation {installation_id}")
        if current_version < len(upgrade_handlers):
            for i, upgrade_handler in enumerate(upgrade_handlers[current_version:]):
                try:
                    logger.info(
                        f"\tUpgrading installation {installation_id} from version "
                        f"{current_version+i} to version {current_version+i+1}"
                    )
                    bot_installation = upgrade_handler(db_session, bot_installation)
                except Exception as e:
                    logger.error(
                        f"Error upgrading installation {installation_id} from version "
                        f"{current_version+i} to version {current_version+i+1}:"
                    )
                    logger.error(repr(e))
                    break
            logger.info(
                f"Automatically upgraded installation {installation_id} to version"
                f"{bot_installation.version}"
            )
        else:
            logger.info(
                f"Installation {installation_id} is already at most recent version "
                f"({current_version})."
            )


@app.get("/oauth")
async def slack_oauth(
    code: str,
    background_tasks: BackgroundTasks,
) -> RedirectResponse:
    background_tasks.add_task(submit_oauth_code, code)
    return RedirectResponse(url=BUGOUT_OAUTH_COMPLETION_URL)


@app.post("/event")
async def slack_event(
    request: Request,
    background_tasks: BackgroundTasks,
    item: Dict[str, Any] = Body(...),
    db_session: Session = Depends(db.yield_connection_from_env),
) -> Any:
    verified = await verify_slack_request_p(request)
    if not verified:
        logger.error("Could not verify slack signature")
        raise HTTPException(status_code=400, detail="Improper Slack signature")

    spire_api_url = os.environ.get(
        "SPIRE_API_URL", "/".join(str(request.url).rstrip("/").split("/")[:-2])
    )

    item_type = item.get("type", "")
    event = item.get("event", {})
    event_type = event.get("type", "")

    try:
        if item_type == "url_verification":
            logger.info("Bot URL verification requested")
            return handle_url_verification(item)
        elif event_type == "app_uninstalled":
            logger.info("Bot uninstallation event")
            team_id = item["team_id"]
            await handle_app_uninstall(db_session, team_id, spire_api_url)
        elif event_type == "app_mention" or (
            event_type == "message"
            and event.get("channel_type", "") == "im"
            and event.get("subtype") is None
        ):
            logger.info("Bot mention event")
            team_id = item["team_id"]
            user_id = event["user"]
            channel_id = event["channel"]
            text = event["text"]
            thread_ts = event.get("thread_ts")
            if thread_ts is None:
                thread_ts = event.get("ts")

            background_tasks.add_task(
                commands.handle_mention,
                team_id,
                user_id,
                channel_id,
                text,
                thread_ts,
                BUGOUT_PARSER,
                spire_api_url,
            )
        elif event_type == "reaction_added":
            journal_emoji = os.environ.get("BUGOUT_JOURNAL_EMOJI", "")
            received_reaction = event.get("reaction", "")
            logger.info(
                f"Received reaction: {received_reaction}. Checking in targets: {[journal_emoji]}"
            )
            if received_reaction == journal_emoji:
                logger.info("Event: Bugout reaction added")
                background_tasks.add_task(reactions.handle_journal_index_reaction, item)
            else:
                logger.info("Ignoring non-Bugout reaction added event")
        elif event_type == "reaction_removed":
            journal_emoji = os.environ.get("BUGOUT_JOURNAL_EMOJI", "")
            received_reaction = event.get("reaction", "")
            logger.info(
                f"Received reaction: {received_reaction}. Checking in targets: {[journal_emoji]}"
            )
            if received_reaction == journal_emoji:
                logger.info("Event: Bugout reaction added")
                background_tasks.add_task(reactions.handle_journal_index_remove, item)
            else:
                logger.info("Ignoring non-Bugout reaction added event")
        else:
            message_json = {"message": "Unhandled Slack event", "item": item}
            logger.warning(json.dumps(message_json))
    except Exception as e:
        logger.error(f"Error handling event")
        logger.error(repr(e))

    return None


@app.post("/interactions")
async def slack_interaction(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Any:
    """
    Handler to work with shortcuts in slack
    """
    try:
        verified = await verify_slack_request_p(request)
    except:
        verified = False

    if not verified:
        logger.error("Could not verify slack signature in interactions request")
        raise HTTPException(status_code=400, detail="Improper Slack signature")

    body = await request.form()
    try:
        payload = json.loads(body["payload"])
    except Exception as e:
        logger.error("Error parsing interaction payload:")
        logger.error(repr(e))
        raise HTTPException(
            400, detail="Could not parse interaction payload from request"
        )
    payload_type = payload.get("type", "")

    # response for processing options input
    if payload_type == "block_suggestion":
        action_id = payload.get("action_id", "")
        shortcut_handler = interactions.SELECTORS.get(action_id)
        if shortcut_handler is None:
            logger.error(
                f"View submission payload={json.dumps(payload)} corresponds to a view for which "
                "there is not submission handler."
            )
            raise HTTPException(
                400, detail=f"No submission handler for action_id={action_id}"
            )
        response = await shortcut_handler(payload)
        return Response(content=json.dumps(response), media_type="application/json")

    # Responds by opening a modal Shortcut
    elif payload_type == "shortcut":
        logger.info(f"OPEN MODAL: {payload}")
        callback_id = payload.get("callback_id", "")
        shortcut_handler = interactions.SELECTORS.get(callback_id)
        if shortcut_handler is None:
            logger.error(
                f"Interaction payload={json.dumps(payload)} had invalid "
                f"callback_id={callback_id}"
            )
            raise HTTPException(
                400, detail=f"No shortcut with callback_id={callback_id}"
            )
        background_tasks.add_task(shortcut_handler, payload)

    # Update modal to view help
    elif payload_type == "block_actions":

        action_id = payload.get("actions")[0].get("action_id", "")
        block_id = payload.get("actions")[0].get("block_id", "")
        update_handler = interactions.SELECTORS.get(action_id)
        if block_id == "filter-home-journals-by-tags":
            update_handler = interactions.SELECTORS.get(block_id)
        if update_handler is None:
            logger.error(
                f"View submission payload={json.dumps(payload)} corresponds to a view for which "
                "there is not submission handler."
            )
            raise HTTPException(
                400, detail=f"No submission handler for action_id={action_id}"
            )
        background_tasks.add_task(update_handler, payload)

    # Handles user search query and index inputs
    elif payload_type == "view_submission":
        logger.info(f"SUBMIT MODAL: {payload}")
        view_context = payload.get("view", {})
        callback_id = view_context.get("callback_id", "")
        submission_handler = interactions.SELECTORS.get(callback_id)
        if submission_handler is None:
            logger.error(
                f"View submission payload={json.dumps(payload)} corresponds to a view for which "
                "there is not submission handler."
            )
            raise HTTPException(
                400, detail=f"No submission handler for callback_id={callback_id}"
            )
        response = await submission_handler(payload)
        return response

    # Shortcut message action
    elif payload_type == "message_action":
        callback_id = payload.get("callback_id", "")
        submission_handler = interactions.SELECTORS.get(callback_id)
        if submission_handler is None:
            logger.error(
                f"View submission payload={json.dumps(payload)} corresponds to a view for which "
                "there is not submission handler."
            )
            raise HTTPException(
                400, detail=f"No submission handler for callback_id={callback_id}"
            )
        background_tasks.add_task(submission_handler, payload)
        return {}

    else:
        logger.error(
            f"Interaction payload={json.dumps(payload)} had invalid type={payload_type}"
        )
        raise HTTPException(
            400,
            detail=f"Bugout slack bot is not configured to handle payloads of type={payload_type}",
        )
