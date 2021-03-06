"""humbug integration init

Revision ID: d63f160eba77
Revises: 9f8094ed8bb5
Create Date: 2021-03-11 10:29:54.744902

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd63f160eba77'
down_revision = '9f8094ed8bb5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('humbug_events',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('journal_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_humbug_events')),
    sa.UniqueConstraint('group_id', 'journal_id', name=op.f('uq_humbug_events_group_id')),
    sa.UniqueConstraint('id', name=op.f('uq_humbug_events_id'))
    )
    op.create_table('humbug_bugout_users',
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('access_token_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['humbug_events.id'], name=op.f('fk_humbug_bugout_users_event_id_humbug_events'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_humbug_bugout_users')),
    sa.UniqueConstraint('event_id', 'user_id', name=op.f('uq_humbug_bugout_users_event_id')),
    sa.UniqueConstraint('user_id', name=op.f('uq_humbug_bugout_users_user_id'))
    )
    op.create_table('humbug_bugout_user_tokens',
    sa.Column('restricted_token_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
    sa.Column('app_name', sa.String(), nullable=False),
    sa.Column('app_version', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['humbug_events.id'], name=op.f('fk_humbug_bugout_user_tokens_event_id_humbug_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['humbug_bugout_users.user_id'], name=op.f('fk_humbug_bugout_user_tokens_user_id_humbug_bugout_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('restricted_token_id', name=op.f('pk_humbug_bugout_user_tokens')),
    sa.UniqueConstraint('restricted_token_id', name=op.f('uq_humbug_bugout_user_tokens_restricted_token_id'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('humbug_bugout_user_tokens')
    op.drop_table('humbug_bugout_users')
    op.drop_table('humbug_events')
    # ### end Alembic commands ###
