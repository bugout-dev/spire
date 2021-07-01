"""Created slack_bugout_users table

Revision ID: fb4a3770e92a
Revises: 7aaf134cf866
Create Date: 2020-08-10 06:16:19.401436

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fb4a3770e92a'
down_revision = '7aaf134cf866'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('slack_bugout_users',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('slack_oauth_event_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('bugout_user_id', sa.String(), nullable=False),
    sa.Column('bugout_access_token', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['slack_oauth_event_id'], ['slack_oauth_events.id'], name='fk_slack_bugout_users_slack_oauth_events_id'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('slack_bugout_users')
    # ### end Alembic commands ###
