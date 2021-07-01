"""Hard deletes on SlackOauthEvent

Revision ID: daa0a74da38b
Revises: 419fd8c9ae41
Create Date: 2020-08-14 06:47:07.981471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'daa0a74da38b'
down_revision = '419fd8c9ae41'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('slack_oauth_events', 'deleted')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('slack_oauth_events', sa.Column('deleted', sa.BOOLEAN(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
