"""
Handlers for Bugout Slack shortcuts
"""
import os
import argparse
import json
import logging
from typing import Any, Callable, cast, Coroutine, Dict, List, Optional, Union, Tuple

import requests
from concurrent.futures import ThreadPoolExecutor

from .models import SlackOAuthEvent, SlackIndexConfiguration, SlackBugoutUser
from .indices import get_index_by_name, get_installation_indices
from .handlers import InstallationNotFound
from .commands import search_blocks_modifier
from .reactions import (
    get_tags,
    get_permalink,
    get_conversations_history,
    return_reaction_back,
)
from ..db import yield_connection_from_env_ctx
from ..broodusers import get_bugout_user, BugoutUserNotFound, Existence
from ..utils.settings import BUGOUT_CLIENT_ID_HEADER


logger = logging.getLogger(__name__)

SLACK_CONTENT_DIVIDER = "- - -"
THREAD_WORKERS = int(os.getenv("THREAD_WORKERS", 2))

form_entry_block_ids = {
    "title": "title_entry",
    "content": "content_entry",
    "tags": "tags_entry",
}

form_entry_action_ids = {
    "title": "title_action",
    "content": "content_action",
    "tags": "tags_action",
}

action_for_logs = {"POST": "Creating", "PUT": "Updating", "DELETE": "Deleting"}


def generate_entry_form(form: Dict[str, Any] = None) -> List[Any]:
    """
    Generate modal blocks for create/update entry form
    note: If form init is None then return empty entry form
    """
    final_block = []

    if not form:
        form = dict()

    modal_title: Dict[str, Any] = {
        "type": "input",
        "block_id": form_entry_block_ids["title"],
        "label": {"type": "plain_text", "text": "Title"},
        "element": {
            "type": "plain_text_input",
            "action_id": form_entry_action_ids["title"],
        },
    }
    if form.get("title_placeholder", None):
        modal_title["element"]["placeholder"] = {
            "type": "plain_text",
            "text": form["title_placeholder"],
        }
    else:
        modal_title["element"]["initial_value"] = form.get("title_initial", "")
    final_block.append(modal_title)

    modal_content: Dict[str, Any] = {
        "type": "input",
        "block_id": form_entry_block_ids["content"],
        "label": {"type": "plain_text", "text": "Content"},
        "element": {
            "type": "plain_text_input",
            "action_id": form_entry_action_ids["content"],
            "multiline": True,
            "placeholder": {"type": "plain_text", "text": "Your entry content query"},
        },
    }

    if form.get("content_placeholder", None):
        modal_content["element"]["placeholder"] = {
            "type": "plain_text",
            "text": form["content_placeholder"],
        }
    else:
        modal_content["element"]["initial_value"] = form.get("content_initial", "")
    final_block.append(modal_content)

    modal_tags: Dict[str, Any] = {
        "type": "input",
        "block_id": form_entry_block_ids["tags"],
        "dispatch_action": True,
        "label": {"type": "plain_text", "text": "Tags"},
        "element": {
            "placeholder": {"type": "plain_text", "text": "Select tags"},
            "action_id": form_entry_action_ids["tags"],
            "type": "multi_external_select",
            "min_query_length": 0,
        },
        "hint": {"type": "plain_text", "text": "Select tags from dropdown menu."},
    }
    if form.get("tags_initial", None):
        modal_tags["element"]["initial_options"] = []
        modal_tags["element"]["initial_options"].extend(
            [
                {"text": {"type": "plain_text", "text": tag}, "value": tag}
                for tag in form["tags_initial"]
            ]
        )

    final_block.append(modal_tags)
    if not form.get("create_send_to"):
        final_block.append(
            {
                "type": "actions",
                "block_id": "channe_select",
                "elements": [
                    {
                        "action_id": "add-send-option-to-modal",
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Post this entry to a channel",
                        },
                        "value": "click_send_to",
                    }
                ],
            }
        )
    else:
        list_of_channels_filters = ["private", "public"]
        send_to_current_conversation = True
        final_block.append(
            generate_send_to_channel_block(
                list_of_channels_filters, send_to_current_conversation
            )
        )

    if form.get("context_url"):
        modal_permalink: Dict[str, Any] = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Slack message link: {form['context_url']}",
            },
        }
        final_block.extend([{"type": "divider"}, modal_permalink])

    return final_block


