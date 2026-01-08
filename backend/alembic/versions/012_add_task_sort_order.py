"""Add task sort_order field for manual task ordering

Revision ID: 012
Revises: 011
Create Date: 2026-01-08 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле sort_order для ручного управления порядком задач (только для VP4PR)
    op.add_column('tasks', sa.Column('sort_order', sa.Integer(), nullable=True))
    
    # Создаём индекс для sort_order (для быстрой сортировки)
    op.create_index('idx_tasks_sort_order', 'tasks', ['sort_order'], unique=False)


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_tasks_sort_order', table_name='tasks')
    
    # Удаляем поле из tasks
    op.drop_column('tasks', 'sort_order')
