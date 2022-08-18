"""
Journal search and search indices
"""
import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from typing import Any, Callable, Dict, Optional, List, Tuple, Union
from uuid import UUID

from dateutil.parser import parse as parse_datetime
import elasticsearch
from elasticsearch.client import IndicesClient
from elasticsearch.helpers import bulk
from sqlalchemy import and_, or_, not_, func
from sqlalchemy.sql.elements import BooleanClauseList
from sqlalchemy.orm import Session, Query


from . import actions
from .data import JournalSpec, JournalEntryResponse
from ..db import yield_connection_from_env
from ..es import es_client_from_env
from .models import Journal, JournalEntry, JournalEntryTag
from ..utils.settings import DEFAULT_JOURNALS_ES_INDEX, BULK_CHUNKSIZE

logger = logging.getLogger(__name__)


class IndexAlreadyExists(Exception):
    """
    Raised when an elasticsearch index already exists but is expected not to exist.
    """


def _index(index: Union[str, UUID]) -> str:
    """
    Name of index for a single journal.
    """
    return str(index)


def _index_p(es_client: elasticsearch.Elasticsearch, index_name: str) -> bool:
    """
    Checks if the given index exists.
    """
    indices = IndicesClient(es_client)
    return indices.exists(index_name)


def index_p(
    es_client: elasticsearch.Elasticsearch,
    index_id: Union[str, UUID],
    **kwargs,
):
    """
    Checks if an index exists for a given user and journal.
    """
    return _index_p(es_client, _index(index_id))


def drop_index(es_client: elasticsearch.Elasticsearch, es_index: str, **kwargs) -> str:
    """
    Drops an index on Elasticsearch cluster.
    """
    logger.info(f"Dropping index ({es_index})")
    indices = IndicesClient(es_client)
    indices.delete(es_index)
    return es_index


def index_docs_count(es_client: elasticsearch.Elasticsearch, es_index: str):
    return es_client.indices.stats(index=es_index)["indices"][es_index]["total"][
        "docs"
    ]["count"]


def create_index(
    es_client: elasticsearch.Elasticsearch,
    es_index: str,
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    force: bool = False,
    **kwargs,
) -> str:
    """
    Creates an index for a journal. Returns the index identifier.

    Documentation on how elsaticsearch chooses analyzers:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/specify-analyzer.html
    """
    index_name = _index(es_index)
    indices = IndicesClient(es_client)

    if indices.exists(index_name):
        logger.info(f"Index ({index_name}) already exists, force ({force})")
        if force:
            drop_index(es_client, index_name)
        else:
            logger.error(
                f"Cannot create index ({index_name}) because it already exists"
            )
            raise IndexAlreadyExists(index_name)

    logger.info(f"Creating index ({index_name})")
    # TODO(andrey), TODO(neeraj): We are not using gram_2_3_analyzer and gram_2_3_tokenizer for the
    # moment. Should we remove them or do we plan to use them in the future?
    body = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "default": {"type": "standard", "stopwords": "_english_"},
                    "default_search": {"type": "standard", "stopwords": "_english_"},
                    "gram_2_3_analyzer": {
                        "type": "custom",
                        "tokenizer": "gram_2_3_tokenizer",
                        "filter": ["lowercase"],
                    },
                },
                "tokenizer": {
                    "gram_2_3_tokenizer": {
                        "type": "ngram",
                        "min_gram": 2,
                        "max_gram": 3,
                        "token_chars": ["letter", "digit", "punctuation", "symbol"],
                    }
                },
            },
            "number_of_shards": 1,
            "number_of_routing_shards": 2,
        },
        "mappings": {
            "properties": {
                "journal_id": {"type": "keyword"},
                "title": {"type": "text"},
                "content": {"type": "text"},
                "tag": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
                "context_type": {"type": "keyword"},
                "context_id": {"type": "keyword"},
                "context_url": {"type": "keyword"},
            }
        },
    }
    indices.create(index_name, body=body)

    if created_at is None:
        created_at = datetime.utcnow()
    if updated_at is None:
        updated_at = created_at

    return index_name


