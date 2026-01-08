"""Add equipment_request_enabled field to tasks

Revision ID: 016
Revises: 015
Create Date: 2026-01-08 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле для опционального запроса оборудования
    op.add_column('tasks', sa.Column('equipment_request_enabled', sa.Boolean(), nullable=False, server_default='false'))
    
    # Создаём индекс для быстрого поиска задач с возможностью запроса оборудования
    op.create_index('idx_tasks_equipment_request_enabled', 'tasks', ['equipment_request_enabled'])


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_tasks_equipment_request_enabled', table_name='tasks')
    
    # Удаляем поле
    op.drop_column('tasks', 'equipment_request_enabled')
