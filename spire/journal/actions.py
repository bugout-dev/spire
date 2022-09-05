"""
Journal-related actions in Spire
"""
from asyncio import streams
from datetime import date, timedelta, datetime
import calendar
import json
import logging
import os
import time
from typing import Any, Dict, List, Set, Optional, Tuple, Union
from uuid import UUID, uuid4

import boto3

from sqlalchemy.orm import Session, Query
from sqlalchemy import or_, func, text, and_
from sqlalchemy.dialects import postgresql


from .data import (
    JournalScopes,
    JournalEntryScopes,
    CreateJournalRequest,
    JournalSpec,
    JournalStatisticsSpecs,
    CreateJournalEntryRequest,
    JournalEntryListContent,
    CreateJournalEntryTagRequest,
    JournalSearchResultsResponse,
    JournalStatisticsResponse,
    UpdateJournalSpec,
    ListJournalEntriesResponse,
    JournalEntryResponse,
    JournalPermission,
    ContextSpec,
)
from .models import (
    Journal,
    JournalEntry,
    JournalEntryLock,
    JournalEntryTag,
    JournalPermissions,
    HolderType,
    SpireOAuthScopes,
)
from ..utils.confparse import scope_conf
from ..broodusers import bugout_api

logger = logging.getLogger(__name__)


class JournalNotFound(Exception):
    """
    Raised on actions that involve journals which are not present in the database.
    """


class InvalidJournalSpec(ValueError):
    """
    Raised when an invalid journal query is specified.
    """


class EntryNotFound(Exception):
    """
    Raised on actions that involve journal entries which are not present in the database.
    """


class EntryLocked(Exception):
    """
    Raised on actions when entry is not released for editing by other users.
    """


class PermissionsNotFound(Exception):
    """
    Raised on actions that involve permissions for journal or entry which are not present in the database.
    """


class PermissionAlreadyExists(Exception):
    """
    Raised when permission already exists in database.
    """


class InvalidParameters(ValueError):
    """
    Raised when operations are applied to a user/group permissions but invalid parameters are provided.
    """


def acl_auth(
    db_session: Session, user_id: str, user_group_id_list: List[str], journal_id: UUID
) -> Tuple[Journal, Dict[HolderType, List[str]]]:
    """
    Checks the authorization in JournalPermissions model. If it represents
    a verified user or group user belongs to and generates dictionary with
    permissions for user and group. Otherwise raises a 403 error.
    """
    acl: Dict[HolderType, List[str]] = {
        HolderType.user: [],
        HolderType.group: [],
    }

    objects = (
        db_session.query(Journal, JournalPermissions)
        .join(Journal, Journal.id == JournalPermissions.journal_id)
        .filter(JournalPermissions.journal_id == journal_id)
        .filter(
            or_(
                JournalPermissions.holder_id == user_id,
                JournalPermissions.holder_id.in_(user_group_id_list),
            )
        )
        .all()
    )

    if len(objects) == 0:
        raise PermissionsNotFound(f"No permissions for requested information")

    journal = objects[0][0]
    journal_permissions = []
    for object in objects:
        if object[0] != journal != journal_id:
            logger.error(
                f"Unexpected journal {object[0].id} in journal permissions for journal {journal_id}"
            )
            raise Exception("Unexpected journal in journal permissions")
        if object[1] is not None:
            journal_permissions.append(object[1])

    if len(journal_permissions) == 0:
        raise PermissionsNotFound("No permissions for requested information")

    acl[HolderType.user].extend(
        [
            journal_permission.permission
            for journal_permission in journal_permissions
            if journal_permission.holder_type == HolderType.user
        ]
    )
    acl[HolderType.group].extend(
        [
            journal_permission.permission
            for journal_permission in journal_permissions
            if journal_permission.holder_type == HolderType.group
        ]
    )

    return journal, acl


def acl_check(
    acl: Dict[HolderType, List[str]],
    required_scopes: Set[Union[JournalScopes, JournalEntryScopes]],
    check_type: HolderType = None,
) -> None:
    """
    Checks if provided scopes from handler intersect with existing permissions for user/group
    """
    if check_type is None:
        # [["read", "update"], ["update"]] -> ["read", "update"]
        permissions = {value for values in acl.values() for value in values}
    elif check_type in HolderType:
        permissions = {value for value in acl[check_type]}
    else:
        logger.warning("Provided wrong HolderType")
        raise PermissionsNotFound("No permissions for requested information")

    required_scopes_values = {scope.value for scope in required_scopes}
    if not required_scopes_values.issubset(permissions):
        raise PermissionsNotFound("No permissions for requested information")