def new_entry(
    es_client: elasticsearch.Elasticsearch,
    es_index: Union[str, UUID],
    journal_id: Union[str, UUID],
    entry_id: Union[str, UUID],
    title: Optional[str],
    content: Optional[str],
    tags: Union[str, List[str]],
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
    context_url: Optional[str] = None,
) -> str:
    """
    Index a new entry in a journal. Returns the ID of the new document.
    If an entry with that ID has already been indexed, deletes the previous entry and adds the new
    one by default. If you wish to raise an error instead, set `force` to `False` (default is
    `True`).
    """
    index_name = _index(es_index)
    entry_id_str = str(entry_id)

    if es_client.exists(index_name, entry_id_str):
        es_client.delete(index_name, entry_id_str)

    if created_at is None:
        created_at = datetime.utcnow()
    if updated_at is None:
        updated_at = created_at
    entry_body = {
        "journal_id": journal_id,
        "title": title,
        "content": content,
        "tag": tags,
        "created_at": created_at.timestamp(),
        "updated_at": updated_at.timestamp(),
        "context_type": context_type,
        "context_id": context_id,
        "context_url": context_url,
    }
    es_client.create(index_name, entry_id_str, entry_body)
    return entry_id_str


def bulk_create_entries(
    es_client: elasticsearch.Elasticsearch,
    es_index: Union[str, UUID],
    journal_id: Union[str, UUID],
    entries: List[JournalEntryResponse],
) -> str:
    """
    Index a new entry in a journal. Returns the ID of the new document.
    If an entry with that ID has already been indexed, deletes the previous entry and adds the new
    one by default. If you wish to raise an error instead, set `force` to `False` (default is
    `True`).
    """
    index_name = _index(es_index)

    for entries_chunk in [
        entries[i : i + BULK_CHUNKSIZE] for i in range(0, len(entries), BULK_CHUNKSIZE)
    ]:
        bulk_commands = [
            {
                "_index": index_name,
                "_id": str(entry.id),
                "_source": {
                    "journal_id": str(journal_id),
                    "title": entry.title,
                    "content": entry.content,
                    "tag": entry.tags,
                    "created_at": entry.created_at.timestamp()
                    if entry.created_at
                    else datetime.utcnow().timestamp(),
                    "updated_at": entry.updated_at.timestamp()
                    if entry.updated_at
                    else datetime.utcnow().timestamp(),
                    "context_type": entry.context_type,
                    "context_id": entry.context_id,
                    "context_url": entry.context_url,
                },
            }
            for entry in entries_chunk
        ]

        response = bulk(es_client, bulk_commands)

    return response


def delete_entry(
    es_client: elasticsearch.Elasticsearch,
    es_index: Union[str, UUID],
    journal_id: Union[str, UUID],
    entry_id: Union[str, UUID],
) -> str:
    """
    Delete an existing entry in a journal.
    """
    index_name = _index(es_index)
    entry_id_str = str(entry_id)

    if es_client.exists(index_name, entry_id_str):
        es_client.delete(index_name, entry_id_str)

    return entry_id_str


def bulk_delete_entries(
    es_client: elasticsearch.Elasticsearch,
    es_index: str,
    journal_id: Union[str, UUID],
    entries_ids: List[UUID],
):
    """
    Delete enries from index.
    """

    bulk_commands = [
        {"_op_type": "delete", "_index": es_index, "_id": str(entry_id)}
        for entry_id in entries_ids
    ]
    bulk(es_client, bulk_commands)


def delete_journal_entries(
    es_client: elasticsearch.Elasticsearch,
    es_index: str,
    journal_id: Union[str, UUID],
) -> str:
    """
    Delete an existing entries in a journal.
    """

    index_name = _index(es_index)

    es_client.delete_by_query(
        index=index_name, body={"query": {"terms": {"journal_id": [str(journal_id)]}}}
    )

    return str(journal_id)


