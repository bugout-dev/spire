import logging
from typing import Any, cast, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy.orm import Session
import requests

from .data import HumbugEventDependencies, HumbugReport
from .models import HumbugEvent, HumbugBugoutUser, HumbugBugoutUserToken
from ..broodusers import bugout_api, BugoutAPICallFailed
from ..utils.settings import (
    INSTALLATION_TOKEN,
    BOT_INSTALLATION_TOKEN_HEADER,
    auth_url_from_env,
)

logger = logging.getLogger(__name__)

brood_url = auth_url_from_env()


class JournalInvalidParameters(ValueError):
    """
    Raised when operations are applied to a journal but invalid parameters are provided with which to
    specify that journal.
    """


class HumbugEventNotFound(Exception):
    """
    Raised on actions that involve integration which are not present in the database.
    """


class HumbugUserNotFound(Exception):
    """
    Raised on actions that involve humbug user which are not present in the database.
    """


class HumbugTokenNotFound(Exception):
    """
    Raised on actions that involve humbug token which are not present in the database.
    """


public_user_permission_at_journal = ["journals.read", "journals.entries.create"]


def generate_humbug_dependencies(
    token: UUID, group_id: str, journal_name: str
) -> HumbugEventDependencies:
    """
    Check if provided journal exists, if doesn't it creates new one, generate 
    new autogenerated user and add him to journal with restricted permissions, 
    add provided group to journal with full permissions.
    """
    try:
        journal = bugout_api.create_journal(
            token=token, name=journal_name, journal_type="humbug"
        )
    except Exception as e:
        logger.error(f"An error occured due journal creation -- {str(e)}")
        raise BugoutAPICallFailed(
            "Unable to complete Humbug integration workflow with Bugout API"
        )

    try:
        generated_password: str = str(uuid4())
        username = f"humbug-{group_id}-{str(journal.id)}"
        email = f"{username}@bugout.dev"

        installation_token_header = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}

        bugout_user = bugout_api.create_user(
            username, email, generated_password, headers=installation_token_header
        )
        bugout_access_token = bugout_api.create_token(
            username=bugout_user.username, password=generated_password
        )
    except Exception as e:
        logger.error(
            f"An error occured due autogenerated user being created or retrieving group at Brood -- {str(e)}"
        )
        raise BugoutAPICallFailed(
            "Unable to complete Humbug integration workflow with Bugout API"
        )

    try:
        bugout_api.update_journal_scopes(
            token=token,
            journal_id=journal.id,
            holder_type="user",
            holder_id=bugout_user.id,
            permission_list=public_user_permission_at_journal,
        )
    except Exception as e:
        bugout_api.delete_user(
            token=bugout_access_token.id,
            user_id=bugout_user.id,
            headers=installation_token_header,
        )
        logger.error(
            f"An error occured due adding autogenerated user to journal holders -- {str(e)}"
        )
        raise BugoutAPICallFailed(
            "Unable to complete Humbug integration workflow with Bugout API"
        )

    try:
        url = f"{brood_url}/subscriptions/manage"
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "group_id": group_id,
            "units_required": -1,
            "plan_type": "events",
        }

        r = requests.post(url=url, headers=headers, data=data, timeout=5)
        r.raise_for_status()
    except Exception as e:
        logger.info(
            f"Group already contains proper free subscriptions or unexpected error -- {str(e)}"
        )

    try:
        bugout_api.update_journal_scopes(
            token=token,
            journal_id=journal.id,
            holder_type="group",
            holder_id=group_id,
            permission_list=[
                "journals.read",
                "journals.update",
                "journals.entries.create",
                "journals.entries.read",
                "journals.entries.update",
                "journals.entries.delete",
            ],
        )
    except Exception as e:
        logger.info(
            f"Group was already added to journal or unexpected error -- {str(e)}"
        )

    humbug_event_dependencies = HumbugEventDependencies(
        group_id=group_id,
        journal_id=journal.id,
        journal_name=journal.name,
        user_id=bugout_user.id,
        access_token_id=bugout_access_token.id,
    )
    return humbug_event_dependencies


async def remove_humbug_dependencies(
    db_session: Session, token: UUID, humbug_event: HumbugEvent,
) -> None:
    """
    Delete autogenerated user and remove it from journal holders.
    """
    bugout_user = humbug_event.bugout_user
    installation_token_header = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}
    try:
        bugout_api.delete_journal_scopes(
            token=token,
            journal_id=humbug_event.journal_id,
            holder_type="user",
            holder_id=bugout_user.user_id,
            permission_list=public_user_permission_at_journal,
        )
        bugout_api.delete_user(
            token=bugout_user.access_token_id,
            user_id=bugout_user.user_id,
            headers=installation_token_header,
        )
    except Exception as e:
        logger.error(
            f"An error occured due humbug autogenerated user delition workflow -- {str(e)}"
        )
        raise BugoutAPICallFailed(
            "Unable to complete Humbug integration deletion workflow with Bugout AP"
        )

    humbug_group_events = (
        db_session.query(HumbugEvent)
        .filter(HumbugEvent.group_id == humbug_event.group_id)
        .all()
    )
    if len(humbug_group_events) == 0:
        try:
            url = f"{brood_url}/subscriptions/manage"
            headers = {"Authorization": f"Bearer {token}"}
            data = {"group_id": humbug_event.group_id, "plan_type": "events"}

            r = requests.delete(url=url, headers=headers, data=data, timeout=5)
            r.raise_for_status()
        except Exception as e:
            logger.info(
                f"Unable to delete group subscription or unexpected error -- {str(e)}"
            )


