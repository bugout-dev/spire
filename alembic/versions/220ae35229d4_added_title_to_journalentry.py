"""Added title to JournalEntry

Revision ID: 220ae35229d4
Revises: 97ce2c81e19b
Create Date: 2020-08-13 17:57:17.110275

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "220ae35229d4"
down_revision = "97ce2c81e19b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "journal_entries", sa.Column("title", sa.String(length=100), nullable=True)
    )
    op.execute("UPDATE journal_entries SET title = 'Untitled'")
    op.alter_column("journal_entries", "title", nullable=False)


def downgrade():
    op.drop_column("journal_entries", "title")