def erase(
    es_client: elasticsearch.Elasticsearch,
    es_index: str,
    journal_id: str,
    db_session: Optional[Session] = None,
    **kwargs,
) -> None:
    """
    Erases index for a given journal or for all journals.
    """
    if es_index is None:
        logger.warn("Noop erasure for null index")
        return
    if db_session is None:
        db_session = next(yield_connection_from_env())

    try:
        if index_p(es_client, es_index):
            index_name = _index(es_index)

            if journal_id != "any":
                delete_journal_entries(es_client, index_name, journal_id)
            else:
                drop_index(es_client, index_name)
    finally:
        db_session.close()


def synchronize(
    es_client: elasticsearch.Elasticsearch,
    es_index: Optional[str],
    journal_id: str,
    db_session: Optional[Session] = None,
    **kwargs,
) -> None:
    """
    Synchronize the journal information from the given database with the given Elasticsearch cluster

    This can be done for a single journal or for all journals.
    """
    if es_index is None:
        logger.warn("Noop synchronization with null index")
        return

    if db_session is None:
        db_session = next(yield_connection_from_env())

    try:
        erase(es_client, es_index, journal_id, db_session)

        if not index_p(es_client, es_index):
            create_index(es_client, es_index)

        query = (
            db_session.query(Journal)
            .filter(Journal.search_index == es_index)
            .filter(Journal.deleted == False)
        )

        if journal_id != "any":
            journal_uuid = UUID(journal_id)
            query = query.filter(Journal.id == journal_uuid)

        for journal in query.all():

            journal_spec = JournalSpec(
                id=journal.id, bugout_user_id=journal.bugout_user_id, name=journal.name
            )

            try:
                entries = asyncio.run(
                    actions.get_journal_entries(
                        db_session, journal_spec, None, limit=None
                    )
                )
            except Exception as err:
                print(f"Error synhronize {journal.id} error {err}")
                continue

            bulk_commands = []

            for entry in entries:

                bulk_commands.append(
                    {
                        "_index": es_index,
                        "_id": str(entry.id),
                        "_source": {
                            "journal_id": str(journal.id),
                            "title": entry.title,
                            "content": entry.content,
                            "tag": [tag.tag for tag in entry.tags if tag is not None],
                            "created_at": entry.created_at.timestamp(),
                            "updated_at": entry.updated_at.timestamp(),
                            "context_type": entry.context_type,
                            "context_id": entry.context_id,
                            "context_url": entry.context_url,
                        },
                    }
                )

            bulk(es_client, bulk_commands)
            print(f"Synchronization in progress for journal: {journal.id}.")
    finally:
        db_session.close()


class Bound(Enum):
    GT = 1
    GTE = 2
    LTE = 3
    LT = 4


def empty_bounds_dict() -> Dict[Bound, List[datetime]]:
    return {
        Bound.GT: [],
        Bound.GTE: [],
        Bound.LTE: [],
        Bound.LT: [],
    }


@dataclass
class SearchQuery:
    query: str
    required_tags: List[str] = field(default_factory=list)
    forbidden_tags: List[str] = field(default_factory=list)
    optional_tags: List[str] = field(default_factory=list)
    created_at_bounds: Dict[Bound, List[datetime]] = field(
        default_factory=empty_bounds_dict
    )
    updated_at_bounds: Dict[Bound, List[datetime]] = field(
        default_factory=empty_bounds_dict
    )
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None