async def get_humbug_integration(
    db_session: Session, humbug_id: UUID, groups_ids: List[UUID]
) -> HumbugEvent:
    query = db_session.query(HumbugEvent).filter(
        HumbugEvent.group_id.in_(groups_ids), HumbugEvent.id == humbug_id
    )
    humbug_event = query.one_or_none()
    if humbug_event is None:
        raise HumbugEventNotFound("Humbug integration not found in database")

    return humbug_event


async def get_journal_id_by_restricted_token(
    db_session: Session, restricted_token: UUID
) -> UUID:
    """
    Return journal uuid by given restricted token
    """

    journal_id = (
        db_session.query(HumbugEvent.journal_id)
        .join(HumbugBugoutUserToken, HumbugEvent.id == HumbugBugoutUserToken.event_id)
        .filter(HumbugBugoutUserToken.restricted_token_id == restricted_token)
        .one_or_none()
    )
    if journal_id is None:
        raise HumbugEventNotFound("Humbug integration not found in database")

    return journal_id[0]


async def get_humbug_integrations(
    db_session: Session, groups_ids: List[UUID]
) -> List[HumbugEvent]:
    """
    Return list of Humbug integrations for provided group or for all groups
    user belong to.
    """
    query = db_session.query(HumbugEvent).filter(HumbugEvent.group_id.in_(groups_ids))
    humbug_events = query.all()

    if len(humbug_events) == 0:
        raise HumbugEventNotFound("Humbug integration not found in database")

    return humbug_events


async def create_humbug_integration(
    db_session: Session, journal_id: UUID, group_id: UUID
) -> HumbugEvent:
    """
    Create new record in HumbugEvent table.
    """
    humbug_event = HumbugEvent(group_id=group_id, journal_id=journal_id)
    db_session.add(humbug_event)
    db_session.commit()

    return humbug_event


async def delete_humbug_integration(
    db_session: Session, event_id: UUID, groups_ids: List[UUID]
) -> HumbugEvent:
    """
    Delete Humbug integration.
    """
    humbug_event = (
        db_session.query(HumbugEvent)
        .filter(HumbugEvent.group_id.in_(groups_ids), HumbugEvent.id == event_id)
        .one_or_none()
    )
    if humbug_event is None:
        raise HumbugEventNotFound("Humbug integration not found in database")

    db_session.delete(humbug_event)
    db_session.commit()

    return humbug_event


async def get_humbug_user(db_session: Session, event_id: UUID) -> HumbugBugoutUser:
    humbug_user = (
        db_session.query(HumbugBugoutUser)
        .filter(HumbugBugoutUser.event_id == event_id)
        .one_or_none()
    )
    if humbug_user is None:
        raise HumbugUserNotFound("Humbug user not found in database")

    return humbug_user


async def create_humbug_user(
    db_session: Session, event_id: UUID, user_id: UUID, access_token_id: UUID
) -> HumbugBugoutUser:
    """
    Create bugout autogenerated user for Humbug integration.
    """
    new_humbug_user = HumbugBugoutUser(
        user_id=user_id, access_token_id=access_token_id, event_id=event_id,
    )
    db_session.add(new_humbug_user)
    db_session.commit()

    return new_humbug_user


async def get_humbug_tokens(
    db_session: Session, event_id: UUID, user_id: UUID
) -> List[HumbugBugoutUserToken]:
    """
    Return list of restricted tokens.
    """
    humbug_tokens = (
        db_session.query(HumbugBugoutUserToken)
        .filter(
            HumbugBugoutUserToken.event_id == event_id,
            HumbugBugoutUserToken.user_id == user_id,
        )
        .all()
    )

    return humbug_tokens


async def create_humbug_token(
    db_session: Session,
    token: UUID,
    humbug_user: HumbugBugoutUser,
    app_name: str,
    app_version: str,
) -> HumbugBugoutUserToken:
    """
    Make API call to Brood and save to database restricted token.
    """
    restricted_token = bugout_api.create_token_restricted(token)
    assert restricted_token.restricted == True

    restricted_token_id = cast(UUID, restricted_token.id)
    new_humbug_token = HumbugBugoutUserToken(
        restricted_token_id=restricted_token_id,
        event_id=humbug_user.event_id,
        user_id=humbug_user.user_id,
        app_name=app_name,
        app_version=app_version,
    )
    db_session.add(new_humbug_token)
    db_session.commit()

    return new_humbug_token


async def delete_humbug_token(
    db_session: Session, humbug_event: HumbugEvent, restricted_token_id: UUID
):
    query = db_session.query(HumbugBugoutUserToken).filter(
        HumbugBugoutUserToken.event_id == humbug_event,
        HumbugBugoutUserToken.restricted_token_id == restricted_token_id,
    )
    restricted_token = query.one_or_none()
    if restricted_token is None:
        raise HumbugTokenNotFound("Provided restricted token id not found for user")

    humbug_user = (
        db_session.query(HumbugBugoutUser)
        .filter(HumbugBugoutUser.user_id == restricted_token.user_id)
        .first()
    )
    bugout_api.revoke_token(
        token=humbug_user.access_token_id,
        target_token=restricted_token.restricted_token_id,
    )
    db_session.delete(restricted_token)
    db_session.commit()

    return restricted_token


async def create_report(restricted_token: UUID, journal_id: UUID, report: HumbugReport):
    tags = list(set(report.tags))
    tags.append(f"reporter_token:{str(restricted_token)}")
    try:
        entry = bugout_api.create_entry(
            token=restricted_token,
            journal_id=journal_id,
            title=report.title,
            content=report.content,
            context_type="humbug",
            context_id=str(restricted_token),
            tags=tags,
        )
    except Exception as e:
        logger.error(f"An error occured due creating entry: {str(e)}")
        raise BugoutAPICallFailed("Unable create entry.")
