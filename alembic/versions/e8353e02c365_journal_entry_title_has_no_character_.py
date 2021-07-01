"""Journal entry title has no character limit

Revision ID: e8353e02c365
Revises: 823f9ea79a50
Create Date: 2020-08-18 18:05:12.601801

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e8353e02c365"
down_revision = "823f9ea79a50"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "journal_entries", "title", type_=sa.String, existing_type=sa.String(100)
    )


def downgrade():
    op.alter_column(
        "journal_entries", "title", type_=sa.String(100), existing_type=sa.String
    )
