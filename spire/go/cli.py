import argparse
import json

from sqlalchemy.orm import Session

from .models import PermalinkJournal
from ..db import SessionLocal


def list_journals_permalinks(args: argparse.Namespace) -> None:
    """
    Return list of all journal permalinks.
    """
    session = SessionLocal()
    try:
        journal_permalinks = session.query(PermalinkJournal).all()

        journal_permalinks_json = {
            "journals": [
                {
                    "journal_id": str(journal_permalink.journal_id),
                    "permalink": journal_permalink.permalink,
                    "public": journal_permalink.public,
                    "created_at": str(journal_permalink.created_at),
                    "updated_at": str(journal_permalink.updated_at),
                }
                for journal_permalink in journal_permalinks
            ]
        }
        print(json.dumps(journal_permalinks_json))
    except Exception as e:
        print(str(e))

    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Administrative actions for Bugout journals permalinks"
    )
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = parser.add_subparsers(description="Permalinks commands")

    # Permalink journal module
    parser_journals = subcommands.add_parser(
        "journals", description="Journals permalinks"
    )
    parser_journals.set_defaults(func=lambda _: parser_journals.print_help())
    subcommands_journals = parser_journals.add_subparsers(
        description="Journal permalinks commands"
    )
    parser_journals_list = subcommands_journals.add_parser(
        "list", description="List all journals permalinks"
    )
    parser_journals_list.set_defaults(func=list_journals_permalinks)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