async def find_journals(
    db_session: Session, user_id: UUID, user_group_id_list: List[str] = None
) -> List[Journal]:
    """
    Return list of journals for requested user.
    """
    query = (
        db_session.query(
            Journal.id,
            Journal.bugout_user_id,
            func.array_agg(JournalPermissions.holder_id).label("holders_ids"),
            Journal.name,
            Journal.created_at,
            Journal.updated_at,
        )
        .join(JournalPermissions, JournalPermissions.journal_id == Journal.id)
        .join(SpireOAuthScopes, JournalPermissions.permission == SpireOAuthScopes.scope)
        .filter(SpireOAuthScopes.api == "journals", Journal.deleted == False)
        .filter(JournalPermissions.permission == JournalScopes.READ.value)
        .filter(
            or_(
                Journal.bugout_user_id == user_id,
                JournalPermissions.holder_id.in_(user_group_id_list),
                JournalPermissions.holder_id == user_id,
            )
        )
        .group_by(
            Journal.id,
            Journal.bugout_user_id,
            Journal.name,
            Journal.created_at,
            Journal.updated_at,
        )
    )

    journals = query.all()
    if journals is None:
        raise JournalNotFound(f"Did not find journals for user_id: {user_id}")

    return journals


async def find_journal(
    db_session: Session,
    journal_spec: JournalSpec,
    user_group_id_list: List[str] = None,
    deleted: bool = False,
) -> Journal:
    """
    Validates journal spec to make sure that, if the journal id is not specified, both the
    name and bugout_user_id are specified.

    If the journal spec is invalid, raises an InvalidJournalSpec error.

    If the spec is valid, looks for a single journal that matches the spec. If there are multiple
    journals matching the spec, raises an error. If there are no journals matching the spec, raises
    JournalNotFound. Otherwise returns the matching journal.
    """
    try:
        assert journal_spec.id is not None or (
            journal_spec.bugout_user_id is not None and journal_spec.name is not None
        )
    except:
        raise InvalidJournalSpec(
            "If journal id is not specified, specify both bugout_user_id and name."
        )

    query = (
        db_session.query(Journal)
        .outerjoin(JournalPermissions, JournalPermissions.journal_id == Journal.id)
        .filter(Journal.deleted == deleted)
    )

    if journal_spec.id is not None:
        query = query.filter(Journal.id == journal_spec.id)

    if journal_spec.bugout_user_id is not None and user_group_id_list is None:
        query = query.filter(
            or_(
                Journal.bugout_user_id == journal_spec.bugout_user_id,
                JournalPermissions.holder_id == journal_spec.bugout_user_id,
            )
        )

    if journal_spec.bugout_user_id is not None and user_group_id_list is not None:
        query = query.filter(
            or_(
                Journal.bugout_user_id == journal_spec.bugout_user_id,
                JournalPermissions.holder_id.in_(user_group_id_list),
                JournalPermissions.holder_id == journal_spec.bugout_user_id,
            )
        )

    if journal_spec.name is not None:
        query = query.filter(Journal.name == journal_spec.name)

    journal = query.one_or_none()
    if journal is None:
        raise JournalNotFound(
            f"Did not find journal with specification: {repr(journal_spec)}"
        )

    return journal


async def create_journal(
    db_session: Session, journal_request: CreateJournalRequest
) -> Journal:
    """
    Creates the journal specified by the journal_request in the database represented by db_session.
    Returns nothing.
    """
    # Create new journal
    journal = Journal(
        bugout_user_id=journal_request.bugout_user_id,
        name=journal_request.name,
        search_index=journal_request.search_index,
    )
    db_session.add(journal)
    db_session.commit()

    # Extract all possible permissions from OAuthScopes for journal
    journal_scopes = (
        db_session.query(SpireOAuthScopes)
        .filter(SpireOAuthScopes.api == "journals")
        .all()
    )

    # Create journal permissions
    for journal_scope in journal_scopes:
        journal_p = JournalPermissions(
            holder_type=HolderType.user,
            journal_id=journal.id,
            holder_id=journal_request.bugout_user_id,
            permission=journal_scope.scope,
        )
        db_session.add(journal_p)
    db_session.commit()

    return journal


async def update_journal(
    db_session: Session,
    journal_spec: JournalSpec,
    update_spec: UpdateJournalSpec,
    user_group_id_list: List[str] = None,
) -> Journal:
    """
    Updates a journal object in the database. If the record to be updated does not exist, raises a
    JournalNotFound error. If either the journal specification or the update specification is
    invalid, raises an InvalidJournalSpec error.
    """
    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )

    if update_spec.name is not None:
        journal.name = update_spec.name

    db_session.add(journal)
    db_session.commit()
    return journal


