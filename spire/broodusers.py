from enum import Enum, unique
import json
import logging
from typing import Any, Dict, List, Optional, Union
import uuid

from bugout.app import Bugout  # type: ignore
import requests
from sqlalchemy.orm import Session

from .utils.settings import auth_url_from_env, SPIRE_API_URL, BUGOUT_CLIENT_ID_HEADER
from .slack.models import SlackBugoutUser, SlackOAuthEvent
from .github.models import GitHubBugoutUser, GitHubOAuthEvent

logger = logging.getLogger(__name__)

bugout_auth_url = auth_url_from_env()
bugout_api = Bugout(brood_api_url=bugout_auth_url, spire_api_url=SPIRE_API_URL)


class Existence(Enum):
    DoesNotExist = 0
    Exists = 1
    Ambivalent = 2


@unique
class Method(Enum):
    get = "get"
    post = "post"
    delete = "delete"


class InvalidObjSpec(ValueError):
    """
    Provided wrong object type.
    """


class BugoutAuthHTTPError(requests.HTTPError):
    """
    Raised when there is an error making requests against Bugout auth URL.
    """


class BugoutAuthUnexpectedResponse(ValueError):
    """
    Raised when Bugout auth server response is unexpected (e.g. unparseable).
    """


class BugoutUserFound(Exception):
    """
    Raised when a Bugout user was found when there wasn't expected to be one.
    """


class BugoutUserNotFound(Exception):
    """
    Raised when a Bugout user was not found when there was expected to be one.
    """


class BugoutGroupNotFound(Exception):
    """
    Raised when a Bugout group is not presented in database.
    """


class BugoutAPICallFailed(Exception):
    """
    Raised when call to Bugout API failed.
    """


def bugout_auth_user_info(
    access_token: Optional[str], rich: bool = False
) -> Dict[str, Any]:
    """
    Given an access token, queries the given Bugout authentication server for the id of the
    corresponding user and their verification status. Returns the JSON response from the
    authentication server.

    If `rich` is False:
    The response dictionary contains a "user_id" and a "verified" key. The "user_id" value is a
    string denoting the Bugout user's id. The value for "verified" is boolean, denoting whether or
    not the given user has completed the verification flow.

    If `rich` is True:
    Returns a full user object with the following fields: "id", "username", "email",
    "normalized_email", "verified", "created_at", "updated_at".
    """
    user_url = f"{bugout_auth_url}/user"
    headers = {"Authorization": access_token}
    try:
        user_response = requests.get(user_url, headers=headers)
        user_response.raise_for_status()
        user_response_body = user_response.json()
        user_response_body["user_id"]
        user_response_body["verified"]
    except requests.HTTPError as e:
        logger.error("HTTP error when retrieving user with access token")
        raise BugoutAuthHTTPError(str(e))
    except Exception as e:
        logger.error("Unexpected response when retrieving user with access token")
        raise BugoutAuthUnexpectedResponse(str(e))

    if not rich:
        return user_response_body

    user_info_url = f"{user_url}/{user_response_body['user_id']}"
    try:
        user_info_response = requests.get(user_info_url, headers=headers)
        user_info_response.raise_for_status()
        body: Dict[str, Any] = user_info_response.json()
        body["user_id"]
        body["username"]
        body["email"]
        body["normalized_email"]
        body["verified"]
        body["created_at"]
        body["updated_at"]
    except requests.HTTPError as e:
        logger.error("HTTP error when retrieving user info")
        raise BugoutAuthHTTPError(str(e))
    except Exception as e:
        logger.error("Unexpected response when retrieving user info")
        raise BugoutAuthUnexpectedResponse(str(e))

    return body


def get_bugout_user(
    db_session: Session,
    installation_id: uuid.UUID,
    throw_on: Existence = Existence.Ambivalent,
    obj_type: Optional[str] = "slack",
) -> SlackBugoutUser:
    """
    Retrieves the SlackBugoutUser matching the given installation from the given database.
    If throw_on is Existence.Exists, raises a BugoutUserFound error if such a user exists.
    If throw_on is Existence.DoesNotExist, raises a BugoutUserNotFound error if such a user does
    not exist.
    If throw_on is Existence.Ambivalent, does not raise an error except in the case that more than
    one matching user was found.
    """
    if obj_type == "slack":
        ObjBugoutUser = SlackBugoutUser
        obj_attr = "slack_oauth_event_id"
    elif obj_type == "github":
        ObjBugoutUser = GitHubBugoutUser
        obj_attr = "event_id"
    else:
        raise InvalidObjSpec("Provide obj_type argument as slack or github")

    bugout_user_query = db_session.query(ObjBugoutUser).filter(
        getattr(ObjBugoutUser, obj_attr) == installation_id
    )
    bugout_user = bugout_user_query.one_or_none()
    if throw_on == Existence.DoesNotExist and bugout_user is None:
        raise BugoutUserNotFound(
            f"Could not find Bugout user for installation: {installation_id}"
        )
    elif throw_on == Existence.Exists and bugout_user is not None:
        raise BugoutUserFound(
            f"Did not expect to find Bugout user ({bugout_user.id}) for installation "
            f"({installation_id})"
        )
    return bugout_user


def process_group_in_journal_holders(
    method: Method,
    journal_id: str,
    journal_api_url: str,
    access_token: Optional[uuid.UUID],
    group_id: uuid.UUID,
    bot_installation: Union[SlackOAuthEvent, GitHubOAuthEvent],
) -> None:
    """
    Depends on Method add or remove holder to/from journal holders list.

    Only "journals.read", "journals.update" permissions are available for group.
    """
    journal_holder_url = f"{journal_api_url}{journal_id}/scopes"

    headers = {
        "Authorization": f"Bearer {str(access_token)}",
    }
    if type(bot_installation) is SlackOAuthEvent:
        headers.update({BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}"})
    elif type(bot_installation) is GitHubOAuthEvent:
        headers.update(
            {BUGOUT_CLIENT_ID_HEADER: f"github-{bot_installation.github_account_id}"}
        )
    else:
        raise InvalidObjSpec(
            "Provide bot_installation argument as GitHubOAuthEvent or SlackIndexConfiguration"
        )
    data = {
        "holder_type": "group",
        "holder_id": str(group_id),
        "permission_list": [
            "journals.read",
            "journals.update",
            "journals.entries.read",
            "journals.entries.create",
            "journals.entries.update",
            "journals.entries.delete",
        ],
    }
    data_str = json.dumps(data)
    try:
        r = requests.request(
            method.value, url=journal_holder_url, data=data_str, headers=headers
        )
        r.raise_for_status()
    except requests.HTTPError as e:
        logger.error(
            "HTTP error when editing journal holders list during from Spire journal API"
        )
        raise BugoutAuthHTTPError(str(e))
    except Exception as e:
        logger.error(
            "Unexpected response during editing journal holders list during from Spire journal API"
        )
        raise BugoutAuthUnexpectedResponse(str(e))
