"""
Reaction-related operations
"""
import os
import json
import logging
from typing import Any, cast, Dict, List, Union

import requests
from concurrent.futures import ThreadPoolExecutor


from . import indices
from .models import SlackOAuthEvent, SlackBugoutUser
from .. import db
from ..broodusers import get_bugout_user, BugoutUserNotFound, Existence
from ..utils.settings import BUGOUT_CLIENT_ID_HEADER

logger = logging.getLogger(__name__)

THREAD_WORKERS = int(os.getenv("THREAD_WORKERS", 2))


def get_response(
    slack_token: str,
    message_channel: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> Dict[str, Any]:
    """
    It returns message info was reacted with BUGOUT_EMOJI.
    """
    reactions_get_url = "https://slack.com/api/reactions.get"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "timestamp": message_ts,
    }
    try:
        r = requests.post(reactions_get_url, data=payload, timeout=1)
        r.raise_for_status()
        reactions_get_response = r.json()
        logger.info("REACTIONS")
        logger.info(reactions_get_response)
        assert reactions_get_response["ok"]
    except Exception as e:
        logger.error(
            f"Error viewing reactions on Slack message: installation={bot_installation.id}, "
            f"channel={message_channel}, timestamp={message_ts}:\n{repr(e)}"
        )
        raise

    return reactions_get_response


def get_permalink(
    message_channel: str,
    slack_token: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> str:
    """
    Get link to message was reacted with BUGOUT_EMOJI.
    """
    get_link_url = "https://slack.com/api/chat.getPermalink"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "message_ts": message_ts,
    }
    try:
        r = requests.post(get_link_url, data=payload, timeout=2)
        r.raise_for_status()
        response = r.json()
        permalink = response["permalink"]
    except Exception as e:
        logger.error(
            f"Error retrieving permalink from Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, message_ts={message_ts}:\n{repr(e)}"
        )
        raise

    return permalink