async def delete_journal(
    db_session: Session, journal_spec: JournalSpec, user_group_id_list: List[str] = None
) -> Journal:
    """
    Deletes the given journal from the database. If there is no journal with that ID, raises a
    JournalNotFound exception. Returns a journal specification corresponding to the journal that was
    deleted.
    """
    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )
    db_session.query(Journal).filter(Journal.id == journal.id).update(
        {Journal.deleted: True}
    )
    db_session.commit()
    return journal


async def journal_statistics(
    db_session: Session,
    journal_spec: JournalSpec,
    stats_spec: JournalStatisticsSpecs,
    tags: List[str],
    user_group_id_list: List[str] = None,
) -> JournalStatisticsResponse:

    """
    Return journals statistics.
    For now just amount of entries for default periods.
    Use tags interseptions if tags is not empty for num of entries excluding estimate calculation
    """

    stats_response_body: Dict[str, Any] = {"num_entries": {}, "most_used_tags": {}}

    stats = [key for key, value in stats_spec if value]

    if not stats:
        stats = [key for key, value in stats_spec]

    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )

    if tags:
        entries_query = _query_entries_by_tags_intersection(
            db_session=db_session, journal_id=str(journal.id), tags=tags
        )
    else:
        entries_query = db_session.query(JournalEntry.id).filter(
            JournalEntry.journal_id == journal.id
        )

    try:
        if "entries_total" in stats:
            stats_response_body["num_entries"]["total"] = entries_query.count()
    except Exception as err:
        logger.error(f"Statistics: get total: {err}")
        stats_response_body["num_entries"]["total"] = None

    try:
        if "entries_hour" in stats:
            created_at_last_hour = entries_query.filter(
                JournalEntry.created_at > datetime.utcnow() - timedelta(hours=1)
            )
            stats_response_body["num_entries"]["hour"] = created_at_last_hour.count()
    except Exception as err:
        logger.error(f"Statistics: get hour: {err}")
        stats_response_body["num_entries"]["hour"] = None

    try:
        if "entries_day" in stats:
            created_at_last_day = entries_query.filter(
                JournalEntry.created_at > datetime.utcnow() - timedelta(days=1)
            )
            stats_response_body["num_entries"]["day"] = created_at_last_day.count()
    except Exception as err:
        logger.error(f"Statistics: get day: {err}")
        stats_response_body["num_entries"]["day"] = None

    try:
        if "entries_week" in stats:
            created_at_last_week = entries_query.filter(
                JournalEntry.created_at > datetime.utcnow() - timedelta(days=7)
            )
            stats_response_body["num_entries"]["week"] = created_at_last_week.count()
    except Exception as err:
        logger.error(f"Statistics: get week: {err}")
        stats_response_body["num_entries"]["week"] = None

    # estimated (sum(entries)/days_so_far)*days in mounth
    current_timestamp = datetime.utcnow()

    # start of current month timestamp
    start_of_month_timestamp = date(current_timestamp.year, current_timestamp.month, 1)

    try:
        if "entries_month" in stats:
            created_at_last_month = entries_query.filter(
                func.DATE(JournalEntry.created_at)
                > datetime.utcnow() - timedelta(days=28)
            )
            stats_response_body["num_entries"]["month"] = created_at_last_month.count()
    except Exception as err:
        logger.error(f"Statistics: get month: {err}")
        stats_response_body["num_entries"]["month"] = None

    # get total days in month
    days_in_month = calendar.monthrange(
        current_timestamp.year, current_timestamp.month
    )[1]

    try:
        full_count = (
            db_session.query(JournalEntry)
            .filter(JournalEntry.journal_id == journal.id)
            .filter(JournalEntry.created_at > start_of_month_timestamp)
            .count()
        )
        day_of_last_created_entry = (
            db_session.query(func.DATE(func.max(JournalEntry.created_at)))
            .filter(JournalEntry.journal_id == journal.id)
            .filter(JournalEntry.created_at > start_of_month_timestamp)
            .one()[0]
        )
        if day_of_last_created_entry:
            stats_response_body["num_entries"]["estimated"] = int(
                full_count / day_of_last_created_entry.day * days_in_month
            )
        else:
            stats_response_body["num_entries"]["estimated"] = None

    except Exception as err:
        logger.error(f"Statistics: get estimated: {err}")
        stats_response_body["num_entries"]["estimated"] = None

    return JournalStatisticsResponse(num_of_entries=stats_response_body["num_entries"])


