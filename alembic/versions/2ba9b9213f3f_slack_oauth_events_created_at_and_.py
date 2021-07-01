"""slack_oauth_events created_at and updated_at fields

Revision ID: 2ba9b9213f3f
Revises: 7ccd3dddf090
Create Date: 2020-08-02 23:17:30.027336

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2ba9b9213f3f'
down_revision = '7ccd3dddf090'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('slack_oauth_events', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False))
    op.add_column('slack_oauth_events', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False))
    op.create_unique_constraint(None, 'slack_oauth_events', ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'slack_oauth_events', type_='unique')
    op.drop_column('slack_oauth_events', 'updated_at')
    op.drop_column('slack_oauth_events', 'created_at')
    # ### end Alembic commands ###
