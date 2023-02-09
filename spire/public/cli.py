import argparse
import json
from uuid import uuid4

from ..broodusers import bugout_api
from ..db import RO_SessionLocal, SessionLocal, yield_connection_from_env_ctx
from ..utils.settings import BOT_INSTALLATION_TOKEN_HEADER, INSTALLATION_TOKEN
from . import actions
from .models import PublicJournal, PublicUser


def make_journal_public(args: argparse.Namespace) -> None:
    """
    Adds autogenerated public user to journal readers and
    creates journal public record.
    """
    public_permission_list = ["journals.read", "journals.entries.read"]
    if args.entry_create:
        public_permission_list.append("journals.entries.create")
    if args.entry_update:
        public_permission_list.append("journals.entries.update")

    with yield_connection_from_env_ctx() as db_session:
        public_user = actions.get_public_user(
            db_session=db_session, user_id=args.public_user_id
        )

        try:
            bugout_api.update_journal_scopes(
                token=args.token,
                journal_id=args.journal_id,
                holder_type="user",
                holder_id=public_user.user_id,
                permission_list=public_permission_list,
            )
        except Exception as e:
            raise Exception(
                f"Unable to update journal with id: {args.journal_id} scopes, error: {e}"
            )

        try:
            public_journal = actions.create_public_journal(
                db_session=db_session,
                journal_id=args.journal_id,
                user_id=public_user.user_id,
            )
            public_journal_json = {
                "journal_id": str(public_journal.journal_id),
                "user_id": str(public_journal.user_id),
                "created_at": str(public_journal.created_at),
                "updated_at": str(public_journal.updated_at),
                "added_permissions": public_permission_list,
            }
            print(json.dumps(public_journal_json))
        except Exception as e:
            print(
                f"Unable to create record in database with new public journal id: {str(public_journal.journal_id)}, "
                f"user_id: {str(public_journal.user_id)}, err: {str(e)}"
            )


def revoke_journal_public(args: argparse.Namespace) -> None:
    """
    Removes autogenerated public user from journal readers and
    removes journal public record.
    """
    permission_list = [
        "journals.read",
        "journals.update",
        "journals.delete",
        "journals.entries.read",
        "journals.entries.create",
        "journals.entries.update",
        "journals.entries.delete",
    ]

    with yield_connection_from_env_ctx() as db_session:
        public_user = actions.get_public_user(
            db_session=db_session, user_id=args.public_user_id
        )
        public_journal = actions.get_public_journal(
            db_session=db_session, journal_id=args.journal_id
        )

        try:
            bugout_api.delete_journal_scopes(
                token=args.token,
                journal_id=args.journal_id,
                holder_type="user",
                holder_id=public_user.user_id,
                permission_list=permission_list,
            )
        except Exception as e:
            raise Exception(
                f"Unable to remove journal with id: {args.journal_id} scopes, error: {e}"
            )

        try:
            public_journal = actions.delete_public_journal(
                db_session=db_session,
                public_journal=public_journal,
            )

            public_journal_json = {
                "journal_id": str(public_journal.journal_id),
                "user_id": str(public_journal.user_id),
                "created_at": str(public_journal.created_at),
                "updated_at": str(public_journal.updated_at),
                "revoked_permissions": permission_list,
            }
            print(json.dumps(public_journal_json))
        except Exception as e:
            print(
                f"Unable to remove record from database with public journal id: {str(public_journal.journal_id)}, "
                f"user_id: {str(public_journal.user_id)}, err: {str(e)}"
            )


