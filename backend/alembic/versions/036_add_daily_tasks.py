"""Add daily_tasks table for quick planner tasks"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '036'
down_revision = '035'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_name='daily_tasks'"
    ))
    if result.fetchone() is not None:
        return

    op.create_table(
        'daily_tasks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('date', sa.Date(), nullable=False, index=True),
        sa.Column('is_done', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creator_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('assignee_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_daily_tasks_date', 'daily_tasks', ['date'])
    op.create_index('ix_daily_tasks_assignee_date', 'daily_tasks', ['assignee_id', 'date'])


def downgrade():
    op.drop_index('ix_daily_tasks_assignee_date')
    op.drop_index('ix_daily_tasks_date')
    op.drop_table('daily_tasks')
