"""add drive_file_id to tasks

Revision ID: 029
Revises: 028
Create Date: 2026-01-18 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('drive_file_id', sa.String(), nullable=True))


def downgrade():
    op.drop_column('tasks', 'drive_file_id')