async def create_journal_entry(
    db_session: Session,
    journal: Journal,
    entry_request: CreateJournalEntryRequest,
    locked_by: str,
) -> Tuple[JournalEntry, JournalEntryLock]:
    """
    Creates an entry in a given journal. Raises InvalidJournalSpec error if the journal is
    misspecified in the creation request, and raises a JournalNotFound error if no such journal
    is found in the database.
    """
    commit_list = []

    entry_id = uuid4()
    entry = JournalEntry(
        id=entry_id,
        journal_id=journal.id,
        title=entry_request.title,
        content=entry_request.content,
        context_id=entry_request.context_id,
        context_url=entry_request.context_url,
        context_type=entry_request.context_type,
        created_at=entry_request.created_at,
    )
    commit_list.append(entry)

    entry_lock = JournalEntryLock(journal_entry_id=entry_id, locked_by=locked_by)
    commit_list.append(entry_lock)

    if entry_request.tags is not None:
        tags = [
            JournalEntryTag(journal_entry_id=entry.id, tag=tag)
            for tag in entry_request.tags
            if tag
        ]
        commit_list.extend(tags)

    db_session.add_all(commit_list)
    db_session.commit()

    return entry, entry_lock


async def create_journal_entries_pack(
    db_session: Session,
    journal_id: UUID,
    entries_pack_request: JournalEntryListContent,
) -> ListJournalEntriesResponse:
    """
    Bulk pack of entries to database.
    """
    entries_response = ListJournalEntriesResponse(entries=[])

    chunk_size = 50
    chunks = [
        entries_pack_request.entries[i : i + chunk_size]
        for i in range(0, len(entries_pack_request.entries), chunk_size)
    ]
    logger.info(
        f"Entries pack split into to {len(chunks)} chunks for journal {str(journal_id)}"
    )
    for chunk in chunks:
        entries_pack = []
        entries_tags_pack = []

        for entry_request in chunk:
            entry_id = uuid4()
            entries_pack.append(
                JournalEntry(
                    id=entry_id,
                    journal_id=journal_id,
                    title=entry_request.title,
                    content=entry_request.content,
                    context_id=entry_request.context_id,
                    context_url=entry_request.context_url,
                    context_type=entry_request.context_type,
                    created_at=entry_request.created_at,
                )
            )
            if entry_request.tags is not None:
                entries_tags_pack += [
                    JournalEntryTag(journal_entry_id=entry_id, tag=tag)
                    for tag in entry_request.tags
                    if tag
                ]

            entries_response.entries.append(
                JournalEntryResponse(
                    id=entry_id,
                    title=entry_request.title,
                    content=entry_request.content,
                    tags=entry_request.tags if entry_request.tags is not None else [],
                    context_url=entry_request.context_url,
                    context_type=entry_request.context_type,
                    context_id=entry_request.context_id,
                    created_at=entry_request.created_at,
                )
            )

        db_session.bulk_save_objects(entries_pack)
        db_session.commit()
        db_session.bulk_save_objects(entries_tags_pack)
        db_session.commit()

        # Append created_at and updated_at from fresh rows from database
        # TODO(kompotkot): Datetime now not returned from bult_save_objects()
        for entry in [
            e1
            for e1 in entries_response.entries
            if e1.id in [e2.id for e2 in entries_pack]
        ]:
            entry.created_at = list(filter(lambda x: x.id == entry.id, entries_pack))[
                0
            ].created_at
            entry.updated_at = list(filter(lambda x: x.id == entry.id, entries_pack))[
                0
            ].updated_at

    return entries_response


async def get_journal_entries(
    db_session: Session,
    journal_spec: JournalSpec,
    entry_id: Optional[UUID],
    user_group_id_list: List[str] = None,
    context_spec: Optional[ContextSpec] = None,
    limit: Optional[int] = 10,
    offset: int = 0,
) -> List[JournalEntry]:
    """
    Returns a list of journal entries corresponding to the specified journal. If you specify an
    entry_id, returns that specific entry (still in a list).
    """
    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )
    query = db_session.query(JournalEntry).filter(JournalEntry.journal_id == journal.id)
    if entry_id is not None:
        query = query.filter(JournalEntry.id == entry_id)
    if context_spec is not None:
        if context_spec.context_type is not None:
            query = query.filter(JournalEntry.context_type == context_spec.context_type)
        if context_spec.context_id is not None:
            query = query.filter(JournalEntry.context_id == context_spec.context_id)
        if context_spec.context_url is not None:
            query = query.filter(JournalEntry.context_url == context_spec.context_url)
    query = query.order_by(JournalEntry.created_at)
    query = query.limit(limit).offset(offset)
    return query.all()


