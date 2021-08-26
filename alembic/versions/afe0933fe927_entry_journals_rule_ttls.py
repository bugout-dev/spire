"""Entry journals rule ttls

Revision ID: afe0933fe927
Revises: 3efbd7688f59
Create Date: 2021-08-26 11:56:45.267757

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'afe0933fe927'
down_revision = '3efbd7688f59'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('journal_ttls',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('journal_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('name', sa.VARCHAR(length=256), nullable=False),
    sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('action', sa.VARCHAR(length=256), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['journal_id'], ['journals.id'], name=op.f('fk_journal_ttls_journal_id_journals'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_journal_ttls'))
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('journal_ttls')
    # ### end Alembic commands ###