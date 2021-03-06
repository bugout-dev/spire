"""configure github journal

Revision ID: a6067349a12a
Revises: 8fff7d10f85b
Create Date: 2021-02-05 13:06:40.878139

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a6067349a12a'
down_revision = '8fff7d10f85b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('github_index_configurations',
    sa.Column('github_oauth_event_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('index_name', sa.String(), nullable=False),
    sa.Column('index_url', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.Column('use_bugout_auth', sa.Boolean(), nullable=False),
    sa.Column('use_bugout_client_id', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['github_oauth_event_id'], ['github_oauth_events.id'], name=op.f('fk_github_index_configurations_github_oauth_event_id_github_oauth_events'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('github_oauth_event_id', 'index_name', name=op.f('pk_github_index_configurations'))
    )
    op.create_table('github_locusts',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('issue_pr_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('terminal_hash', sa.String(), nullable=False),
    sa.Column('s3_uri', sa.String(), nullable=True),
    sa.Column('response_url', sa.String(), nullable=True),
    sa.Column('commented_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['issue_pr_id'], ['github_issues_prs.id'], name=op.f('fk_github_locusts_issue_pr_id_github_issues_prs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_locusts')),
    sa.UniqueConstraint('id', name=op.f('uq_github_locusts_id'))
    )

    op.add_column('github_issues_prs', sa.Column('branch', sa.String(), nullable=True))
    op.add_column('github_issues_prs', sa.Column('entry_id', sa.String(), nullable=True))

    # Manual part
    op.execute(
        "INSERT INTO github_locusts(id, issue_pr_id, terminal_hash, s3_uri, response_url, "
        "commented_at, created_at) SELECT id, issue_pr_id, terminal_hash, s3_uri, response_url, "
        "commented_at, created_at FROM github_summaries;"
    )
    op.drop_table('github_summaries')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('github_issues_prs', 'entry_id')
    op.drop_column('github_issues_prs', 'branch')

    # Manual part
    op.create_table('github_summaries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('issue_pr_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('terminal_hash', sa.String(), nullable=False),
        sa.Column('s3_uri', sa.String(), nullable=True),
        sa.Column('response_url', sa.String(), nullable=True),
        sa.Column('commented_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
        sa.ForeignKeyConstraint(['issue_pr_id'], ['github_issues_prs.id'], name=op.f('fk_github_summaries_issue_pr_id_github_issues_prs'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_github_summaries')),
        sa.UniqueConstraint('id', name=op.f('uq_github_summaries_id'))
    )
    op.execute(
        "INSERT INTO github_summaries(id, issue_pr_id, terminal_hash, s3_uri, response_url, "
        "commented_at, created_at) SELECT id, issue_pr_id, terminal_hash, s3_uri, response_url, "
        "commented_at, created_at FROM github_locusts;"
    )
    
    # Alembic part
    op.drop_table('github_locusts')
    op.drop_table('github_index_configurations')
    # ### end Alembic commands ###
