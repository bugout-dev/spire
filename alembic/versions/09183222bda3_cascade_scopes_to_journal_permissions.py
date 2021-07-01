"""Cascade updates to foreign key from journal_permissions to spire_oauth_scopes

Revision ID: 09183222bda3
Revises: 0c9b33f440d1
Create Date: 2021-01-20 12:35:18.608607

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "09183222bda3"
down_revision = "0c9b33f440d1"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "fk_journal_permissions_spire_oauth_scopes_scope",
        "journal_permissions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_journal_permissions_spire_oauth_scopes_scope",
        "journal_permissions",
        "spire_oauth_scopes",
        ["permission"],
        ["scope"],
        onupdate="CASCADE",
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_journal_permissions_spire_oauth_scopes_scope",
        "journal_permissions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_journal_permissions_spire_oauth_scopes_scope",
        "journal_permissions",
        "spire_oauth_scopes",
        ["permission"],
        ["scope"],
    )
