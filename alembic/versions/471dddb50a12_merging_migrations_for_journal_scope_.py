"""Merging migrations for journal scope refinements onto bugout_group_id column addition for slack_bugout_users and github_bugout_users tables

Revision ID: 471dddb50a12
Revises: f1755bf67b88, 241b56de2bc3
Create Date: 2021-01-25 10:40:50.759948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '471dddb50a12'
down_revision = ('f1755bf67b88', '241b56de2bc3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
