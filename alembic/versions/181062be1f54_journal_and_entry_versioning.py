"""Journal and entry versioning

Revision ID: 181062be1f54
Revises: fffa1d642e4d
Create Date: 2020-08-12 06:09:23.313137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "181062be1f54"
down_revision = "fffa1d642e4d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "journal_entries", sa.Column("version_id", sa.Integer(), nullable=True)
    )
    op.add_column("journals", sa.Column("version_id", sa.Integer(), nullable=True))

    op.execute("UPDATE journals SET version_id = 1;")
    op.execute("UPDATE journal_entries SET version_id = 1;")

    op.alter_column("journals", "version_id", nullable=False)
    op.alter_column("journal_entries", "version_id", nullable=False)


def downgrade():
    op.drop_column("journals", "version_id")
    op.drop_column("journal_entries", "version_id")
