"""Add forum_topic_id to tasks for Telegram group topics"""
from alembic import op
import sqlalchemy as sa

revision = '037'
down_revision = '036'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='tasks' AND column_name='forum_topic_id'"
    ))
    if result.fetchone() is None:
        op.add_column('tasks', sa.Column('forum_topic_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('tasks', 'forum_topic_id')