def generate_send_to_channel_block(
    channel_type_filter: List[str], send_to_current_conversation: bool
) -> Dict[str, Any]:
    """
    Generate block with send to channel option with current channel preset
    """

    conversation_select = {
        "type": "actions",
        "block_id": "conversation_select",
        "elements": [
            {
                "type": "conversations_select",
                "default_to_current_conversation": send_to_current_conversation,
                "placeholder": {
                    "type": "plain_text",
                    "text": "Select conversation",
                    "emoji": True,
                },
                "filter": {"include": channel_type_filter},
                "action_id": "conversation_id",
            }
        ],
    }
    return conversation_select


def extract_entry_payload(payload: Dict[str, Any], action: str) -> List[Any]:
    """
    Process data when we push button "submit/edit". It makes easy to extract title, content,
    tags and context. Generates list according to form_entry_block_ids.
    """

    view_context: Optional[Dict[str, Any]] = payload.get("view")
    if view_context is None:
        logger.error("Malformed view_submission payload")
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_submission")

    # Process input values from user
    view_state_values: Dict[str, Any] = view_context.get("state", {}).get("values", {})

    user_input_data: List[Any] = []
    for key in form_entry_block_ids.keys():
        if key == "tags":
            tags_options = (
                view_state_values.get(form_entry_block_ids[key], {})
                .get(form_entry_action_ids[key], {})
                .get("selected_options")
            )
            if tags_options is None:
                logger.error(
                    f"Could not find {form_entry_block_ids[key]} value in view_submission payload. {action} action."
                )
                logger.error(json.dumps(payload))
                raise ValueError("Bad interaction payload for view_submission")
            query_input = [tag["text"]["text"] for tag in tags_options]

        else:
            query_input = (
                view_state_values.get(form_entry_block_ids[key], {})
                .get(form_entry_action_ids[key], {})
                .get("value")
            )
            if query_input is None:
                logger.error(
                    f"Could not find {form_entry_block_ids[key]} value in view_submission payload. {action} action."
                )
                logger.error(json.dumps(payload))
                raise ValueError("Bad interaction payload for view_submission")
        user_input_data.append(query_input)

    # processing conversation
    conversation_id = None
    if action == "create":
        conversation_id = (
            view_state_values.get("conversation_select", {})
            .get("conversation_id", {})
            .get("selected_conversation")
        )

    user_input_data.append(conversation_id)

    # Extract permalink from block section type
    block_values: List[Dict[str, Any]] = view_context.get("blocks", [])
    if block_values:
        journal_permalink_query = block_values[-1].get("text", {}).get("text")
        if journal_permalink_query is not None:
            context_url = (
                journal_permalink_query.rstrip("<").split("<")[-1].replace(">", "")
            )
            context_id_raw = context_url.rstrip("/").split("/")[-1]
            context_id = context_id_raw.rstrip("?").split("?")[0].replace("p", "")

            user_input_data.extend([context_url, context_id])

    return user_input_data


horizontal_line = {"type": "divider"}


async def noop_handler(payload: Dict[str, Any]) -> None:
    """
    Empty handler for {block,message,etc.} actions which do not need any additional handling logic.
    (e.g. choosing a channel in entry creation modal)

    Using this handler allows us to cleanly send a response back to the Slack API. Without this
    handler, we were sending back 400 status codes (which resulted in users seeing an alarm icon).
    Fixing this in the API would have required unnecessary custom logic.
    """
    pass


