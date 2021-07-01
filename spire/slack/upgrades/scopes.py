"""
Utilities related to Slack OAuth scopes
"""

from typing import Set

from ..models import SlackOAuthEvent


class InsufficientSlackScopes(ValueError):
    """
    Raised when an installation has insufficient scopes.
    """


def parse_scopes(scope_string: str) -> Set[str]:
    """
    Takes a scope string (as seen in the `scope` query parameter of a Slack app installation URL)
    and returns a set of scopes.
    """
    return set(scope_string.split(","))


def check_scopes(
    bot_installation: SlackOAuthEvent, expected_scopes: Set[str]
) -> SlackOAuthEvent:
    bot_scopes = parse_scopes(bot_installation.bot_scope)
    missing_scopes = ",".join(
        [scope for scope in expected_scopes if scope not in bot_scopes]
    )
    if missing_scopes != "":
        raise InsufficientSlackScopes(
            f"Installation ({bot_installation.id}) in workspace ({bot_installation.team_id}) is "
            f"missing the following Slack scopes: {missing_scopes}"
        )
    return bot_installation
