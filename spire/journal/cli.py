"""
Spire Journal CLI
"""
import argparse
import json
from typing import Any, cast, Callable, Dict, List, Optional

from sqlalchemy import text

from . import actions
from . import data
from . import search
from ..db import SessionLocal
from .models import Journal, JournalPermissions, HolderType, JournalTTL
from ..utils.confparse import scope_conf
from ..utils.settings import DEFAULT_JOURNALS_ES_INDEX
from ..es import yield_es_client_from_env_ctx


def journal_as_json_dict(journals: List[Journal]) -> List[Dict[str, Any]]:
    """
    Returns a representation of the given user as a JSON-serializable dictionary.
    """
    journals_json = [
        {
            "id": str(journal.id),
            "bugout_user_id": str(journal.bugout_user_id),
            "name": journal.name,
            "version_id": journal.version_id,
            "created_at": str(journal.created_at),
            "updated_at": str(journal.updated_at),
            "holder_ids": list({holder.holder_id for holder in journal.permissions}),
        }
        for journal in journals
    ]
    return journals_json


def journal_permissions_as_json_dict(
    journal_permissions: List[JournalPermissions],
) -> List[Dict[str, Any]]:
    """
    Returns a representation of the given user as a JSON-serializable dictionary.
    """
    journal_permissions_json = [
        {
            "holder_type": str(j_permission.holder_type),
            "journal_id": str(j_permission.journal_id),
            "holder_id": str(j_permission.holder_id),
            "permission": j_permission.permission,
        }
        for j_permission in journal_permissions
    ]
    return journal_permissions_json


def print_journals(journals: List[Journal]) -> None:
    """
    Print journals to screen as JSON object.
    """
    print(json.dumps(journal_as_json_dict(journals)))


def print_journal_permissions(journal_permissions: List[JournalPermissions]) -> None:
    """
    Print journal permissions to screen as JSON object.
    """
    print(json.dumps(journal_permissions_as_json_dict(journal_permissions)))


def journals_get_handler(args: argparse.Namespace) -> None:
    """
    Handler for "journals get" subcommand.
    """
    session = SessionLocal()
    try:
        query = session.query(Journal)

        if args.name:
            query.filter(Journal.name == args.name)

        journals = query.all()
        print_journals(journals)
    finally:
        session.close()


def holders_add_handler(args: argparse.Namespace) -> None:
    """
    Handler for "journals holders add" subcommand.
    """
    session = SessionLocal()
    try:
        journal_permissions = []
        for permission in args.permissions:
            journal_permission = JournalPermissions(
                holder_type=args.type,
                journal_id=args.journal,
                holder_id=args.holder,
                permission=permission,
            )
            journal_permissions.append(journal_permission)
            session.add(journal_permission)
        session.commit()
        print_journal_permissions(journal_permissions)
    finally:
        session.close()


def journal_backup_restore_handler(args: argparse.Namespace) -> None:
    """
    Handler for "journals backup restore" subcommand.
    """
    session = SessionLocal()

    es_index = DEFAULT_JOURNALS_ES_INDEX
    try:
        query = session.query(Journal).filter(Journal.id == args.journal)
        journal = query.one_or_none()
        if journal is None:
            raise actions.JournalNotFound(f"Journal with id: {args.journal} not found")
        if journal.deleted == False:
            raise actions.JournalNotFound(
                f"Nothing to restore, journal with id: {journal.id} is active"
            )
        query.update({Journal.deleted: False})
        session.commit()
        print(f"Journal with id: {journal.id} restored")

        with yield_es_client_from_env_ctx() as es_client:
            search.synchronize(
                es_client=es_client, journal_id=str(journal.id), es_index=es_index
            )
            print("Configured and synchronized indices for deleted journal")
    finally:
        session.close()


def journal_backup_purge_handler(args: argparse.Namespace) -> None:
    """
    Handler for "journals backup purge" subcommand.
    """
    session = SessionLocal()
    es_index = DEFAULT_JOURNALS_ES_INDEX
    try:
        query = session.query(Journal).filter(Journal.id == args.journal)
        journal = query.one_or_none()
        if journal is None:
            raise actions.JournalNotFound(f"Journal with id: {args.journal} not found")
        session.delete(journal)
        session.commit()
        print(f"Journal with id: {journal.id} deleted")

        with yield_es_client_from_env_ctx() as es_client:
            try:
                search.drop_index(es_client, es_index)
                print("Journal index droped")
            except Exception as e:
                print("Index for this journal doesn't exists")
    finally:
        session.close()