async def bugout_search_open(payload: Dict[str, Any]) -> None:
    """
    Handles global shortcut starting a Bugout search from Slack. Responds by opening a modal in
    which users can specify their search queries and the index they would like to search in.
    """
    team_id = payload.get("team", {}).get("id", "")
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token

        bot_indices = (
            db_session.query(SlackIndexConfiguration)
            .filter(SlackIndexConfiguration.slack_oauth_event_id == installation_id)
            .all()
        )

    index_map = {index.index_name: index for index in bot_indices}
    index_options = {
        index_name: {
            "text": {
                "type": "plain_text",
                "text": index_name,
                "emoji": True,
            },
            "value": index_name,
        }
        for index_name in index_map
    }
    index_selector = {
        "type": "static_select",
        "action_id": "bugout-search-index",
        "placeholder": {
            "type": "plain_text",
            "text": "Select a search index",
            "emoji": False,
        },
        "options": list(index_options.values()),
    }
    if "web" in index_options:
        index_selector["initial_option"] = index_options["web"]
    if "journal" in index_options:
        index_selector["initial_option"] = index_options["journal"]

    search_input = {
        "type": "input",
        "block_id": "bugout-search-query-block",
        "label": {"type": "plain_text", "text": "Search query"},
        "element": {
            "type": "plain_text_input",
            "action_id": "bugout-search-query",
            "placeholder": {
                "type": "plain_text",
                "text": "Your Bugout search query",
            },
        },
    }
    modal_input = {
        "type": "input",
        "block_id": "bugout-search-index-block",
        "label": {"type": "plain_text", "text": "Select the search index"},
        "element": index_selector,
    }
    search_description = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "Shortcut @bugout helps you execute Bugout search queries directly from your Slack workspace.",
        },
    }
    help_btn = {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "action_id": "expand_help_action",
                "text": {"type": "plain_text", "text": "Expand help", "emoji": True},
                "value": "expand_help_btn",
            }
        ],
    }

    # https://api.slack.com/methods/views.open
    views_open_url = "https://slack.com/api/views.open"
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Bugout search"},
        "blocks": [
            search_input,
            modal_input,
            {"type": "divider"},
            search_description,
            help_btn,
        ],
        "submit": {"type": "plain_text", "text": "Search"},
        "callback_id": "bugout-search-callback",
    }
    view_str = json.dumps(view)
    payload = {
        "token": slack_token,
        "trigger_id": payload["trigger_id"],
        "view": view_str,
    }
    try:
        r = requests.post(views_open_url, data=payload, timeout=1)
        r.raise_for_status()
        views_open_response = r.json()
        logger.info("SHORTCUT: bugout-search")
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(
            f"Error opening Bugout search modal: installation={installation_id}"
        )
        logger.error(repr(e))
        raise