def list_public_journals(args: argparse.Namespace) -> None:
    """
    List all public journals.
    """
    session = RO_SessionLocal()
    try:
        public_journals = session.query(PublicJournal).all()
        public_journals_json = {
            "public_journals": [
                {
                    "journal_id": str(public_journal.journal_id),
                    "user_id": str(public_journal.user_id),
                    "created_at": str(public_journal.created_at),
                    "updated_at": str(public_journal.updated_at),
                }
                for public_journal in public_journals
            ]
        }
        print(json.dumps(public_journals_json))
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def create_public_user(args: argparse.Namespace) -> None:
    """
    Create autogenerated public user for public journals access.
    """
    session = SessionLocal()

    username = f"public-{str(uuid4())}-{args.name}"
    email = f"{username}@bugout.dev"
    generated_password: str = str(uuid4())

    headers = {BOT_INSTALLATION_TOKEN_HEADER: INSTALLATION_TOKEN}

    try:
        user = bugout_api.create_user(
            username=username, email=email, password=generated_password, headers=headers
        )
    except Exception as e:
        raise Exception(
            f"Unable to create autogenerated user with username: {username}, email: {email}, error: {e}"
        )

    try:
        user_token = bugout_api.create_token(
            username=username, password=generated_password
        )
    except Exception as e:
        raise Exception(
            f"Unable to create token for autogenerated user with username: {username}, "
            f"email: {email}, password: {generated_password}, error: {e}"
        )

    try:
        user_restricted_token = bugout_api.create_token_restricted(user_token.id)
    except Exception as e:
        raise Exception(
            f"Unable to create restricted token for autogenerated user with username: {username}, "
            f"email: {email}, password: {generated_password}, error: {e}"
        )

    try:
        public_user = PublicUser(
            user_id=user.id,
            access_token_id=user_token.id,
            restricted_token_id=user_restricted_token.id,
        )
        session.add(public_user)
        session.commit()

        public_user_json = {
            "username": username,
            "user_id": str(public_user.user_id),
            "access_token_id": str(public_user.access_token_id),
            "restricted_token_id": str(public_user.restricted_token_id),
            "created_at": str(public_user.created_at),
            "updated_at": str(public_user.updated_at),
        }
        print(json.dumps(public_user_json))
    except Exception as e:
        raise Exception(
            f"Unable to save autogenerated user in database with username: {username}, "
            f"email: {email}, password: {generated_password}, error: {e}"
        )
    finally:
        session.close()


def list_public_users(args: argparse.Namespace) -> None:
    """
    List all public users.
    """
    session = RO_SessionLocal()
    try:
        public_users = session.query(PublicUser).all()
        public_user_json = {
            "public_users": [
                {
                    "user_id": str(public_user.user_id),
                    "access_token_id": str(public_user.access_token_id),
                    "restricted_token_id": str(public_user.restricted_token_id),
                    "created_at": str(public_user.created_at),
                    "updated_at": str(public_user.updated_at),
                }
                for public_user in public_users
            ]
        }
        print(json.dumps(public_user_json))
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Administrative actions for Bugout Public access"
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = parser.add_subparsers(description="Public commands")

    # Public journal module
    parser_journals = subcommands.add_parser("journals", description="Public journals")
    parser_journals.set_defaults(func=lambda _: parser_journals.print_help())
    subcommands_journals = parser_journals.add_subparsers(
        description="Public journals commands"
    )
    parser_journal_make = subcommands_journals.add_parser(
        "make", description="Make bugout journal public"
    )
    parser_journal_make.add_argument(
        "-t",
        "--token",
        required=True,
        help="Access token of journal owner",
    )
    parser_journal_make.add_argument(
        "-j",
        "--journal-id",
        required=True,
        help="Journal ID to make public",
    )
    parser_journal_make.add_argument(
        "--public-user-id",
        required=True,
        help="Public user ID",
    )
    parser_journal_make.add_argument(
        "--entry-create",
        action="store_true",
        help="Allow unknown users to create entries",
    )
    parser_journal_make.add_argument(
        "--entry-update",
        action="store_true",
        help="Allow unknown users to touch entries",
    )
    parser_journal_make.set_defaults(func=make_journal_public)

    parser_journal_revoke = subcommands_journals.add_parser(
        "revoke", description="Revoke bugout journal from public access public"
    )
    parser_journal_revoke.add_argument(
        "-t",
        "--token",
        required=True,
        help="Access token of journal owner",
    )
    parser_journal_revoke.add_argument(
        "-j",
        "--journal-id",
        required=True,
        help="Journal ID to make public",
    )
    parser_journal_revoke.add_argument(
        "--public-user-id",
        required=True,
        help="Public user ID",
    )
    parser_journal_revoke.set_defaults(func=revoke_journal_public)

    parser_journals_list = subcommands_journals.add_parser(
        "list", description="List all public bugout journals"
    )
    parser_journals_list.set_defaults(func=list_public_journals)

    # Public user module
    parser_users = subcommands.add_parser("users", description="Public users")
    parser_users.set_defaults(func=lambda _: parser_users.print_help())
    subcommands_users = parser_users.add_subparsers(
        description="Public user access commands"
    )
    parser_user_create = subcommands_users.add_parser(
        "create", description="Create public bugout user"
    )
    parser_user_create.add_argument(
        "-n",
        "--name",
        required=True,
        help="Name postfix for public bugout user (public-uuid-<name>)",
    )
    parser_user_create.set_defaults(func=create_public_user)
    parser_user_list = subcommands_users.add_parser(
        "list", description="List all public bugout users"
    )
    parser_user_list.set_defaults(func=list_public_users)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