def get_tags(
    message_channel: str,
    message_user: str,
    slack_token: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> List[str]:

    """
    Compose list of tags to message was reacted with BUGOUT_EMOJI.
    """
    tags = []
    conversation_info_url = "https://slack.com/api/conversations.info"
    conversation_payload = {
        "token": slack_token,
        "channel": message_channel,
    }
    user_info_url = "https://slack.com/api/users.profile.get"
    user_payload = {
        "token": slack_token,
        "user": message_user,
    }

    def _make_request(url: str, data: Dict[str, Any]) -> Dict[str, Any]:
        r = requests.post(url, data=data, timeout=1)
        r.raise_for_status()
        response = r.json()
        logger.info(f"Slack {url} info response")
        return response

    try:
        with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
            f_channel = executor.submit(
                _make_request, conversation_info_url, conversation_payload
            )
            f_user = executor.submit(_make_request, user_info_url, user_payload)

            channel, user = (
                f_channel.result().get("channel", {}),
                f_user.result().get("profile", {}),
            )

            if user:
                user_name = user.get("display_name")
                if user_name is not None:
                    tags.extend([user_name])

            if channel.get("is_channel", False) or channel.get("is_group", False):
                channel_name = channel.get("name")
                if channel_name is not None:
                    tags.extend([channel_name])

    except Exception as e:
        logger.error(
            f"Error retrieving conversation info from Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, message_ts={message_ts}:\n{repr(e)}"
        )
        raise

    return tags


def get_conversations_history(
    slack_token: str,
    message_channel: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> List[Dict[str, Any]]:
    """
    This function is used to get message history in channel.
    """
    # Documentation: https://api.slack.com/methods/conversations.history
    # 370 ~ 5 min backlog
    conversations_history_url = "https://slack.com/api/conversations.history"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "latest": message_ts,
        "inclusive": 0,
        "limit": 100,
        "oldest": float(message_ts) - 350,
    }
    try:
        r = requests.post(conversations_history_url, data=payload, timeout=3)
        r.raise_for_status()
        response = r.json()
        logger.info("Slack messages response:")
        logger.info(json.dumps(response))
    except Exception as e:
        logger.error(
            f"Error retrieving message from Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, message_ts={message_ts}:\n{repr(e)}"
        )
        raise

    message_row = []
    if response.get("messages") is not None:
        message_row = response["messages"]

    return message_row


def add_entry(
    permalink: str,
    message_content: str,
    tags: list,
    journal_base_url: str,
    reaction_user: str,
    bugout_user: SlackBugoutUser,
    bot_installation: SlackOAuthEvent,
) -> Dict[str, Any]:
    """
    Creates entry for reacted message and returns entry_id.
    """
    entry_url = f"{journal_base_url}/entries"
    context_id_raw = permalink.rstrip("/").split("/")[-1]
    context_id = context_id_raw.rstrip("?").split("?")[0].replace("p", "")
    try:
        payload = {
            "title": " ".join(message_content.split()[:4]),
            "content": message_content,
            "tags": tags,
            "context_id": context_id,
            "context_url": permalink,
            "context_type": "slack",
        }
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{reaction_user}",
            "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        }
        r = requests.post(entry_url, headers=headers, json=payload, timeout=3)
        r.raise_for_status()
        entry = r.json()
    except Exception as e:
        logger.error(
            f"Error posting new entry to journal ({entry_url}) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        raise

    return entry


def remove_entry(
    journal_base_url: str,
    entry_id: str,
    reaction_user: str,
    bugout_user: SlackBugoutUser,
    bot_installation: SlackOAuthEvent,
) -> None:
    """
    Remove entry from journal
    """
    entry_delete = f"{journal_base_url}/entries/{entry_id}"

    try:
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{reaction_user}",
            "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        }
        r = requests.delete(entry_delete, headers=headers, timeout=3)
        r.raise_for_status()
    except Exception as e:
        logger.error(
            f"Error deleting entry ({entry_id}) from journal ({entry_delete}) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        raise


def search_entry(
    journal_base_url: str,
    message_ts: str,
    reaction_user: str,
    bugout_user: SlackBugoutUser,
    bot_installation: SlackOAuthEvent,
) -> str:
    """
    Search journal via message_ts
    """

    entry_search = f"{journal_base_url}/search"
    try:
        params: Dict[str, Union[int, str]] = {
            "q": f"p{message_ts.replace('.','')}",
            "limit": 1,
        }
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}-{reaction_user}",
            "Authorization": f"Bearer {bugout_user.bugout_access_token}",
        }
        r = requests.get(entry_search, headers=headers, params=params, timeout=3)
        r.raise_for_status()
        response = r.json()
        if response.get("results"):
            entry_id = response["results"][0]["entry_url"].split("/")[-1]
        else:
            logger.error(
                "Search in journal {entry_search} not return result for message {message_ts}"
            )
            raise
    except Exception as e:
        logger.error(
            f"Error search entry in journal ({entry_search}) for "
            f"installation={bot_installation.id}:\n{repr(e)}"
        )
        raise
    return entry_id


def remove_reaction(
    slack_token: str,
    message_channel: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> None:
    """
    Remove Bugout reaction from Slack
    """
    back_emoji = os.environ.get("BUGOUT_BACK_EMOJI", "thumbsup")
    reaction_remove_url = "https://slack.com/api/reactions.remove"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "timestamp": message_ts,
        "name": back_emoji,
    }
    try:
        r = requests.post(reaction_remove_url, data=payload, timeout=1)
        r.raise_for_status()
        response = r.json()
        logger.info("Response to reaction.remove attempt:")
        logger.info(json.dumps(response))
        assert response["ok"]
    except Exception as e:
        logger.error(
            f"Error remove reaction to Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, timestamp={message_ts}:\n{repr(e)}"
        )
        raise


def return_reaction_back(
    slack_token: str,
    message_channel: str,
    message_ts: str,
    bot_installation: SlackOAuthEvent,
) -> None:
    """
    Returns confirmation to Slack using an emoji.
    """
    back_emoji = os.environ.get("BUGOUT_BACK_EMOJI", "thumbsup")
    reaction_add_url = "https://slack.com/api/reactions.add"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "timestamp": message_ts,
        "name": back_emoji,
    }
    try:
        r = requests.post(reaction_add_url, data=payload, timeout=1)
        r.raise_for_status()
        response = r.json()
        logger.info("Response to reaction.add attempt:")
        logger.info(json.dumps(response))
        assert response["ok"] or response["error"] == "already_reacted"
    except Exception as e:
        logger.error(
            f"Error posting reaction to Slack: installation={bot_installation.id}, "
            f"channel={message_channel}, timestamp={message_ts}:\n{repr(e)}"
        )
        raise


def handle_journal_index_remove(item: Dict[str, Any]) -> None:
    """
    Handles a remove entry from journal.
    """
    bugout_emoji = os.environ.get("BUGOUT_JOURNAL_EMOJI", "")
    event = item["event"]
    event_item = event["item"]
    reaction_user = event["user"]

    message_channel = event_item["channel"]
    message_ts = event_item["ts"]

    with db.yield_connection_from_env_ctx() as db_session:
        team_id = item["team_id"]
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .one()
        )

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
        journal_index = indices.get_index_by_name(
            db_session, bot_installation, journal_index_name
        )
        # Strip off "/search" from index search URL to get the base URL for the journal
        journal_base_url = "/".join(journal_index.index_url.rstrip("/").split("/")[:-1])

    all_bugout_reaction_is_removed = True
    already_reacted = False

    reactions_get_response = get_response(
        slack_token, message_channel, message_ts, bot_installation
    )
    response_message = reactions_get_response.get("message", {})
    existing_reactions = response_message.get("reactions", [])

    # Andrey TODO: remove hardcode when our bugout reaction not have 2 names
    for reaction in existing_reactions:
        if reaction["name"] == bugout_emoji:
            all_bugout_reaction_is_removed = False
        if (
            reaction["name"] == "+1" or reaction["name"] == "thumbsup"
        ) and bot_installation.bot_user_id in reaction.get("users", []):
            already_reacted = True

    if not all_bugout_reaction_is_removed or not already_reacted:
        return

    remove_reaction(
        slack_token,
        message_channel,
        message_ts,
        bot_installation,
    )

    entry_id = search_entry(
        journal_base_url,
        message_ts,
        reaction_user,
        bugout_user,
        bot_installation,
    )

    remove_entry(
        journal_base_url,
        entry_id,
        reaction_user,
        bugout_user,
        bot_installation,
    )