async def bugout_search_submit(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handles user search query and index inputs on the Bugout search modal in Slack.
    """
    view_context: Optional[Dict[str, Any]] = payload.get("view")
    if view_context is None:
        logger.error("Malformed view_submission payload")
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_submission")

    # Process input values from user
    view_state_values: Dict[str, Any] = view_context.get("state", {}).get("values", {})
    bugout_search_query = (
        view_state_values.get("bugout-search-query-block", {})
        .get("bugout-search-query", {})
        .get("value")
    )
    if bugout_search_query is None:
        logger.error(
            "Could not find bugout-search-query value in view_submission payload"
        )
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_submission")

    # Get value from "Select the search index" field
    bugout_search_index = (
        view_state_values.get("bugout-search-index-block", {})
        .get("bugout-search-index", {})
        .get("selected_option", {})
        .get("value")
    )
    if bugout_search_index is None:
        logger.error(
            "Could not find bugout-search-index value in view_submission payload"
        )
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_submission")

    team_id = payload.get("team", {}).get("id", "")
    search_request_headers = {}
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .one()
        )
        installation_id = bot_installation.id
        bot_index = (
            db_session.query(SlackIndexConfiguration)
            .filter(SlackIndexConfiguration.slack_oauth_event_id == bot_installation.id)
            .filter(SlackIndexConfiguration.index_name == bugout_search_index)
            .one()
        )

        if bot_index.use_bugout_client_id:
            user_id = payload.get("user", {}).get("id", "")
            search_request_headers[
                BUGOUT_CLIENT_ID_HEADER
            ] = f"slack-{team_id}-{user_id}"

        if bot_index.use_bugout_auth:
            bugout_user = (
                db_session.query(SlackBugoutUser)
                .filter(SlackBugoutUser.slack_oauth_event_id == installation_id)
                .one()
            )
            search_request_headers[
                "Authorization"
            ] = f"Bearer {bugout_user.bugout_access_token}"

        view: Dict[str, Any] = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "Bugout search results"},
            "blocks": [],
        }

        # Search result cleaning and collecting
        await search_blocks_modifier(
            db_session,
            view["blocks"],
            argparse.Namespace(
                browser=False,
                command="search",
                index=bugout_search_index,
                nothread=False,
                query=[bugout_search_query],
            ),
            team_id,
            user_id,
            bot_installation,
        )

        response_body = {"response_action": "push", "view": view}
        return response_body


async def bugout_search_update(payload: Dict[str, Any]) -> None:
    """
    Handles action modal update. Responds by clicking "Expand help" button.
    """
    view_id = payload.get("container", {}).get("view_id", "")
    view_hash = payload.get("view", {}).get("hash", "")

    team_id = payload.get("team", {}).get("id", "")
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .one()
        )
        installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token

        bot_indices = (
            db_session.query(SlackIndexConfiguration)
            .filter(SlackIndexConfiguration.slack_oauth_event_id == installation_id)
            .all()
        )

        index_map = {index.index_name: index for index in bot_indices}
        index_options = {
            index_name: {
                "text": {
                    "type": "plain_text",
                    "text": index_name,
                    "emoji": True,
                },
                "value": index_name,
            }
            for index_name in index_map
        }
        index_selector = {
            "type": "static_select",
            "action_id": "bugout-search-index",
            "placeholder": {
                "type": "plain_text",
                "text": "Select a search index",
                "emoji": False,
            },
            "options": list(index_options.values()),
        }
        if "web" in index_options:
            index_selector["initial_option"] = index_options["web"]
        if "journal" in index_options:
            index_selector["initial_option"] = index_options["journal"]

        search_input = {
            "type": "input",
            "block_id": "bugout-search-query-block",
            "label": {"type": "plain_text", "text": "Search query"},
            "element": {
                "type": "plain_text_input",
                "action_id": "bugout-search-query",
                "placeholder": {
                    "type": "plain_text",
                    "text": "Your Bugout search query",
                },
            },
        }

        modal_input = {
            "type": "input",
            "block_id": "bugout-search-index-block",
            "label": {"type": "plain_text", "text": "Select the search index"},
            "element": index_selector,
        }
        search_description = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Shortcut @bugout helps you execute Bugout search queries directly from your Slack workspace.",
            },
        }
        help_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "These are the search indices configured in your Slack workspace:",
            },
        }

        # https://api.slack.com/methods/views.update
        views_open_url = "https://slack.com/api/views.update"
        view: Dict[str, Any] = {
            "type": "modal",
            "title": {"type": "plain_text", "text": "Bugout search"},
            "blocks": [
                search_input,
                modal_input,
                {"type": "divider"},
                help_block,
            ],
            "submit": {"type": "plain_text", "text": "Search"},
            "callback_id": "bugout-search-callback",
        }

        # Options in help (web, index, journal)
        installation_indices = get_installation_indices(db_session, bot_installation)
        for index in installation_indices:
            view["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"Index: *{index.index_name}*\n"
                        f"URL: {index.index_url}\n"
                        f"Requires Bugout token? *{index.use_bugout_auth}*\n"
                        f"{index.description}",
                    },
                }
            )
        view["blocks"].append(search_description)

        view_str = json.dumps(view)
        payload = {
            "token": slack_token,
            "view_id": view_id,
            "hash": view_hash,
            "view": view_str,
        }
        try:
            r = requests.post(views_open_url, data=payload, timeout=1)
            r.raise_for_status()
            views_open_response = r.json()
            logger.info("SHORTCUT: bugout-search-update")
            assert views_open_response["ok"], json.dumps(views_open_response)
        except Exception as e:
            logger.error(
                f"Error opening Bugout search update modal: installation={installation_id}"
            )
            logger.error(repr(e))
            raise


async def create_journal_open(payload: Dict[str, Any]) -> None:
    """
    Handles global shortcut Create journal entry from Slack. It allow to user add any
    type of content with title and tags in group journal.
    """
    team_id = payload.get("team", {}).get("id", "")
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token

    # https://api.slack.com/methods/views.open
    # available_channel = get_conversation_list(slack_token,'public_channel,private_channel',bot_installation)

    form_init = {
        "title_placeholder": "Your entry title query",
        "content_placeholder": "Your entry content query",
        "tags_placeholder": "Tag, another tag",
        "create_send_to": False,
    }

    views_open_url = "https://slack.com/api/views.open"
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Add to team journal"},
        "blocks": generate_entry_form(form_init),
        "submit": {"type": "plain_text", "text": "Create"},
        "callback_id": "create-journal-callback",
    }
    view_str = json.dumps(view)
    payload = {
        "token": slack_token,
        "trigger_id": payload["trigger_id"],
        "view": view_str,
    }
    try:
        r = requests.post(views_open_url, data=payload, timeout=1)
        r.raise_for_status()
        views_open_response = r.json()
        logger.info("SHORTCUT: create-journal-entry")
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(
            f"Error opening Bugout create journal modal: installation={installation_id}"
        )
        logger.error(repr(e))
        raise


def add_send_to_block(payload: Dict[str, Any]):
    """
    Add send to selection element
    """

    # extract updating info
    view_id = payload.get("container", {}).get("view_id")
    view_hash = payload.get("view", {}).get("hash")
    team_id = payload.get("team", {}).get("id", "")

    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .one()
        )
        installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token

    if not view_id or not view_hash:
        logger.error("Malformed view_actions update payload")
        logger.error(f"Not found one of necessary field")
        logger.error({"view_id": view_id, "view_hash": view_hash})
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_actions")

    form_init = {
        "title_placeholder": "Your entry title query",
        "content_placeholder": "Your entry content query",
        "tags_placeholder": "Tag, another tag",
        "create_send_to": True,
    }
    views_open_url = "https://slack.com/api/views.update"
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Add to team journal"},
        "blocks": generate_entry_form(form_init),
        "submit": {"type": "plain_text", "text": "Create"},
        "callback_id": "create-journal-callback",
    }

    payload = {
        "token": slack_token,
        "view_id": view_id,
        "hash": view_hash,
        "view": json.dumps(view),
    }

    try:
        r = requests.post(views_open_url, data=payload, timeout=1)
        r.raise_for_status()
        views_open_response = r.json()
        logger.info("SHORTCUT: Add send block update")
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(f"Updating modal error for view {view}")
        logger.error(repr(e))
        raise


async def create_journal_msg_open(payload: Dict[str, Any]) -> None:
    """
    Handles message shortcut Create journal entry from Slack.
    """
    team_id = payload.get("team", {}).get("id", "")
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        bot_installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token

    # Get message content
    message_context: Optional[Dict[str, Any]] = payload.get("message")

    if message_context is None:
        logger.error("Malformed message_action payload")
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for message_action")
    # Get value from text
    message_content_query = message_context.get("text")

    if message_content_query is None:
        logger.error(
            "Could not find message_content_query value in message_action payload"
        )
        logger.error(json.dumps(payload))
        raise ValueError("Bad interaction payload for view_submission")

    message_channel = payload.get("channel", {}).get("id")
    message_ts = payload.get("message_ts")
    message_user = message_context.get("user")

    with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
        f_permalink = executor.submit(
            get_permalink, message_channel, slack_token, message_ts, bot_installation_id
        )
        f_tags = executor.submit(
            get_tags,
            message_channel,
            message_user,
            slack_token,
            message_ts,
            bot_installation_id,
        )
        f_get_conversations_history = executor.submit(
            get_conversations_history,
            slack_token,
            message_channel,
            message_ts,
            bot_installation,
        )
        permalink, tags, conversations_history = (
            f_permalink.result(),
            f_tags.result(),
            f_get_conversations_history.result(),
        )

    # Input modal generate params
    form_init = {
        "title_placeholder": "Your entry title query",
        "content_initial": f"{message_content_query}",
        "tags_initial": tags,
        "context_url": f"{permalink}",
    }
    # Add additional messages from conversations history in content input field
    for each_message in conversations_history:
        if each_message["user"] == message_user:
            form_init[
                "content_initial"
            ] = f"{form_init.get('content_initial', '')}\n{SLACK_CONTENT_DIVIDER}\n{each_message['text']}"

    # https://api.slack.com/methods/views.open
    views_open_url = "https://slack.com/api/views.open"
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Create journal entry"},
        "blocks": generate_entry_form(form_init),
        "submit": {"type": "plain_text", "text": "Create"},
        "callback_id": "create-journal-callback",
    }
    view_str = json.dumps(view)
    payload = {
        "token": slack_token,
        "trigger_id": payload["trigger_id"],
        "view": view_str,
    }
    try:
        r = requests.post(views_open_url, data=payload, timeout=1)
        r.raise_for_status()
        views_open_response = r.json()
        logger.info("SHORTCUT: create-journal-entry-msg")
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(
            f"Error opening Bugout create journal modal: installation={bot_installation_id}"
        )
        logger.error(repr(e))
        raise


async def edit_journal_modal_open(payload: Dict[str, Any]) -> None:
    """
    Handles ephemeral message edit button. Responds by opening a modal
    in which user can modify his previously "bugged" by emoji message.
    For ex. add tags, change title and content.

    Make request to /journal/{journal_id}/entries/{entry_id}
    """

    team_id = payload.get("team", {}).get("id", "")
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        bot_installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token
        try:
            bugout_user = get_bugout_user(
                db_session,
                bot_installation.id,
                throw_on=Existence.DoesNotExist,
            )
            bugout_user = cast(SlackBugoutUser, bugout_user)
        except BugoutUserNotFound as e:
            logger.error(
                f"No Bugout user registered for installation={bot_installation.id}:\n{repr(e)}"
            )
            raise

    # Get message content
    message_context: Optional[Dict[str, Any]] = payload.get("container")
    if message_context is None:
        logger.error("Malformed message container")
        raise ValueError("Bad interaction payload for message_action")

    action_button_value = payload.get("actions")
    if not action_button_value:
        logger.error("Malformed action message")
        raise ValueError("Bad interaction payload for buttons message_action")

    message_user = message_context.get("user")
    entry_url = action_button_value[0]["value"]

    try:
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{message_user}",
            "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        }
        r = requests.get(entry_url, headers=headers, json=payload, timeout=3)
        r.raise_for_status()
        entry = r.json()
    except Exception as e:
        logger.error(
            f"Error get entry from journal ({entry_url}) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        # TODO: If in case when entry not found ephemeral must closing automatically uncomment string below
        # remove_ephemeral_msg(payload)
        raise

    tags = entry["tags"]
    title = entry["title"]
    content = entry["content"]
    context_url = entry["context_url"]

    form_init = {
        "title_initial": title,
        "content_initial": content,
        "tags_initial": tags,
        "context_url": f"{context_url}",
    }

    # https://api.slack.com/methods/views.open
    views_open_url = "https://slack.com/api/views.open"
    view = {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Edit journal entry"},
        "blocks": generate_entry_form(form_init),
        "submit": {"type": "plain_text", "text": "Edit"},
        "private_metadata": entry_url,
        "callback_id": "edit-journal-entry-submit",
    }

    view_str = json.dumps(view)
    payload = {
        "token": slack_token,
        "trigger_id": payload["trigger_id"],
        "view": view_str,
    }
    try:
        r = requests.post(views_open_url, data=payload, timeout=1)
        r.raise_for_status()
        views_open_response = r.json()
        logger.info("interactions: edit-journal-entry-modal")
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(
            f"Error opening Bugout create journal modal: installation={bot_installation_id}"
        )
        logger.error(repr(e))
        raise


def journal_entry_request_handler(
    method: str,
    url: str,
    payload: Dict[str, Any],
    authorization_data: Dict[str, Any],
) -> None:
    """
    Process requests to get entries from Slack journal API.

    Depends of passed method POST, PUT and required data.
    /{journal_id}/entries
    /{journal_id}/entries/tags
    """
    # Andrey TODO: replace all request to our api to one class with methods
    reaction_user: str = authorization_data["reaction_user"]
    bugout_user: SlackBugoutUser = authorization_data["bugout_user"]
    bot_installation: SlackOAuthEvent = authorization_data["bot_installation"]

    headers = {
        BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{reaction_user}",
        "Authorization": f"Bearer {bugout_user.bugout_access_token}",
    }
    try:
        r = requests.request(method, headers=headers, url=url, json=payload, timeout=3)
        r.raise_for_status()
    except Exception as e:
        logger.error(
            f"Error {action_for_logs[method]} entry in journal ({url}) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        raise


async def journal_entry_submit_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processing entry submissions when user made changes.
    After user push Create/Submit/Edit button in Slack shortcut, it creates journal entry
    and collapse modal window.
    """
    # Parsing payload
    action = payload["view"]["callback_id"].split("-")[0]

    title, content, tags, conversations_id, *context_data = extract_entry_payload(
        payload, action=action
    )

    team_id = payload.get("team", {}).get("id", "")
    reaction_user = payload.get("user", {}).get("id", "")

    # Andrey TODO: Make 1 function for extract auth data from db
    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        try:
            bugout_user = get_bugout_user(
                db_session,
                bot_installation.id,
                throw_on=Existence.DoesNotExist,
            )
            bugout_user = cast(SlackBugoutUser, bugout_user)
        except BugoutUserNotFound as e:
            logger.error(
                f"No Bugout user registered for installation={bot_installation.id}:\n{repr(e)}"
            )
            raise

    # Set entry url
    if action == "edit":
        convers = payload.get("user", {}).get("id", "")
        entry_url = payload["view"].get("private_metadata", None)
        if not entry_url:
            logger.error(
                f"Could not find entry_url value in view_submission payload. {action} action."
            )
            logger.error(json.dumps(payload))
            raise ValueError("Bad interaction payload for view_submission")
    else:
        journal_index_name = "journal"
        journal_index = get_index_by_name(
            db_session, bot_installation, journal_index_name
        )

        journal_base_url = "/".join(journal_index.index_url.rstrip("/").split("/")[:-1])
        entry_url = f"{journal_base_url}/entries"

    authorization_data = {
        "reaction_user": reaction_user,
        "bugout_user": bugout_user,
        "bot_installation": bot_installation,
    }

    if action == "create":

        rest_payload = {
            "title": title,
            "content": content,
            "tags": tags,
            "context_url": context_data[0] if context_data else None,
            "context_id": context_data[1] if context_data else None,
            "context_type": "slack",
        }
        journal_entry_request_handler(
            "POST", entry_url, rest_payload, authorization_data
        )
        slack_token = bot_installation.bot_access_token
        if context_data:
            # slack_token = bot_installation.bot_access_token
            message_channel = context_data[0].rstrip("/").split("/")[-2]
            message_ts = context_data[1][0:10] + "." + context_data[1][10:]
            return_reaction_back(
                slack_token, message_channel, message_ts, bot_installation
            )

    elif action == "edit":
        rest_payload = {
            "title": title,
            "content": content,
        }
        journal_entry_request_handler(
            "PUT", entry_url, rest_payload, authorization_data
        )

        rest_payload = {
            "tags": tags,
        }
        entry_tags_url = f"{entry_url}/tags"
        journal_entry_request_handler(
            "PUT", entry_tags_url, rest_payload, authorization_data
        )
    if conversations_id:
        send_message(
            reaction_user, rest_payload, slack_token, conversations_id, bot_installation
        )

    return {"response_action": "clear"}


async def return_tags_options(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate tags options
    current value input condition:
    len(input) = 0 - return 7 most used tags
    len(input) > 0 - return input as 1 option
    """

    team_id = payload.get("team", {}).get("id", "")

    options: Dict[str, Any] = {"options": []}

    if len(payload.get("value", "")) > 0:
        options["options"].append(
            {
                "text": {"type": "plain_text", "text": payload["value"]},
                "value": "value-0",
            }
        )
        return options

    with yield_connection_from_env_ctx() as db_session:
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .order_by(SlackOAuthEvent.updated_at.desc())
        ).first()

        if bot_installation is None:
            raise InstallationNotFound(
                f"Did not find active installation of @bugout in team: {team_id}"
            )

        bot_installation_id = bot_installation.id
        slack_token = bot_installation.bot_access_token
        try:
            bugout_user = get_bugout_user(
                db_session,
                bot_installation.id,
                throw_on=Existence.DoesNotExist,
            )
            bugout_user = cast(SlackBugoutUser, bugout_user)
        except BugoutUserNotFound as e:
            logger.error(
                f"No Bugout user registered for installation={bot_installation.id}:\n{repr(e)}"
            )
            raise
        journal_index_name = "journal"
        journal_index = get_index_by_name(
            db_session, bot_installation, journal_index_name
        )

        journal_base_url = "/".join(journal_index.index_url.rstrip("/").split("/")[:-1])

    user = payload.get("user", {}).get("id", None)
    if user is None:
        logger.error("Malformed message user id is not in payload")
        raise ValueError("Bad interaction payload for block_suggestion")

    try:
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{user}",
            "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        }
        r = requests.get(
            f"{journal_base_url}/tags", headers=headers, json=payload, timeout=3
        )
        r.raise_for_status()
        most_used_tags = r.json()
    except Exception as e:
        logger.error(
            f"Error get tags from journal (journal_base_url) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        raise
    [
        options["options"].append(
            {"text": {"type": "plain_text", "text": text[0]}, "value": f"value-{index}"}
        )
        for index, text in enumerate(most_used_tags)
    ]
    return options


async def remove_ephemeral_msg(payload: Dict[str, Any]) -> None:
    response_url = payload["response_url"]
    delete_payload = {
        "delete_original": True,
    }
    try:
        r = requests.post(
            response_url,
            headers={"Content-type": "application/json"},
            data=json.dumps(delete_payload),
            timeout=1,
        )
        r.raise_for_status()
        views_open_response = r.json()
        assert views_open_response["ok"], json.dumps(views_open_response)
    except Exception as e:
        logger.error(f"Error close ephemeral message.")
        logger.error(repr(e))
        raise


def send_message(
    user: str,
    entry: Dict[str, Any],
    slack_token: str,
    message_channel: str,
    bot_installation: SlackOAuthEvent,
) -> None:
    """
    Send message to channel
    """
    reaction_add_url = "https://slack.com/api/chat.postMessage"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "text": "Bot message.",
        "blocks": json.dumps(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"<@{user}> added a new entry to your team journal.\n"
                            f"*Title: * {entry['title']}\n"
                            f"*Tags: * {' '.join([''.join(('`',tag_rep,'`')) for tag_rep in entry['tags']])}\n"
                            f"```{entry['content']}```"
                        ),
                    },
                }
            ]
        ),
    }
    try:
        r = requests.post(reaction_add_url, data=payload, timeout=1)
        r.raise_for_status()
        response = r.json()
        logger.info("Send entry to channel")
        logger.info(json.dumps(response))
        assert response["ok"] or response["error"] == "already_reacted"
    except Exception as e:
        logger.error(
            f"Error posting reaction to Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, err: {e}"
        )


# Make sure that keys of this dict used as callback_id or external_id fields where necessary.
SELECTORS: Dict[
    str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Union[None, Dict[str, Any]]]]
] = {
    # Search
    "bugout-search": bugout_search_open,
    "expand_help_action": bugout_search_update,
    "bugout-search-callback": bugout_search_submit,
    # Global journal
    "create-journal-entry": create_journal_open,
    "create-journal-callback": journal_entry_submit_handler,
    # Message journal
    "create-journal-entry-msg": create_journal_msg_open,
    # Edit entry
    "edit-journal-entry-modal": edit_journal_modal_open,
    # Ephemeral message button actions
    "remove_ephemeral_message": remove_ephemeral_msg,
    # Modal window actions
    "edit-journal-entry-submit": journal_entry_submit_handler,
    "tags_action": return_tags_options,
    "add-send-option-to-modal": add_send_to_block,
    # TODO(andrey): Maybe this needs to be a real handler? This will add the channel tag to the
    # current entry.
    "conversation_id": noop_handler,
}