async def get_journal_entry(
    db_session: Session, journal_entry_id: UUID
) -> Optional[JournalEntry]:
    """
    Returns a journal entry by its id.
    """
    journal_entry = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.id == journal_entry_id)
        .one_or_none()
    )
    return journal_entry


async def get_journal_entry_with_tags(
    db_session: Session, journal_entry_id: UUID
) -> Tuple[JournalEntry, List[JournalEntryTag], JournalEntryLock]:
    """
    Returns a journal entry by its id with tags.
    """
    objects = (
        db_session.query(JournalEntry, JournalEntryTag, JournalEntryLock)
        .join(
            JournalEntryTag,
            JournalEntryTag.journal_entry_id == JournalEntry.id,
            isouter=True,
        )
        .join(
            JournalEntryLock,
            JournalEntryLock.journal_entry_id == JournalEntry.id,
            isouter=True,
        )
        .filter(JournalEntry.id == journal_entry_id)
        .all()
    )
    if len(objects) == 0:
        raise EntryNotFound("Entry not found")

    entry = objects[0][0]
    entry_lock = objects[0][2]
    tags: List[JournalEntryTag] = []
    for object in objects:
        if object[1] is not None:
            tags.append(object[1])

    return entry, tags, entry_lock


async def update_journal_entry(
    db_session: Session,
    new_title: str,
    new_content: str,
    locked_by: str,
    journal_entry: JournalEntry,
    entry_lock: Optional[JournalEntryLock] = None,
) -> Tuple[JournalEntry, JournalEntryLock]:
    """
    Updates existing journal entry content.
    If lock does not exist, it creates new, otherwise update timestamp.
    """
    commit_list = []
    update_timestamp = datetime.utcnow()

    journal_entry.title = new_title
    journal_entry.content = new_content
    journal_entry.updated_at = update_timestamp

    commit_list.append(journal_entry)

    if entry_lock is None:
        entry_lock = JournalEntryLock(
            journal_entry_id=journal_entry.id, locked_by=locked_by
        )
    entry_lock.locked_at = update_timestamp
    commit_list.append(entry_lock)

    db_session.add_all(commit_list)
    db_session.commit()

    return journal_entry, entry_lock


async def delete_journal_entry(
    db_session: Session,
    journal: Journal,
    entry_id: Optional[UUID],
) -> JournalEntry:
    """
    Deletes the given journal entry.
    """
    query = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.journal_id == journal.id)
        .filter(JournalEntry.id == entry_id)
    )
    entry = query.one_or_none()
    if entry is None:
        raise EntryNotFound(
            f"Could not find the journal entry with id: {str(entry_id)}"
        )

    db_session.delete(entry)
    db_session.commit()
    return entry


async def delete_journal_entries(
    db_session: Session,
    journal_spec: JournalSpec,
    entry_ids: List[UUID],
    user_group_id_list: List[str] = None,
) -> ListJournalEntriesResponse:
    """
    Deletes the given journal entries.
    """

    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )
    query = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.journal_id == journal.id)
        .filter(JournalEntry.id.in_(entry_ids))
    )

    entries = query.all()
    entries_response = ListJournalEntriesResponse(entries=[])
    for entry in entries:
        entries_response.entries.append(
            JournalEntryResponse(
                id=entry.id,
                title=entry.title,
                content=entry.content,
                context_url=entry.context_url,
                context_type=entry.context_type,
                context_id=entry.context_id,
            )
        )

    if not entries:
        raise EntryNotFound(
            f"Could not find entries {entries} in that journal: {str(journal.id)}"
        )

    query.delete(synchronize_session="fetch")
    db_session.commit()

    return entries_response


