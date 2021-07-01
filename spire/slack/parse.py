"""
Slack message parsing
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SlackTextTokenType(Enum):
    """
    Types of tokens that can be found in the text of a Slack message. As per:
    https://api.slack.com/reference/surfaces/formatting#retrieving-messages
    """

    PLAIN = 1
    CHANNEL = 2
    USER = 3
    SUBTEAM = 4
    SPECIAL = 5
    EMAIL = 6
    URL = 7


@dataclass
class SlackTextToken:
    """
    A token in the text of a Slack message
    """

    raw: str
    token_type: SlackTextTokenType
    token: str
    label: Optional[str] = None


def parse_raw_text(raw_token: str) -> SlackTextToken:
    """
    Parses raw text from a Slack message into a SlackTextToken object. Follows the guidelines
    specified here:
    https://api.slack.com/reference/surfaces/formatting#retrieving-messages

    This doesn't account for the possibility of Slack-formatted parts of a message that are not
    isolated with spaces, line breaks, etc.
    For example, asldkjfksdjf<https://example.com|haha>akjsdklfjsd would parse as a completely plain
    text token.
    """
    if raw_token == "" or raw_token[0] != "<" or raw_token[-1] != ">":
        return SlackTextToken(
            raw=raw_token, token_type=SlackTextTokenType.PLAIN, token=raw_token
        )

    inner_text = raw_token[1:-1]
    if inner_text == "":
        return SlackTextToken(
            raw=raw_token, token_type=SlackTextTokenType.PLAIN, token=raw_token
        )

    segments = inner_text.split("|")
    if len(segments) > 2:
        return SlackTextToken(
            raw=raw_token, token_type=SlackTextTokenType.PLAIN, token=raw_token
        )

    label = None
    if len(segments) == 2:
        label = segments[1]

    slack_signifier = segments[0]
    parsed_token = SlackTextToken(
        raw=raw_token,
        token_type=SlackTextTokenType.URL,
        token=slack_signifier,
        label=label,
    )
    if slack_signifier.startswith("#C"):
        parsed_token.token_type = SlackTextTokenType.CHANNEL
        parsed_token.token = slack_signifier[1:]
    elif slack_signifier.startswith("@"):
        parsed_token.token_type = SlackTextTokenType.USER
        parsed_token.token = slack_signifier[1:]
    elif slack_signifier.startswith("!subteam^"):
        parsed_token.token_type = SlackTextTokenType.SUBTEAM
        parsed_token.token = slack_signifier[len("!subteam^") :]
    elif slack_signifier.startswith("!"):
        parsed_token.token_type = SlackTextTokenType.SPECIAL
        parsed_token.token = slack_signifier[1:]
    elif slack_signifier.startswith("mailto:"):
        parsed_token.token_type = SlackTextTokenType.EMAIL
        parsed_token.token = slack_signifier[len("mailto:") :]

    return parsed_token


def slack_email(raw: str) -> str:
    """
    Parses an email from a slack message
    """
    token = parse_raw_text(raw)
    if token.token_type != SlackTextTokenType.EMAIL:
        raise ValueError(
            f"This token does not represent an email in a Slack message: {raw}"
        )
    return token.token