def journal_rules_list_handler(args: argparse.Namespace) -> None:
    """
    List journal entry rules.
    """
    db_session = SessionLocal()
    try:
        query = (
            db_session.query(JournalTTL)
            .order_by(JournalTTL.id)
            .offset(args.offset - 1 if args.offset != 0 else args.offset)
            .limit(args.limit)
        )
        if args.journal is not None:
            query = query.filter(JournalTTL.journal_id == args.journal)

        rules = query.all()
        print(
            data.JournalTTLRulesListResponse(
                rules=[
                    data.JournalTTLRuleResponse(
                        id=rule.id,
                        journal_id=rule.journal_id,
                        name=rule.name,
                        conditions=rule.conditions,
                        action=data.RuleActions(rule.action).value,
                        active=rule.active,
                        created_at=rule.created_at,
                    )
                    for rule in rules
                ]
            ).json()
        )
    finally:
        db_session.close()


def journal_rules_add_handler(args: argparse.Namespace) -> None:
    """
    Create new entry rule.
    """
    db_session = SessionLocal()
    try:
        latest_rule_id = (
            db_session.query(JournalTTL.id)
            .order_by(text("id desc"))
            .limit(1)
            .one_or_none()
        )
        if latest_rule_id is None:
            latest_rule_id = 0
        else:
            latest_rule_id = latest_rule_id[0]

        rule = JournalTTL(
            id=latest_rule_id + 1,
            journal_id=args.journal,
            name=args.name,
            conditions=json.loads(args.conditions),
            action=args.action,
            active=args.active,
        )
        db_session.add(rule)
        db_session.commit()

        print(
            data.JournalTTLRuleResponse(
                id=rule.id,
                journal_id=rule.journal_id,
                name=rule.name,
                conditions=rule.conditions,
                action=data.RuleActions(rule.action).value,
                active=rule.active,
                created_at=rule.created_at,
            ).json()
        )
    finally:
        db_session.close()


def journal_rules_toggle_handler(args: argparse.Namespace) -> None:
    """
    Mark rule as active or incactive.
    """
    db_session = SessionLocal()
    try:
        query = db_session.query(JournalTTL).filter(JournalTTL.id == args.id)
        rule = query.one()
        query.update({JournalTTL.active: args.active})
        db_session.commit()

        print(
            data.JournalTTLRuleResponse(
                id=rule.id,
                journal_id=rule.journal_id,
                name=rule.name,
                conditions=rule.conditions,
                action=data.RuleActions(rule.action).value,
                active=rule.active,
                created_at=rule.created_at,
            ).json()
        )
    finally:
        db_session.close()


