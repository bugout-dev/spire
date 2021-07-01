"""Description for indices

Revision ID: 9be6d71375dc
Revises: daa0a74da38b
Create Date: 2020-08-14 09:16:08.511134

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9be6d71375dc'
down_revision = 'daa0a74da38b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('slack_index_configurations', sa.Column('description', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('slack_index_configurations', 'description')
    # ### end Alembic commands ###
