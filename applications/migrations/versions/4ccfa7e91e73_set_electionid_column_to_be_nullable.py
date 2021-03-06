"""Set electionId column to be nullable.

Revision ID: 4ccfa7e91e73
Revises: e888908bfa01
Create Date: 2021-05-31 00:21:44.761279

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '4ccfa7e91e73'
down_revision = 'e888908bfa01'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('votes', 'electionId',
               existing_type=mysql.INTEGER(),
               nullable=True)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('votes', 'electionId',
               existing_type=mysql.INTEGER(),
               nullable=False)
    # ### end Alembic commands ###