def normalized_search_query(
    q: str, filters: List[str], strict_filter_mode: bool = True
) -> SearchQuery:
    """
    A journal search query may specify filters in the query string (e.g. tag:$tag, !tag:$tag,
    updated_at:>$date, etc.)

    This function takes a query string and a list of filters, extracts all filters from the query
    string into the list of filters, and returns a SearchQuery object.
    """
    required_tags: List[str] = []
    forbidden_tags: List[str] = []
    optional_tags: List[str] = []
    # TODO(neeraj): Test created_at and updated_at bounds in query language. Current tests do not
    # test these.
    created_at_bounds: Dict[Bound, List[datetime]] = {
        Bound.GT: [],
        Bound.GTE: [],
        Bound.LTE: [],
        Bound.LT: [],
    }
    updated_at_bounds: Dict[Bound, List[datetime]] = {
        Bound.GT: [],
        Bound.GTE: [],
        Bound.LTE: [],
        Bound.LT: [],
    }
    time_bounds: Dict[str, Dict[Bound, List[datetime]]] = {
        "created_at": created_at_bounds,
        "updated_at": updated_at_bounds,
    }
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_url: Optional[str] = None

    filter_prefixes = [
        "context_type:",
        "context_id:",
        "context_url:",
        "tag:",
        "!tag:",
        "?tag:",
        "#",
        "!#",
        "?#",
    ] + [f"{key}:" for key in time_bounds]

    # If we are not in strict_filter_mode, check if there are filters in the q parameter itself.
    # If we are in strict_filter_mode, q is used as-is and is not processed into.
    query_string = q.strip()
    if not strict_filter_mode:
        logger.info(
            f"strict_filter_mode is off; original query: {q}, original filters: {filters}"
        )
        tokens = q.split()
        found_filters = False
        for token in tokens:
            if any([token.startswith(prefix) for prefix in filter_prefixes]):
                filters.append(token)
                found_filters = True

        if found_filters:
            query_string = " ".join(
                [token for token in tokens if token not in filters]
            ).strip()

        logger.info(
            f"strict_filter_mode is off; new query: {query_string}, new filters: {filters}"
        )
    else:
        logger.info("strict_filter_mode is on")

    for filter_item in filters:
        if filter_item == "":
            logger.warning("Skipping empty filter item")
            continue
        filter_type: Optional[str] = None
        filter_spec: Optional[str] = None

        # Try Google style search filters
        components = filter_item.split(":")
        if len(components) >= 2:
            filter_type = components[0]
            filter_spec = ":".join(components[1:])

        if filter_item[0] == "#" and len(filter_item) > 1:
            filter_type = "tag"
            filter_spec = filter_item[1:]
        elif filter_item[:2] == "!#" and len(filter_item) > 2:
            filter_type = "!tag"
            filter_spec = filter_item[2:]
        elif filter_item[:2] == "?#" and len(filter_item) > 2:
            filter_type = "?tag"
            filter_spec = filter_item[2:]

        if filter_type is None or filter_spec is None:
            logger.warning(f"Skipping invalid filter item: {filter_item}")
            continue

        if filter_type == "tag":
            required_tags.append(filter_spec)
        elif filter_type == "!tag":
            forbidden_tags.append(filter_spec)
        elif filter_type == "?tag":
            optional_tags.append(filter_spec)
        elif filter_type == "context_type":
            context_type = filter_spec
        elif filter_type == "context_id":
            context_id = filter_spec
        elif filter_type == "context_url":
            context_url = filter_spec
        elif filter_type in time_bounds:
            bound_type: Optional[Bound] = None
            raw_bound: Optional[str] = None
            if filter_spec[:2] == ">=":
                bound_type = Bound.GTE
                raw_bound = filter_spec[2:]
            elif filter_spec[:2] == "<=":
                bound_type = Bound.LTE
                raw_bound = filter_spec[2:]
            elif filter_spec[:1] == ">":
                bound_type = Bound.GT
                raw_bound = filter_spec[1:]
            elif filter_spec[:1] == "<":
                bound_type = Bound.LT
                raw_bound = filter_spec[1:]

            if bound_type is None or raw_bound is None:
                logger.warning(f"Skipping invalid time filter {filter_item}")
                continue

            bound: Optional[datetime] = None
            try:
                bound = parse_datetime(raw_bound)
            except Exception as e:
                logger.error(repr(e))

            if bound is None:
                try:
                    bound = datetime.utcfromtimestamp(int(raw_bound))
                    logger.error(
                        f"Attempting to parse time bound as an epoch timestamp: {raw_bound}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Skipping time filter {filter_item} with unparseable time: {raw_bound}"
                    )
                    continue

            time_bounds[filter_type][bound_type].append(bound)
        else:
            logger.warning(
                f"Skipping filter {filter_item} with invalid type: {filter_type}"
            )

    search_query = SearchQuery(
        query=query_string,
        required_tags=required_tags,
        forbidden_tags=forbidden_tags,
        optional_tags=optional_tags,
        created_at_bounds=time_bounds["created_at"],
        updated_at_bounds=time_bounds["updated_at"],
        context_type=context_type,
        context_id=context_id,
        context_url=context_url,
    )
    return search_query


