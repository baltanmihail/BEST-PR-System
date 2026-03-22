"""Add scheduled_time and priority to daily_tasks"""
from alembic import op
import sqlalchemy as sa

revision = '038'
down_revision = '037'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    for col, coldef in [("scheduled_time", "TIME"), ("priority", "INTEGER DEFAULT 0")]:
        result = conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='daily_tasks' AND column_name=:col"
        ), {"col": col})
        if result.fetchone() is None:
            op.add_column('daily_tasks', sa.Column(col, sa.Time() if col == 'scheduled_time' else sa.Integer(), nullable=True, server_default='0' if col == 'priority' else None))


def downgrade():
    op.drop_column('daily_tasks', 'priority')
    op.drop_column('daily_tasks', 'scheduled_time')
