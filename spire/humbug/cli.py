"""
Spire Humbug CLI.

Synchronize tokens
python -m spire.humbug.cli tokens synchronize
"""
import argparse
from distutils.util import strtobool
from typing import cast
from uuid import UUID

from .data import (
    HumbugIntegrationResponse,
    HumbugIntegrationListResponse,
    HumbugTokenResponse,
    HumbugTokenListResponse,
)
from .models import HumbugEvent, HumbugBugoutUser, HumbugBugoutUserToken
from ..db import SessionLocal
from ..broodusers import bugout_api


def get_humbug_integrations(args: argparse.Namespace) -> None:
    """
    Get list of Humbug integrations.
    """
    session = SessionLocal()
    try:
        query = session.query(HumbugEvent)
        if args.id is not None:
            query = query.filter(HumbugEvent.id == args.id)
        if args.group is not None:
            query = query.filter(HumbugEvent.group_id == args.group)
        if args.journal is not None:
            query = query.filter(HumbugEvent.journal_id == args.journal)
        events = query.all()

        events_response = HumbugIntegrationListResponse(
            integrations=[
                HumbugIntegrationResponse(
                    id=event.id,
                    group_id=event.group_id,
                    journal_id=event.journal_id,
                    created_at=event.created_at,
                    updated_at=event.updated_at,
                )
                for event in events
            ]
        )
        print(events_response.json())
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def create_humbug_restricted_token(args: argparse.Namespace) -> None:
    """
    Create new humbug restricted token.
    """
    session = SessionLocal()
    try:
        event = (
            session.query(HumbugEvent).filter(HumbugEvent.id == args.id).one_or_none()
        )
        if event is None:
            print("Provided event not found")
            return

        humbug_user = (
            session.query(HumbugBugoutUser)
            .filter(HumbugBugoutUser.event_id == event.id)
            .one()
        )
        restricted_token = bugout_api.create_token_restricted(
            token=humbug_user.access_token_id
        )
        assert restricted_token.restricted == True
        restricted_token_id = cast(UUID, restricted_token.id)

        humbug_token = HumbugBugoutUserToken(
            restricted_token_id=restricted_token_id,
            event_id=event.id,
            user_id=humbug_user.user_id,
            app_name=args.name,
            app_version=args.version,
        )
        session.add(humbug_token)
        session.commit()

        humbug_token_response = HumbugTokenListResponse(
            user_id=humbug_user.user_id,
            humbug_id=event.id,
            tokens=[
                HumbugTokenResponse(
                    restricted_token_id=restricted_token_id,
                    app_name=args.name,
                    app_version=args.version,
                )
            ],
        )

        print(humbug_token_response.json())
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def revoke_humbug_restricted_token(args: argparse.Namespace) -> None:
    """
    Revoke humbug restricted token.
    """
    session = SessionLocal()
    try:
        restricted_token = (
            session.query(HumbugBugoutUserToken)
            .filter(HumbugBugoutUserToken.restricted_token_id == args.token)
            .one_or_none()
        )
        if restricted_token is None:
            print("Provided token not found")
            return

        humbug_user = (
            session.query(HumbugBugoutUser)
            .filter(HumbugBugoutUser.user_id == restricted_token.user_id)
            .first()
        )
        bugout_api.revoke_token(
            token=humbug_user.access_token_id,
            target_token=restricted_token.restricted_token_id,
        )
        session.delete(restricted_token)
        session.commit()

        humbug_token_response = HumbugTokenListResponse(
            user_id=humbug_user.user_id,
            humbug_id=humbug_user.event_id,
            tokens=[
                HumbugTokenResponse(
                    restricted_token_id=restricted_token.restricted_token_id,
                    app_name=restricted_token.app_name,
                    app_version=restricted_token.app_version,
                )
            ],
        )
        print("Token revoked: ")
        print(humbug_token_response.json())
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def get_humbug_restricted_tokens(args: argparse.Namespace) -> None:
    """
    Get humbug restricted tokens.
    """
    session = SessionLocal()
    try:
        restricted_tokens = (
            session.query(HumbugBugoutUserToken)
            .filter(HumbugBugoutUserToken.event_id == args.id)
            .all()
        )
        if len(restricted_tokens) == 0:
            print("No tokens for provided integration")
            return

        humbug_token_response = HumbugTokenListResponse(
            user_id=restricted_tokens[0].user_id,
            humbug_id=args.id,
            tokens=[
                HumbugTokenResponse(
                    restricted_token_id=restricted_token.restricted_token_id,
                    app_name=restricted_token.app_name,
                    app_version=restricted_token.app_version,
                )
                for restricted_token in restricted_tokens
            ],
        )
        print(humbug_token_response.json())
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def synchronize_humbug_restricted_token(args: argparse.Namespace) -> None:
    """
    Synchronize restricted tokens with Brood database.

    If token was revoked on Brood side, it deletes unactive from HumbugBugoutUserToken.
    If token was created on Brood side and doesn't exist in Spire database, it
    creates a record in HumbugBugoutUserToken.
    """
    session = SessionLocal()
    try:
        restricted_humbug_tokens = session.query(HumbugBugoutUserToken).all()
        restricted_humbug_tokens_ids = set(
            [token.restricted_token_id for token in restricted_humbug_tokens]
        )
        humbug_users = session.query(HumbugBugoutUser).all()
        for user in humbug_users:
            restricted_user_tokens = bugout_api.get_user_tokens(
                token=user.access_token_id, restricted=True
            )

            # Delete inactive token from HumbugBugoutUserToken
            inactive_restricted_user_tokens = list(
                filter(
                    lambda token: token.active == False, restricted_user_tokens.tokens
                )
            )
            inactive_restricted_user_tokens_ids = set(
                [token.id for token in inactive_restricted_user_tokens]
            )
            delete_tokens = restricted_humbug_tokens_ids.intersection(
                inactive_restricted_user_tokens_ids
            )
            for token_id in delete_tokens:
                delete_token = list(
                    filter(
                        lambda token: token.restricted_token_id == token_id,
                        restricted_humbug_tokens,
                    )
                )[0]
                session.delete(delete_token)
                print(
                    f"Revoked restricted token with id: {delete_token.restricted_token_id}, "
                    f"app name: {delete_token.app_name}, event id: {user.event_id}"
                )

            # Add new one
            active_restricted_user_tokens = list(
                filter(
                    lambda token: token.active == True, restricted_user_tokens.tokens
                )
            )
            active_restricted_user_tokens_ids = set(
                [token.id for token in active_restricted_user_tokens]
            )
            fresh_tokens = active_restricted_user_tokens_ids.difference(
                restricted_humbug_tokens_ids
            )
            for token_id in fresh_tokens:
                fresh_token = HumbugBugoutUserToken(
                    restricted_token_id=token_id,
                    event_id=user.event_id,
                    user_id=user.user_id,
                    app_name="unknown",
                    app_version="unknown",
                )
                session.add(fresh_token)
                print(
                    f"Added new unknown restricted token with id: {token_id},"
                    f"event id: {user.event_id}"
                )
        session.commit()
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def update_humbug_restricted_token(args: argparse.Namespace) -> None:
    session = SessionLocal()
    try:
        query = session.query(HumbugBugoutUserToken).filter(
            HumbugBugoutUserToken.restricted_token_id == args.restricted_token_id
        )
        token = query.one_or_none()
        if token is None:
            print("Restricted token doesn't exist")
            return
        if args.app_name is not None:
            query.update({HumbugBugoutUserToken.app_name: args.app_name})
        if args.app_version is not None:
            query.update({HumbugBugoutUserToken.app_version: args.app_version})
        if args.store_ip is not None:
            query.update(
                {HumbugBugoutUserToken.store_ip: bool(strtobool(args.store_ip))}
            )
        session.commit()
        print("Restricted token updated")
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Administrative actions for Bugout Humbug"
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = parser.add_subparsers(description="Humbug commands")

    # Humbug integrations module
    parser_integrations = subcommands.add_parser(
        "integrations", description="Humbug integrations"
    )
    parser_integrations.set_defaults(func=lambda _: parser_integrations.print_help())
    subcommands_integrations = parser_integrations.add_subparsers(
        description="Humbug integrations commands"
    )
    parser_integrations_get = subcommands_integrations.add_parser(
        "get", description="Get humbug integrations"
    )
    parser_integrations_get.add_argument(
        "-i", "--id", help="Humbug event integration ID"
    )
    parser_integrations_get.add_argument("-g", "--group", help="Group ID")
    parser_integrations_get.add_argument("-j", "--journal", help="Journal ID")
    parser_integrations_get.set_defaults(func=get_humbug_integrations)

    # Humbug restricted tokens module
    parser_tokens = subcommands.add_parser(
        "tokens", description="Humbug restricted tokens"
    )
    parser_tokens.set_defaults(func=lambda _: parser_tokens.print_help())
    subcommands_tokens = parser_tokens.add_subparsers(
        description="Humbug restricted tokens commands"
    )
    parser_tokens_create = subcommands_tokens.add_parser(
        "create", description="Create humbug restricted token"
    )

    parser_tokens_create.add_argument("-i", "--id", help="Humbug event integration ID")
    parser_tokens_create.add_argument(
        "-n", "--name", required=True, help="Application name"
    )
    parser_tokens_create.add_argument(
        "-v", "--version", required=True, help="Application version"
    )
    parser_tokens_create.set_defaults(func=create_humbug_restricted_token)
    parser_tokens_revoke = subcommands_tokens.add_parser(
        "revoke", description="Revoke humbug restricted token"
    )
    parser_tokens_revoke.add_argument("-t", "--token", help="Restricted token ID")
    parser_tokens_revoke.set_defaults(func=revoke_humbug_restricted_token)
    parser_tokens_get = subcommands_tokens.add_parser(
        "get", description="Get humbug restricted tokens"
    )
    parser_tokens_get.add_argument("-i", "--id", help="Humbug event integration ID")
    parser_tokens_get.set_defaults(func=get_humbug_restricted_tokens)
    parser_tokens_update = subcommands_tokens.add_parser(
        "update", description="Update humbug restricted token"
    )
    parser_tokens_update.add_argument(
        "-r", "--restricted_token_id", required=True, help="Restricted token ID"
    )
    parser_tokens_update.add_argument(
        "-n", "--app_name", type=str, help="Restricted token app name"
    )
    parser_tokens_update.add_argument(
        "-v", "--app_version", type=str, help="Restricted token app version"
    )
    parser_tokens_update.add_argument(
        "-s", "--store_ip", choices=["True", "False"], help="Restricted token store ip"
    )
    parser_tokens_update.set_defaults(func=update_humbug_restricted_token)
    parser_tokens_synchronize = subcommands_tokens.add_parser(
        "synchronize", description="Synchronize humbug restricted tokens"
    )
    parser_tokens_synchronize.set_defaults(func=synchronize_humbug_restricted_token)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