class ResultsOrder(Enum):
    DESCENDING = "desc"
    ASCENDING = "asc"


def search_database(
    db_session: Session,
    journal_id: Union[str, UUID],
    search_query: SearchQuery,
    size: int = 10,
    start: int = 0,
    order: ResultsOrder = ResultsOrder.DESCENDING,
) -> Tuple[int, List[JournalEntry]]:
    """
    Implements the same interface as search, but searches in database rather than in Elasticsearch.

    This is by way of a bypass for journals whose entries do not need to be indexed in Elasticsearch
    (for example Humbug journals).

    Does not implement permission checks since it is assumed that permissions are checked prior to
    calling this method.

    TODO(neeraj): Better search functionality:
    2. Assign scores for optional tags
    """
    query = db_session.query(JournalEntry).filter(JournalEntry.journal_id == journal_id)

    if search_query.context_type is not None:
        query = query.filter(JournalEntry.context_type == search_query.context_type)
    if search_query.context_id is not None:
        query = query.filter(JournalEntry.context_id == search_query.context_id)
    if search_query.context_url is not None:
        query = query.filter(JournalEntry.context_url == search_query.context_url)

    # or_() -> BooleanClauseList
    tags_filter: List[Union[BooleanClauseList, List[Query]]] = []

    """
    Because we can't do correct join with tags table 
    and request from joined table intersection of the tags
    for working with tag intersection
    we use exists clause with AND conditions
    it's works correct but has a certain cost for required_tags number

    Disscation about changes https://github.com/bugout-dev/spire/pull/15
    """
    if search_query.required_tags:
        tags_filter.extend(
            [
                db_session.query(JournalEntryTag)
                .filter(JournalEntryTag.journal_entry_id == JournalEntry.id)
                .filter(JournalEntryTag.tag == tag)
                .exists()
                for tag in search_query.required_tags
            ]
        )

    if search_query.forbidden_tags:
        tags_filter.append(
            not_(
                db_session.query(JournalEntryTag)
                .filter(JournalEntryTag.journal_entry_id == JournalEntry.id)
                .filter(
                    or_(
                        *[
                            JournalEntryTag.tag == tag
                            for tag in search_query.forbidden_tags
                        ]
                    )
                )
                .exists()
            )
        )

    if search_query.optional_tags:
        tags_filter.append(
            db_session.query(JournalEntryTag)
            .filter(JournalEntryTag.journal_entry_id == JournalEntry.id)
            .filter(
                or_(*[JournalEntryTag.tag == tag for tag in search_query.optional_tags])
            )
            .exists()
        )

    if tags_filter:
        query = query.filter(and_(*tags_filter))

    if search_query.context_type is not None:
        query = query.filter(JournalEntry.context_type == search_query.context_type)
    if search_query.context_id is not None:
        query = query.filter(JournalEntry.context_id == search_query.context_id)
    if search_query.context_url is not None:
        query = query.filter(JournalEntry.context_url == search_query.context_url)

    for comparator, bounds in search_query.created_at_bounds.items():
        if comparator == Bound.GT:
            for bound in bounds:
                query = query.filter(JournalEntry.created_at > bound)
        elif comparator == Bound.GTE:
            for bound in bounds:
                query = query.filter(JournalEntry.created_at >= bound)
        if comparator == Bound.LT:
            for bound in bounds:
                query = query.filter(JournalEntry.created_at < bound)
        elif comparator == Bound.LTE:
            for bound in bounds:
                query = query.filter(JournalEntry.created_at <= bound)

    for comparator, bounds in search_query.updated_at_bounds.items():
        if comparator == Bound.GT:
            for bound in bounds:
                query = query.filter(JournalEntry.updated_at > bound)
        elif comparator == Bound.GTE:
            for bound in bounds:
                query = query.filter(JournalEntry.updated_at >= bound)
        if comparator == Bound.LT:
            for bound in bounds:
                query = query.filter(JournalEntry.updated_at < bound)
        elif comparator == Bound.LTE:
            for bound in bounds:
                query = query.filter(JournalEntry.updated_at <= bound)

    if order == ResultsOrder.ASCENDING:
        query = query.order_by(JournalEntry.created_at.asc())
    else:
        query = query.order_by(JournalEntry.created_at.desc())
    num_entries = query.count()
    query = query.limit(size).offset(start)

    journal_entries_temp = query.cte(name="journal_entries_temp")

    entries_ids_with_tags = (
        db_session.query(journal_entries_temp.c.id, JournalEntryTag.tag).join(
            JournalEntryTag,
            JournalEntryTag.journal_entry_id == journal_entries_temp.c.id,
        )
    ).cte(name="entries_ids_with_tags")

    aggregated_tags = (
        db_session.query(
            entries_ids_with_tags.c.id,
            func.array_agg(entries_ids_with_tags.c.tag).label("tags"),
        )
        .group_by(entries_ids_with_tags.c.id)
        .cte(name="aggregated_tags")
    )

    query = db_session.query(
        journal_entries_temp.c.id.label("id"),
        aggregated_tags.c.tags.label("tags"),
        journal_entries_temp.c.title.label("title"),
        journal_entries_temp.c.content.label("content"),
        journal_entries_temp.c.context_id.label("context_id"),
        journal_entries_temp.c.context_url.label("context_url"),
        journal_entries_temp.c.context_type.label("context_type"),
        journal_entries_temp.c.version_id.label("version_id"),
        journal_entries_temp.c.created_at.label("created_at"),
        journal_entries_temp.c.updated_at.label("updated_at"),
    ).join(aggregated_tags, journal_entries_temp.c.id == aggregated_tags.c.id)

    rows = query.all()

    return num_entries, rows


