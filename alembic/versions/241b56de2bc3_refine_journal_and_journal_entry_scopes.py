"""Refine journal (and journal entry) scopes

Revision ID: 241b56de2bc3
Revises: 09183222bda3
Create Date: 2021-01-20 12:46:28.124384

"""
from sqlalchemy.sql.expression import update
from alembic import op
import sqlalchemy as sa

from spire.utils.confparse import scope_conf
from spire.journal.models import SpireOAuthScopes


# revision identifiers, used by Alembic.
revision = "241b56de2bc3"
down_revision = "09183222bda3"
branch_labels = None
depends_on = None


NEW_SCOPES = [
    "journals.read",
    "journals.update",
    "journals.delete",
    "journals.entries.read",
    "journals.entries.create",
    "journals.entries.update",
    "journals.entries.delete",
]


def get_scope_description(scope):
    scope_components = scope.split(".")
    current_object = scope_conf
    for component in scope_components:
        current_object = current_object[component]
    assert current_object == str(current_object)
    return current_object


def upgrade():
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals.v0', scope = 'journals.read.v0' WHERE api = 'journals' AND scope = 'journals.read';"
    )
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals.v0', scope = 'journals.update.v0' WHERE api = 'journals' AND scope = 'journals.update';"
    )
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals.v0', scope = 'journals.delete.v0' WHERE api = 'journals' AND scope = 'journals.delete';"
    )
    op.bulk_insert(
        SpireOAuthScopes.__table__,
        [
            {
                "api": "journals",
                "scope": scope,
                "description": get_scope_description(scope),
            }
            for scope in NEW_SCOPES
        ],
    )

    # We add updated permissions for existing holders using the Postgresql DO statement:
    # https://www.postgresql.org/docs/12/sql-do.html
    update_journals_read_permissions_query = """
DO $$DECLARE existing_permission RECORD;
BEGIN
    FOR existing_permission IN
        SELECT journal_id, holder_id, holder_type, permission FROM journal_permissions WHERE permission = 'journals.read.v0'
    LOOP
        INSERT INTO journal_permissions (journal_id, holder_id, holder_type, permission) VALUES
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.read'),
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.entries.read');
    END LOOP;
END$$;
"""
    op.execute(update_journals_read_permissions_query)

    update_journals_delete_permissions_query = """
DO $$DECLARE existing_permission RECORD;
BEGIN
    FOR existing_permission IN
        SELECT journal_id, holder_id, holder_type, permission FROM journal_permissions WHERE permission = 'journals.delete.v0'
    LOOP
        INSERT INTO journal_permissions (journal_id, holder_id, holder_type, permission) VALUES
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.delete');
    END LOOP;
END$$;
"""
    op.execute(update_journals_delete_permissions_query)

    update_journals_update_permissions_query = """
DO $$DECLARE existing_permission RECORD;
BEGIN
    FOR existing_permission IN
        SELECT journal_id, holder_id, holder_type, permission FROM journal_permissions WHERE permission = 'journals.update.v0'
    LOOP
        INSERT INTO journal_permissions (journal_id, holder_id, holder_type, permission) VALUES
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.update'),
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.entries.create'),
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.entries.update'),
        (existing_permission.journal_id, existing_permission.holder_id, existing_permission.holder_type, 'journals.entries.delete');
    END LOOP;
END$$;
"""
    op.execute(update_journals_update_permissions_query)


def downgrade():
    quoted_scopes_to_delete = [f"'{scope}'" for scope in NEW_SCOPES]
    op.execute(
        f"DELETE FROM spire_oauth_scopes WHERE scope IN ({','.join(quoted_scopes_to_delete)});"
    )
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals', scope = 'journals.read' WHERE api = 'journals.v0' AND scope = 'journals.read.v0';"
    )
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals', scope = 'journals.update' WHERE api = 'journals.v0' AND scope = 'journals.update.v0';"
    )
    op.execute(
        "UPDATE spire_oauth_scopes SET api = 'journals', scope = 'journals.delete' WHERE api = 'journals.v0' AND scope = 'journals.delete.v0';"
    )
