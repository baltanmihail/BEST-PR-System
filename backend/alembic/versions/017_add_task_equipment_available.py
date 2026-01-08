"""Add equipment_available field to tasks table

Revision ID: 017
Revises: 016
Create Date: 2026-01-08 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '017'
down_revision = '016'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле equipment_available для отметки возможности получения оборудования (для Channel задач)
    op.add_column('tasks', sa.Column('equipment_available', sa.Boolean(), nullable=False, server_default='false'))
    
    # Создаём индекс для equipment_available (для быстрого поиска задач с доступным оборудованием)
    op.create_index('idx_tasks_equipment_available', 'tasks', ['equipment_available'], unique=False)


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_tasks_equipment_available', table_name='tasks')
    
    # Удаляем поле из tasks
    op.drop_column('tasks', 'equipment_available')