def search(
    es_client: elasticsearch.Elasticsearch,
    es_index: Union[str, UUID],
    journal_id: Union[str, UUID],
    search_query: SearchQuery,
    size: int = 10,
    start: int = 0,
    order: ResultsOrder = ResultsOrder.DESCENDING,
) -> Dict[str, Any]:
    """
    Execute a search against a journal index. Returns Elasticsearch hits object:
    https://www.elastic.co/guide/en/elasticsearch/reference/current/search-search.html#search-api-response-body
    """
    body: Dict[str, Any] = {}
    query: Dict[str, Any] = {}
    query_bool: Dict[str, Any] = {}

    query_bool_should: List[Dict[str, Any]] = []
    if search_query.query != "":
        query_bool_should.extend(
            [
                # boost value of 2 is based on intuition, not data
                # TODO(neeraj): Analyze data to choose a better justified value for this boost factor.
                {"match": {"title": {"query": search_query.query, "boost": 2}}},
                {"match": {"content": {"query": search_query.query}}},
            ]
        )
    else:
        query_bool_should.append({"match_all": {}})
        if not search_query.optional_tags:
            order_value = "desc"
            if order == ResultsOrder.ASCENDING:
                order_value = "asc"
            # If there is no proper search element to the query, sort in descending order of
            # created_at field.
            # Elasticsearch sort documentation:
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/sort-search-results.html
            body["sort"] = [{"created_at": {"order": order_value}}, "_score"]

    if search_query.optional_tags:
        query_bool_should.append({"terms": {"tag": search_query.optional_tags}})

    if query_bool_should:
        query_bool["should"] = query_bool_should

    query_bool_must: List[Dict[str, Any]] = []

    query_bool_must.append({"terms": {"journal_id": [journal_id]}})

    if search_query.required_tags:
        query_bool_must.extend(
            [{"terms": {"tag": [tag]}} for tag in search_query.required_tags]
        )

    if search_query.context_type is not None:
        query_bool_must.append({"terms": {"context_type": [search_query.context_type]}})

    if search_query.context_id is not None:
        query_bool_must.append({"terms": {"context_id": [search_query.context_id]}})
    if search_query.context_url is not None:
        query_bool_must.append({"terms": {"context_url": [search_query.context_url]}})

    if query_bool_must:
        query_bool["must"] = query_bool_must

    query_bool_filter: List[Dict[str, Any]] = []
    time_ranges: Dict[str, Dict[str, Any]] = {
        "created_at": {},
        "updated_at": {},
    }
    time_bounds: Dict[str, Dict[Bound, List[datetime]]] = {
        "created_at": search_query.created_at_bounds,
        "updated_at": search_query.updated_at_bounds,
    }
    for time_type, bounds in time_bounds.items():
        if bounds[Bound.GT]:
            time_ranges[time_type]["gt"] = max(
                [int(dt.timestamp()) for dt in bounds[Bound.GT]]
            )
        if bounds[Bound.GTE]:
            time_ranges[time_type]["gte"] = max(
                [int(dt.timestamp()) for dt in bounds[Bound.GTE]]
            )
        if bounds[Bound.LT]:
            time_ranges[time_type]["lt"] = min(
                [int(dt.timestamp()) for dt in bounds[Bound.LT]]
            )
        if bounds[Bound.LTE]:
            time_ranges[time_type]["lte"] = min(
                [int(dt.timestamp()) for dt in bounds[Bound.LTE]]
            )

    for time_type, time_range in time_ranges.items():
        if time_range:
            query_bool_filter.append({"range": {time_type: time_range}})

    if query_bool_filter:
        query_bool["filter"] = query_bool_filter

    query_bool_should_not: List[Dict[str, Any]] = []
    if search_query.forbidden_tags:
        query_bool_should_not.append({"terms": {"tag": search_query.forbidden_tags}})

    if query_bool_should_not:
        query_bool["must_not"] = query_bool_should_not

    query["bool"] = query_bool

    body["query"] = query

    index_name = _index(es_index)
    results = es_client.search(body, index_name, size=size, from_=start)
    hits = results.get("hits", {})
    return hits