def journal_rules_delete_handler(args: argparse.Namespace) -> None:
    """
    Delete journal rule.
    """
    db_session = SessionLocal()
    try:
        rule = db_session.query(JournalTTL).filter(JournalTTL.id == args.id).one()
        db_session.delete(rule)
        db_session.commit()
        print(
            data.JournalTTLRuleResponse(
                id=rule.id,
                journal_id=rule.journal_id,
                name=rule.name,
                conditions=rule.conditions,
                action=data.RuleActions(rule.action).value,
                active=rule.active,
                created_at=rule.created_at,
            ).json()
        )
    finally:
        db_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Spire Journal CLI")
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = parser.add_subparsers(description="Journal commands")

    parser_journals = subcommands.add_parser("journals", description="Spire journals")
    parser_journals.set_defaults(func=lambda _: parser_journals.print_help())
    subcommands_journals = parser_journals.add_subparsers(
        description="Spire journals commands"
    )

    parser_journal_get = subcommands_journals.add_parser(
        "get", description="Get Spire journal"
    )
    parser_journal_get.add_argument(
        "-n",
        "--name",
        help="Journal name",
    )
    parser_journal_get.set_defaults(func=journals_get_handler)

    # Journal holders parser
    parser_holders = subcommands.add_parser(
        "holders", description="Spire journal holders"
    )
    parser_holders.set_defaults(func=lambda _: parser_holders.print_help())
    subcommands_holders = parser_holders.add_subparsers(
        description="Holder handler for Spire journal"
    )
    parser_holders_add = subcommands_holders.add_parser(
        "add", description="Add journal holders"
    )
    parser_holders_add.add_argument(
        "-j",
        "--journal",
        required=True,
        help="Journal id",
    )
    parser_holders_add.add_argument(
        "-o",
        "--holder",
        required=True,
        help="User's/group's id)",
    )
    parser_holders_add.add_argument(
        "-t",
        "--type",
        required=True,
        choices=[member for member in HolderType.__members__],
        help="Specifies the type of holder",
    )
    journal_permission_choices = [journal.value for journal in data.JournalScopes]
    entries_permission_choices = [entry.value for entry in data.JournalEntryScopes]
    parser_holders_add.add_argument(
        "-p",
        "--permissions",
        choices=journal_permission_choices + entries_permission_choices,
        nargs="+",
        help="List of permissions (for ex. -p 'journals.read journals.update')",
    )
    parser_holders_add.set_defaults(func=holders_add_handler)

    # Restore module
    parser_backup = subcommands.add_parser("backup", description="Journal backup")
    parser_backup.set_defaults(func=lambda _: parser_backup.print_help())
    subcommands_backup = parser_backup.add_subparsers(
        description="Handler to manage journal backup"
    )
    parser_backup_restore = subcommands_backup.add_parser(
        "restore", description="Restore journal and index from backup"
    )
    parser_backup_restore.add_argument(
        "-j",
        "--journal",
        required=True,
        help="Journal id",
    )
    parser_backup_restore.set_defaults(func=journal_backup_restore_handler)
    parser_backup_purge = subcommands_backup.add_parser(
        "purge", description="Purge journal completle"
    )
    parser_backup_purge.add_argument(
        "-j",
        "--journal",
        required=True,
        help="Journal id",
    )
    parser_backup_purge.set_defaults(func=journal_backup_purge_handler)

    # Rules module
    parser_rules = subcommands.add_parser("rules", description="Journal rules")
    parser_rules.set_defaults(func=lambda _: parser_rules.print_help())
    subcommands_rules = parser_rules.add_subparsers(
        description="Handler to manage journal rules"
    )
    parser_rules_list = subcommands_rules.add_parser(
        "list", description="List all rules for provided journal"
    )
    parser_rules_list.add_argument("-j", "--journal", help="Journal ID")
    parser_rules_list.add_argument(
        "-o",
        "--offset",
        type=int,
        default=0,
        help="Offset for output result, default is 0",
    )
    parser_rules_list.add_argument(
        "-l",
        "--limit",
        type=int,
        default=10,
        help="Limit of output result, default is 10",
    )
    parser_rules_list.set_defaults(func=journal_rules_list_handler)
    parser_rules_add = subcommands_rules.add_parser(
        "add", description="Add rule for provided journal"
    )
    parser_rules_add.add_argument("-j", "--journal", required=False, help="Journal ID")
    parser_rules_add.add_argument("-n", "--name", required=True, help="Rule name")
    parser_rules_add.add_argument(
        "-c",
        "--conditions",
        required=True,
        help='Rule conditions, as ex: \'{"ttl": 3600, "tags": ["client_id:server-1"]}\'',
    )
    parser_rules_add.add_argument(
        "-a",
        "--action",
        required=True,
        help=f"Rule actions: {[member for member in data.RuleActions.__members__]}",
    )
    parser_rules_add.add_argument(
        "--active", action="store_true", help="Provide to activate rule"
    )
    parser_rules_add.set_defaults(func=journal_rules_add_handler)
    parser_rules_toggle = subcommands_rules.add_parser(
        "toggle", description="Toggle active rule with provided ID"
    )
    parser_rules_toggle.add_argument("-i", "--id", required=True, help="Rule ID")
    parser_rules_toggle.add_argument(
        "--active", action="store_true", help="Provide to activate rule"
    )
    parser_rules_toggle.set_defaults(func=journal_rules_toggle_handler)
    parser_rules_delete = subcommands_rules.add_parser(
        "delete", description="Delete rule with provided ID"
    )
    parser_rules_delete.add_argument("-i", "--id", required=True, help="Rule ID")
    parser_rules_delete.set_defaults(func=journal_rules_delete_handler)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
