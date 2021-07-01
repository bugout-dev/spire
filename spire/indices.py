import logging
from typing import Any, Callable, cast, Dict, List, Union

import requests
from requests.api import head
from sqlalchemy.orm import Session

from .slack.data import Index
from .slack.models import SlackOAuthEvent, SlackIndexConfiguration
from .github.models import GitHubOAuthEvent, GitHubBugoutUser, GithubIndexConfiguration
from .broodusers import get_bugout_user, Existence, InvalidObjSpec
from .utils.settings import BUGOUT_CLIENT_ID_HEADER

logger = logging.getLogger(__name__)


def create_team_journal_and_register_index(
    db_session: Session,
    journal_api_url: str,
    bot_installation: Union[SlackOAuthEvent, GitHubOAuthEvent],
) -> Index:
    """
    Creates a team journal and registers the index as a Github index configuration. This only works
    for authenticated Bugout installations.
    """
    # TODO(kompotkot): Lead to a common value journal_name
    if type(bot_installation) is GitHubOAuthEvent:
        ObjIndexConfiguration = GithubIndexConfiguration
        org_name = bot_installation.github_installation_url.rstrip("/").split("/")[-1]
        journal_name = f"Team journal: {org_name}-{bot_installation.github_account_id}"
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"github-{bot_installation.github_account_id}",
        }
    elif type(bot_installation) is SlackOAuthEvent:
        ObjIndexConfiguration = SlackIndexConfiguration
        journal_name = "Team journal" + (
            f": {bot_installation.team_name}"
            if bot_installation.team_name is not None
            else ""
        )
        headers = {
            BUGOUT_CLIENT_ID_HEADER: f"slack-{bot_installation.team_id}",
        }
    else:
        raise InvalidObjSpec(
            "Provide bot_installation argument as GitHubOAuthEvent or SlackIndexConfiguration"
        )

    index_name = "journal"
    journal_count = (
        db_session.query(ObjIndexConfiguration)
        .filter(ObjIndexConfiguration.github_oauth_event_id == bot_installation.id)
        .filter(ObjIndexConfiguration.index_name == index_name)
        .count()
    )
    if journal_count > 0:
        # If Index already exists and configured for workspace before, it means was installed before
        # so just return already configured ObjIndexConfiguration
        slack_index_configuration = (
            db_session.query(ObjIndexConfiguration)
            .filter(ObjIndexConfiguration.github_oauth_event_id == bot_installation.id)
            .filter(ObjIndexConfiguration.index_name == index_name)
            .first()
        )
        index_configuration = Index(
            index_name=slack_index_configuration.index_name,
            index_url=slack_index_configuration.index_url,
            description=slack_index_configuration.description,
            use_bugout_auth=slack_index_configuration.use_bugout_auth,
            use_bugout_client_id=slack_index_configuration.use_bugout_client_id,
        )
        return index_configuration

    bugout_user = get_bugout_user(
        db_session,
        bot_installation.id,
        throw_on=Existence.DoesNotExist,
        obj_type="github",
    )
    bugout_user = cast(GitHubBugoutUser, bugout_user)

    # Create journal request against journal API
    if journal_api_url[-1] != "/":
        journal_api_url += "/"

    logger.info(f"Requesting new journal creation: {journal_api_url}")

    headers.update({"Authorization": f"Bearer {bugout_user.bugout_access_token}"})

    payload = {"name": journal_name}
    r = requests.post(journal_api_url, json=payload, headers=headers, timeout=3)
    r.raise_for_status()
    response = r.json()

    # Register the index under the bot index configurations
    # Note that, at this point, journal_api_url should already have a trailing slash.
    index_url = f"{journal_api_url}{response['id']}/search"
    index = ObjIndexConfiguration(
        github_oauth_event_id=bot_installation.id,
        index_name=index_name,
        index_url=index_url,
        description=("This is your github team journal."),
        use_bugout_auth=True,
        use_bugout_client_id=True,
    )
    db_session.add(index)
    db_session.commit()

    index_configuration = Index(
        index_name=index.index_name,
        index_url=index.index_url,
        description=index.description,
        use_bugout_auth=index.use_bugout_auth,
        use_bugout_client_id=index.use_bugout_client_id,
    )

    return index_configuration