def search_cli(
    es_client: elasticsearch.Elasticsearch,
    es_index: Union[str, UUID],
    journal_id: Union[str, UUID],
    q: str,
    filters: List[str],
    strict: bool,
    size: int = 10,
    start: int = 0,
    **kwargs,
):
    """
    Wraps search function so that it's callable from the CLI.
    """
    search_query = normalized_search_query(q, filters, strict_filter_mode=strict)
    return search(es_client, es_index, journal_id, search_query, size, start)


def search_db_cli(
    db_session: Optional[Session],
    journal_id: Union[str, UUID],
    q: str,
    filters: List[str],
    size: int = 10,
    start: int = 0,
    **kwargs,
):
    """
    Wraps search_database function so that it's callable from the CLI.
    """
    if db_session is None:
        db_session = next(yield_connection_from_env())
    try:
        search_query = normalized_search_query(q, filters, strict_filter_mode=False)
        results = search_database(db_session, journal_id, search_query, size, start)
    finally:
        db_session.close()
    return results


def set_index_cli(
    db_session: Optional[Session],
    es_client: elasticsearch.Elasticsearch,
    journal_id: Union[str, UUID],
    index: Optional[str] = None,
    **kwargs,
) -> str:
    """
    Wraps search_database function so that it's callable from the CLI.
    """
    if db_session is None:
        db_session = next(yield_connection_from_env())

    try:
        journal_id_uuid = UUID(str(journal_id))
        journal = db_session.query(Journal).filter(Journal.id == journal_id_uuid).one()
        journal.search_index = index
        db_session.commit()
        if index is not None:
            synchronize(es_client, index, str(journal_id), db_session)
    except Exception as e:
        print("Error setting index")
        print(str(e))
        db_session.rollback()
    finally:
        db_session.close()

    return f"Index set to: {index}"


def print_return_value(wrapped_func: Callable) -> Callable[..., None]:
    """
    Wraps a function so that its return value gets printed to screen. Decorator.
    """

    def decoration(**kwargs):
        result = wrapped_func(**kwargs)
        print(result)
        return None

    return decoration


