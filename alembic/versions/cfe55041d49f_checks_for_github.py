"""Checks for GitHub

Revision ID: cfe55041d49f
Revises: a760c9157e9e
Create Date: 2020-11-30 12:36:09.724628

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cfe55041d49f'
down_revision = 'a760c9157e9e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    
    # Manually. There is constraint wich blocks upgrade head, because was sat manually
    # in previous github migration, it should be dropped only once.
    op.execute("ALTER TABLE github_diffs DROP CONSTRAINT IF EXISTS fk_github_diffs_installation_id;")

    # Auto
    op.add_column('github_oauth_events', sa.Column('github_account_id', sa.Integer(), nullable=False))
    op.add_column('github_oauth_events', sa.Column('github_installation_id', sa.Integer(), nullable=False))
    op.add_column('github_oauth_events', sa.Column('github_installation_url', sa.String(), nullable=False))
    op.create_unique_constraint(op.f('uq_github_oauth_events_github_account_id'), 'github_oauth_events', ['github_account_id'])
    op.create_unique_constraint(op.f('uq_github_oauth_events_github_installation_id'), 'github_oauth_events', ['github_installation_id'])
    op.create_unique_constraint(op.f('uq_github_oauth_events_github_installation_url'), 'github_oauth_events', ['github_installation_url'])
    
    op.create_table('github_repos',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('github_repo_id', sa.Integer(), nullable=False),
    sa.Column('github_repo_name', sa.String(), nullable=False),
    sa.Column('github_repo_url', sa.String(), nullable=False),
    sa.Column('private', sa.Boolean(), nullable=False),
    sa.Column('default_branch', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['github_oauth_events.id'], name=op.f('fk_github_repos_event_id_github_oauth_events'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_repos')),
    sa.UniqueConstraint('id', name=op.f('uq_github_repos_id'))
    )
    op.create_table('github_issues_prs',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('repo_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('comments_url', sa.String(), nullable=True),
    sa.Column('terminal_hash', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['github_oauth_events.id'], name=op.f('fk_github_issues_prs_event_id_github_oauth_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['repo_id'], ['github_repos.id'], name=op.f('fk_github_issues_prs_repo_id_github_repos'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_issues_prs')),
    sa.UniqueConstraint('id', name=op.f('uq_github_issues_prs_id'))
    )
    op.create_table('github_checks',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('issue_pr_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('repo_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('github_check_id', sa.Integer(), nullable=False),
    sa.Column('github_check_name', sa.String(), nullable=False),
    sa.Column('github_status', sa.String(), nullable=True),
    sa.Column('github_conclusion', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['github_oauth_events.id'], name=op.f('fk_github_checks_event_id_github_oauth_events'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['issue_pr_id'], ['github_issues_prs.id'], name=op.f('fk_github_checks_issue_pr_id_github_issues_prs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['repo_id'], ['github_repos.id'], name=op.f('fk_github_checks_repo_id_github_repos'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_checks')),
    sa.UniqueConstraint('id', name=op.f('uq_github_checks_id'))
    )
    op.create_table('github_check_notes',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('check_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('note', sa.String(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=False),
    sa.Column('accepted', sa.Boolean(), nullable=False),
    sa.Column('accepted_by', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text("TIMEZONE('utc', statement_timestamp())"), nullable=False),
    sa.ForeignKeyConstraint(['check_id'], ['github_checks.id'], name=op.f('fk_github_check_notes_check_id_github_checks'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_github_check_notes')),
    sa.UniqueConstraint('id', name=op.f('uq_github_check_notes_id'))
    )
    
    op.drop_constraint('uq_github_oauth_events_account_id', 'github_oauth_events', type_='unique')
    op.drop_constraint('uq_github_oauth_events_installation_id', 'github_oauth_events', type_='unique')
    op.drop_constraint('uq_github_oauth_events_installation_url', 'github_oauth_events', type_='unique')
    op.drop_column('github_oauth_events', 'account_id')
    op.drop_column('github_oauth_events', 'installation_url')
    op.drop_column('github_oauth_events', 'installation_id')
    op.add_column('github_summaries', sa.Column('issue_pr_id', postgresql.UUID(as_uuid=True), nullable=False))
    op.drop_constraint('fk_github_summaries_diff_id', 'github_summaries', type_='foreignkey')
    op.create_foreign_key(op.f('fk_github_summaries_issue_pr_id_github_issues_prs'), 'github_summaries', 'github_issues_prs', ['issue_pr_id'], ['id'], ondelete='CASCADE')
    op.drop_column('github_summaries', 'diff_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('github_summaries', sa.Column('diff_id', postgresql.UUID(), autoincrement=False, nullable=False))
    op.drop_constraint(op.f('fk_github_summaries_issue_pr_id_github_issues_prs'), 'github_summaries', type_='foreignkey')
    op.create_foreign_key('fk_github_summaries_diff_id', 'github_summaries', 'github_diffs', ['diff_id'], ['id'], ondelete='CASCADE')
    op.drop_column('github_summaries', 'issue_pr_id')
    op.add_column('github_oauth_events', sa.Column('installation_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.add_column('github_oauth_events', sa.Column('installation_url', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('github_oauth_events', sa.Column('account_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.create_unique_constraint('uq_github_oauth_events_installation_url', 'github_oauth_events', ['installation_url'])
    op.create_unique_constraint('uq_github_oauth_events_installation_id', 'github_oauth_events', ['installation_id'])
    op.create_unique_constraint('uq_github_oauth_events_account_id', 'github_oauth_events', ['account_id'])
    op.drop_constraint(op.f('uq_github_oauth_events_github_installation_url'), 'github_oauth_events', type_='unique')
    op.drop_constraint(op.f('uq_github_oauth_events_github_installation_id'), 'github_oauth_events', type_='unique')
    op.drop_constraint(op.f('uq_github_oauth_events_github_account_id'), 'github_oauth_events', type_='unique')
    op.drop_column('github_oauth_events', 'github_installation_url')
    op.drop_column('github_oauth_events', 'github_installation_id')
    op.drop_column('github_oauth_events', 'github_account_id')
    op.drop_table('github_check_notes')
    op.drop_table('github_checks')
    op.drop_table('github_issues_prs')
    op.drop_table('github_repos')
    # ### end Alembic commands ###
