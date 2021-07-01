"""search_index column in journals

Revision ID: 9f8094ed8bb5
Revises: a6067349a12a
Create Date: 2021-03-06 01:36:44.912803

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9f8094ed8bb5"
down_revision = "a6067349a12a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column("journals", sa.Column("search_index", sa.String(), nullable=True))
    op.create_index(
        op.f("ix_journal_entry_tags_tag"), "journal_entry_tags", ["tag"], unique=False
    )
    # ### end Alembic commands ###
    op.execute("UPDATE journals set search_index='bugout-main';")
    # Humbug journals should have NULL seach_index columns
    # Activeloop - Hub
    op.execute(
        "UPDATE journals set search_index=NULL WHERE id='5e264dc7-72bf-44bb-9b0b-220b7381ad72';"
    )
    # Toolchain Labs - Pants
    op.execute(
        "UPDATE journals set search_index=NULL WHERE id='801e9b3c-6b03-40a7-870f-5b25d326da66';"
    )
    # B612 Asteroid Institute - adam_home
    op.execute(
        "UPDATE journals set search_index=NULL WHERE id='b1163c7b-e54b-4ee9-a76c-69c777140107';"
    )


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("journals", "search_index")
    op.drop_index(op.f("ix_journal_entry_tags_tag"), table_name="journal_entry_tags")
    # ### end Alembic commands ###
