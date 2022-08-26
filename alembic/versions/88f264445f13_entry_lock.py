"""Entry lock

Revision ID: 88f264445f13
Revises: 245914e1ddf9
Create Date: 2022-08-25 16:18:01.167287

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '88f264445f13'
down_revision = '245914e1ddf9'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('journal_entries', sa.Column('locked_by', sa.String(), nullable=True))
    op.create_index(op.f('ix_journal_entries_locked_by'), 'journal_entries', ['locked_by'], unique=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_journal_entries_locked_by'), table_name='journal_entries')
    op.drop_column('journal_entries', 'locked_by')

    # ### end Alembic commands ###