def return_ephemeral(
    user: str,
    journal_base_url: str,
    slack_token: str,
    message_channel: str,
    entry: Dict[str, Any],
    bot_installation: SlackOAuthEvent,
) -> None:
    """
    Returns ephemeral message to user, which is visible only to the assigned user.

    # TODO(kompotkot): "blocks" and "attachments" in payload doesn't want to work, no idea why..
    # Need to consult with Slack why I get response: {"ok": false, "error": "internal_error"}
    # https://api.slack.com/docs/messages/builder
    # "attachments": [{"text": "And here’s an attachment!"}]
    # "blocks": [{"type": "section", "text": {"type": "plain_text", "text": "Hello world"}}],
    """
    bugout_domain = os.getenv("BUGOUT_WEB_URL", "")
    journal_id = str(entry.get("journal_url")).split("/")[-1]

    link_url = f"{bugout_domain}/journals/{journal_id}/{entry.get('id')}"
    entry_url = f"{journal_base_url}/entries/{entry.get('id')}"
    # Documentation: https://api.slack.com/methods/chat.postEphemeral
    ephemeral_url = "https://slack.com/api/chat.postEphemeral"
    payload = {
        "token": slack_token,
        "channel": message_channel,
        "user": user,
        "text": f"A new entry was created in your journal.\n*<{link_url}|Edit the entry or add tags>*",
        "blocks": json.dumps(
            [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"A new entry was created in your journal.\n*<{link_url}|Edit the entry or add tags>*",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Okay!",
                                "emoji": True,
                            },
                            "value": "placeholder_value",
                            "action_id": "remove_ephemeral_message",
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "Edit",
                                "emoji": True,
                            },
                            "value": f"{entry_url}",
                            "action_id": "edit-journal-entry-modal",
                        },
                    ],
                },
            ]
        ),
    }
    try:
        r = requests.post(ephemeral_url, data=payload, timeout=1)
        r.raise_for_status()
        response = r.json()
        logger.info("Ephemeral response:")
        logger.info(json.dumps(response))
        assert response["ok"] or response["error"] == "bad_ephemeral"
    except Exception as e:
        logger.error(
            f"Error posting reaction to Slack: installation={bot_installation.id}"
        )
        raise


def handle_journal_index_reaction(item: Dict[str, Any]) -> None:
    """
    Handles a Slack reaction_added event signifying that a comment should be indexed in the
    team journal.
    """

    event = item["event"]
    event_item = event["item"]
    reaction_user = event["user"]

    message_channel = event_item["channel"]
    message_ts = event_item["ts"]
    message_user = event["item_user"]

    with db.yield_connection_from_env_ctx() as db_session:
        team_id = item["team_id"]
        bot_installation = (
            db_session.query(SlackOAuthEvent)
            .filter(SlackOAuthEvent.team_id == team_id)
            .one()
        )

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
        journal_index = indices.get_index_by_name(
            db_session, bot_installation, journal_index_name
        )
        # Strip off "/search" from index search URL to get the base URL for the journal
        journal_base_url = "/".join(journal_index.index_url.rstrip("/").split("/")[:-1])

    # Get message with reaction
    # TODO(neeraj): Improve the logic here. This is an unnecessary API call. We can check that the
    # message that's being reacted to has been added to the database (using the permalink, for
    # example) instead. That would reduce the latency of the slack :+1: response. It's also reflects
    # the role of our database as the definitive source of truth - not Slack's database!!
    already_reacted = False
    reactions_get_response = get_response(
        slack_token, message_channel, message_ts, bot_installation
    )

    response_message = reactions_get_response.get("message", {})
    existing_reactions = response_message.get("reactions", [])
    for reaction in existing_reactions:
        if (
            reaction["name"] == "+1" or reaction["name"] == "thumbsup"
        ) and bot_installation.bot_user_id in reaction.get("users", []):
            already_reacted = True

    if already_reacted:
        return

    with ThreadPoolExecutor(max_workers=THREAD_WORKERS) as executor:
        # Get permalink func
        f_permalink = executor.submit(
            get_permalink, message_channel, slack_token, message_ts, bot_installation.id
        )

        # Reaction back to Slack
        executor.submit(
            return_reaction_back,
            slack_token,
            message_channel,
            message_ts,
            bot_installation,
        )

        # Add entry
        f_tags = executor.submit(
            get_tags,
            message_channel,
            message_user,
            slack_token,
            message_ts,
            bot_installation.id,
        )

        permalink, tags = f_permalink.result(), f_tags.result()

    entry = add_entry(
        permalink,
        response_message["text"],
        tags,
        journal_base_url,
        reaction_user,
        bugout_user,
        bot_installation,
    )

    return_ephemeral(
        reaction_user,
        journal_base_url,
        slack_token,
        message_channel,
        entry,
        bot_installation,
    )