def _query_entries_by_tags_intersection(
    db_session: Session, journal_id: str, tags: List[str]
) -> Query:
    """
    Return query for given tags intersection

    An example of a compiled request



    SELECT journal_entries.id AS journal_entries_id
    FROM journal_entries
    WHERE journal_entries.journal_id = %(journal_id_1)s
        AND (
            EXISTS (SELECT 1 FROM journal_entry_tags
                    WHERE journal_entries.id = journal_entry_tags.journal_entry_id
                                            AND journal_entry_tags.tag = %(tag_1)s
                    )
            )
        AND (
            EXISTS (SELECT 1 FROM journal_entry_tags
                    WHERE journal_entries.id = journal_entry_tags.journal_entry_id
                                            AND journal_entry_tags.tag = %(tag_2)s
                    )
            )
    """
    if not tags:
        # Empty list not aplied any filters and return all entries
        raise InvalidParameters("At least one tag must be specified")

    tag_existence_queries = [JournalEntry.tags.any(tag=tag) for tag in tags]

    query = (
        db_session.query(JournalEntry.id)
        .filter(JournalEntry.journal_id == journal_id)
        .filter(and_(*tag_existence_queries))
    )
    return query


async def hard_delete_by_tags(
    db_session: Session,
    journal_id: str,
    tags: List[str],
    limit: int,
    offset: int,
) -> List[UUID]:
    """
    Remove entries from database by tags intersection(AND condition)
    """

    query = (
        _query_entries_by_tags_intersection(db_session, journal_id, tags)
        .limit(limit)
        .offset(offset)
    )

    entries_ids = [entry_id[0] for entry_id in query.all()]

    query = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.journal_id == journal_id)
        .filter(JournalEntry.id.in_(entries_ids))
    )

    query.delete(synchronize_session="fetch")
    db_session.commit()

    return entries_ids


async def get_entries_count_by_tags(
    db_session: Session, journal_id: str, tags: List[str]
) -> int:
    """
    Return amount of entries for given tags intersection

    Have more faster way for sqlalchemy count : https://gist.github.com/hest/8798884
    """
    amount = _query_entries_by_tags_intersection(db_session, journal_id, tags).count()

    return amount


async def get_journal_most_used_tags(
    db_session: Session,
    journal_spec: JournalSpec,
    user_group_id_list: List[str] = None,
    limit: int = 7,
) -> List[Any]:
    """
    Returns a list of tags for a given entry.
    """

    journal = await find_journal(
        db_session=db_session,
        journal_spec=journal_spec,
        user_group_id_list=user_group_id_list,
    )
    query = (
        db_session.query(
            JournalEntryTag.tag, func.count(JournalEntryTag.tag).label("total")
        )
        .join(JournalEntry)
        .join(Journal)
        .filter(Journal.id == journal.id)
        .order_by(text("total DESC"))
        .group_by(JournalEntryTag.tag)
        .limit(limit)
    )
    return query.all()


async def create_journal_entry_tags(
    db_session: Session,
    journal: Journal,
    tag_request: CreateJournalEntryTagRequest,
) -> List[JournalEntryTag]:
    """
    Tags the given journal entry.
    """
    query = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.journal_id == journal.id)
        .filter(JournalEntry.id == tag_request.journal_entry_id)
    )
    entry = query.one_or_none()
    if entry is None:
        raise EntryNotFound("Could not find the given entry")

    # Need check how do it in one request
    query = db_session.query(JournalEntryTag).filter(
        JournalEntryTag.journal_entry_id == tag_request.journal_entry_id
    )
    exists_tags = [tag.tag for tag in query.all()]

    # Add new tags
    new_tags = [
        JournalEntryTag(journal_entry_id=entry.id, tag=tag)
        for tag in tag_request.tags
        if tag not in exists_tags
    ]

    if new_tags:
        db_session.add_all(new_tags)
        db_session.commit()

    return new_tags


async def get_journal_entry_tags(
    db_session: Session,
    journal_spec: JournalSpec,
    entry_id: UUID,
    user_group_id_list: List[str] = None,
) -> List[JournalEntryTag]:
    """
    Returns a list of tags for a given entry.
    """
    # Checks that the authenticated user is authorized to work with the given journal and that the
    # entry exists.
    entries = await get_journal_entries(
        db_session, journal_spec, entry_id, user_group_id_list=user_group_id_list
    )
    if len(entries) == 0:
        raise EntryNotFound()
    assert len(entries) == 1

    query = db_session.query(JournalEntryTag).filter(
        JournalEntryTag.journal_entry_id == entry_id
    )

    return query.all()


