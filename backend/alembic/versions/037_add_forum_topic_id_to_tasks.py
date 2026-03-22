"""Add forum_topic_id to tasks for Telegram group topics"""
from alembic import op
import sqlalchemy as sa

revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tasks', sa.Column('forum_topic_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('tasks', 'forum_topic_id')