def generate_argument_parser() -> argparse.ArgumentParser:
    """
    Generates a command-line interface that performs journal search actions from the command line.
    """
    parser = argparse.ArgumentParser(description="Spire Journal search")
    subparsers = parser.add_subparsers(title="Actions")

    drop_index_parser = subparsers.add_parser("drop-index", description="Drop an index")
    drop_index_parser.add_argument(
        "-i", "--index", required=True, help="Name of index to drop"
    )
    drop_index_parser.set_defaults(func=print_return_value(drop_index))

    index_exists_parser = subparsers.add_parser(
        "index-exists?",
        description="Check for existence of an index for a single journal",
    )
    index_exists_parser.add_argument("-j", "--journal-id")
    index_exists_parser.set_defaults(func=print_return_value(index_p))

    create_index_parser = subparsers.add_parser(
        "create-index", description="Create index for a single journal"
    )
    create_index_parser.add_argument("-j", "--journal-id", required=True)
    create_index_parser.add_argument("-f", "--force", action="store_true")
    create_index_parser.set_defaults(func=print_return_value(create_index))

    search_parser = subparsers.add_parser(
        "search", description="Search within a journal"
    )
    search_parser.add_argument("-j", "--journal-id", required=True)
    search_parser.add_argument("-n", "--size", type=int, default=10)
    search_parser.add_argument("-s", "--start", type=int, default=0)
    search_parser.add_argument("-q", default="")
    search_parser.add_argument("-f", "--filters", nargs="+", default=[])
    search_parser.add_argument(
        "--strict", action="store_true", help="Strict filter mode?"
    )
    search_parser.set_defaults(func=print_return_value(search_cli))

    search_db_parser = subparsers.add_parser("search-db", description="Database search")
    search_db_parser.add_argument("-j", "--journal-id", required=True)
    search_db_parser.add_argument("-n", "--size", type=int, default=10)
    search_db_parser.add_argument("-s", "--start", type=int, default=0)
    search_db_parser.add_argument("-q", default="")
    search_db_parser.add_argument("-f", "--filters", nargs="+", default=[])
    search_db_parser.add_argument(
        "--strict", action="store_true", help="Strict filter mode?"
    )
    search_db_parser.set_defaults(func=print_return_value(search_db_cli))

    erase_parser = subparsers.add_parser("erase", description="Erase indices for user")
    erase_parser.add_argument(
        "-j",
        "--journal-id",
        required=True,
        help="Set --journal-id=any to synchronize all journals",
    )
    erase_parser.add_argument(
        "-i",
        "--es-index",
        default=None,
        choices=[DEFAULT_JOURNALS_ES_INDEX],
        help="Name of search index the journal synchronizes to. Leave empty to set index to NULL.",
    )
    erase_parser.set_defaults(func=print_return_value(erase))

    set_index_parser = subparsers.add_parser(
        "set-index", description="Set an index for a journal"
    )
    set_index_parser.add_argument(
        "-j", "--journal-id", required=True, help="ID of journal for which to set index"
    )
    set_index_parser.add_argument(
        "-i",
        "--index",
        default=None,
        help="Name of search index the journal synchronizes to. Leave empty to set index to NULL.",
    )
    set_index_parser.set_defaults(func=print_return_value(set_index_cli))

    synchronize_parser = subparsers.add_parser(
        "synchronize", description="Synchronize indices"
    )
    synchronize_parser.add_argument(
        "-j",
        "--journal-id",
        required=True,
        help="Set --journal-id=any to synchronize all journals",
    )
    synchronize_parser.add_argument(
        "-i",
        "--es-index",
        default=None,
        choices=[DEFAULT_JOURNALS_ES_INDEX],
        help="Name of search index the journal synchronizes to. Leave empty to set index to NULL.",
    )

    synchronize_parser.set_defaults(func=print_return_value(synchronize))

    return parser


def main() -> None:
    """
    Handles running this module as a script.
    """
    parser = generate_argument_parser()
    args = parser.parse_args()
    args.es_client = es_client_from_env()
    args.db_session = None
    args.func(**vars(args))


if __name__ == "__main__":
    main()