async def update_journal_entry_tags(
    db_session: Session,
    journal: Journal,
    entry_id: UUID,
    tag_request: CreateJournalEntryTagRequest,
) -> List[JournalEntryTag]:
    query = (
        db_session.query(JournalEntry)
        .filter(JournalEntry.journal_id == journal.id)
        .filter(JournalEntry.id == tag_request.journal_entry_id)
    )
    entry = query.one_or_none()
    if entry is None:
        raise EntryNotFound("Could not find the given entry")

    # Need check how do it in one request
    query = db_session.query(JournalEntryTag).filter(
        JournalEntryTag.journal_entry_id == entry_id
    )
    exists_tags = [tag.tag for tag in query.all()]

    # Add new tags
    new_tags = [
        JournalEntryTag(journal_entry_id=entry.id, tag=tag)
        for tag in tag_request.tags
        if tag not in exists_tags
    ]

    if new_tags:
        db_session.add_all(new_tags)

    # remove old tags
    query = (
        db_session.query(JournalEntryTag)
        .filter(JournalEntryTag.journal_entry_id == entry_id)
        .filter(JournalEntryTag.tag.notin_(tag_request.tags))
    )

    if query.first:
        query.delete(synchronize_session="fetch")

    db_session.commit()

    query = db_session.query(JournalEntryTag).filter(
        JournalEntryTag.journal_entry_id == entry_id
    )
    return query.all()


async def delete_journal_entry_tag(
    db_session: Session,
    journal_spec: JournalSpec,
    entry_id: UUID,
    tag: str,
    user_group_id_list: List[str] = None,
) -> Optional[JournalEntryTag]:
    """
    Delete the given tags from the given journal entry (all specified in the tag_request).
    """
    # Checks that the authenticated user is authorized to work with the given journal and that the
    # entry exists.
    entries = await get_journal_entries(
        db_session, journal_spec, entry_id, user_group_id_list=user_group_id_list
    )
    if len(entries) == 0:
        raise EntryNotFound()
    assert len(entries) == 1

    query = (
        db_session.query(JournalEntryTag)
        .filter(JournalEntryTag.journal_entry_id == entry_id)
        .filter(JournalEntryTag.tag == tag)
    )
    journal_entry_tag = query.one_or_none()
    if journal_entry_tag is not None:
        db_session.delete(journal_entry_tag)
        db_session.commit()
    return journal_entry_tag


def store_search_results(
    search_url: str,
    journal_id: UUID,
    bugout_user_id: str,
    bugout_client_id: Optional[str],
    q: str,
    filters: List[str],
    limit: int,
    offset: int,
    response: JournalSearchResultsResponse,
) -> None:
    """
    Stores search results on AWS S3 if the appropriate configuration is available in the environment
    """
    bucket = os.environ.get("AWS_S3_JOURNAL_SEARCH_RESULTS_BUCKET")
    prefix = os.environ.get("AWS_S3_JOURNAL_SEARCH_RESULTS_PREFIX", "").rstrip("/")
    if bucket is None:
        logger.warning(
            "AWS_S3_JOURNAL_SEARCH_RESULTS_BUCKET environment variable not defined, skipping storage of search results"
        )
        return

    current_time = int(time.time())
    result_id = f"{current_time}-{str(uuid4())}"
    logger.info(f"Storing search results at s3://{bucket}/{prefix}/{result_id}.json")

    result = {
        "search_url": search_url,
        "search_type": "journal",
        "bugout_user_id": bugout_user_id,
        "bugout_client_id": bugout_client_id,
        "q": q,
        "filters": filters,
        "limit": limit,
        "offset": offset,
        "response": response.dict(),
    }
    result_bytes = json.dumps(result).encode("utf-8")
    result_key = f"{prefix}/{result_id}.json"

    s3 = boto3.client("s3")
    s3.put_object(
        Body=result_bytes,
        Bucket=bucket,
        Key=result_key,
        ContentType="application/json",
        Metadata={"search_type": "journal"},
    )


async def get_scopes(db_session: Session, api: str) -> List[SpireOAuthScopes]:
    """
    Returns list of all scopes for provided api.
    """
    scopes = (
        db_session.query(SpireOAuthScopes).filter(SpireOAuthScopes.api == api).all()
    )
    return scopes


async def get_journal_scopes(
    db_session: Session, user_id: str, user_group_id_list: List[str], journal_id: UUID
) -> List[JournalPermissions]:
    """
    Returns list of all permissions (group user belongs to and user) for provided user and journal.
    """
    journal_spec = JournalSpec(id=journal_id)
    await find_journal(db_session, journal_spec)

    if journal_id is None:
        raise JournalNotFound(
            "In order to get journal permissions, journal_id must be specified"
        )
    query = db_session.query(JournalPermissions).filter(
        JournalPermissions.journal_id == journal_id
    )

    if user_id is None and user_group_id_list is None:
        raise InvalidParameters(
            "In order to get journal permissions, at least one of user_id, or user_group_id_list must be specified"
        )

    query = query.filter(
        or_(
            JournalPermissions.holder_id == user_id,
            JournalPermissions.holder_id.in_(user_group_id_list),
        )
    )

    journal_permissions = query.all()

    if not journal_permissions:
        raise PermissionsNotFound(f"No permissions for journal_id={journal_id}")

    return journal_permissions


async def get_journal_permissions(
    db_session: Session, journal_id: UUID, holder_ids: Optional[List[str]] = None
) -> List[JournalPermission]:
    query = (
        db_session.query(
            JournalPermissions.journal_id,
            JournalPermissions.holder_id,
            JournalPermissions.holder_type,
            postgresql.array_agg(JournalPermissions.permission),
        )
        .join(SpireOAuthScopes, JournalPermissions.permission == SpireOAuthScopes.scope)
        .filter(
            SpireOAuthScopes.api == "journals"
        )  # TODO(neeraj): Use a constant instead of "journals"
        .filter(JournalPermissions.journal_id == journal_id)
        .group_by(
            JournalPermissions.journal_id,
            JournalPermissions.holder_id,
            JournalPermissions.holder_type,
        )
    )
    if holder_ids is not None:
        query = query.filter(JournalPermissions.holder_id.in_(holder_ids))

    aggregated_permissions = query.all()
    results = [
        JournalPermission(
            holder_id=holder_id, holder_type=holder_type, permissions=permissions
        )
        for _, holder_id, holder_type, permissions in aggregated_permissions
    ]
    return results


async def update_journal_scopes(
    user_token: str,
    db_session: Session,
    holder_type: str,
    holder_id: str,
    permission_list: List[str],
    journal_id: UUID,
) -> List[str]:
    """
    User and group scopes can be added and only by user who belongs to this group
    and has access to proposed journal.
    """
    if journal_id is None or holder_id is None or permission_list is None:
        raise JournalNotFound(
            "In order to update journal permissions, all parameters should be specified"
        )
    journal_spec = JournalSpec(id=journal_id)
    await find_journal(db_session, journal_spec)

    # Check if user belong to group which one he wants to add to journal
    if holder_type == HolderType.group.value:
        try:
            bugout_api.find_group(group_id=holder_id, token=user_token)
        except Exception as e:
            logger.error(
                f"Error retrieving group from Brood: group_id={holder_id}, {str(e)}"
            )
            raise PermissionsNotFound("User can't find provided group")

    journal_permissions = (
        db_session.query(JournalPermissions)
        .filter(JournalPermissions.journal_id == journal_id)
        .filter(JournalPermissions.holder_id == holder_id)
        .all()
    )
    # Remove permissions already exists in database
    for journal_p in journal_permissions:
        if journal_p.permission in permission_list:
            permission_list.remove(journal_p.permission)

    if not permission_list:
        raise PermissionAlreadyExists(f"Provided permission already exist")

    for permission in permission_list:
        journal_p = JournalPermissions(
            holder_type=holder_type,
            journal_id=journal_id,
            holder_id=holder_id,
            permission=permission,
        )
        db_session.add(journal_p)
    db_session.commit()

    return permission_list


async def delete_journal_scopes(
    user_token: str,
    db_session: Session,
    holder_type: str,
    holder_id: str,
    permission_list: List[str],
    journal_id: UUID,
) -> List[str]:
    """
    Only group scopes can be deleted and only by user who belongs to this group
    and has access to proposed journal.
    """
    if journal_id is None or holder_id is None or permission_list is None:
        raise JournalNotFound(
            "In order to update journal permissions, all parameters should be specified"
        )
    journal_spec = JournalSpec(id=journal_id)
    await find_journal(db_session, journal_spec)

    # Check if user belong to group which one he wants to add to journal
    if holder_type == HolderType.group.value:
        try:
            bugout_api.find_group(group_id=holder_id, token=user_token)
        except Exception as e:
            logger.error(
                f"Error retrieving group from Brood: group_id={holder_id}, {str(e)}"
            )
            raise PermissionsNotFound("User can't find provided group")

    query = (
        db_session.query(JournalPermissions)
        .filter(JournalPermissions.journal_id == journal_id)
        .filter(JournalPermissions.holder_id == holder_id)
    )

    journal_permissions_delete = query.filter(
        JournalPermissions.permission.in_(permission_list)
    ).all()
    if not journal_permissions_delete:
        raise PermissionsNotFound(f"Provided permissions don't exist")

    for journal_p_delete in journal_permissions_delete:
        db_session.delete(journal_p_delete)

    db_session.commit()

    return permission_list
