"""Add Google Drive fields to Task model

Revision ID: 020
Revises: 019
Create Date: 2026-01-09 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '020'
down_revision = '019'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле drive_folder_id для хранения ID папки задачи в Google Drive
    op.add_column('tasks', sa.Column('drive_folder_id', sa.String(), nullable=True))
    
    # Добавляем индекс для быстрого поиска задач по drive_folder_id
    op.create_index('ix_tasks_drive_folder_id', 'tasks', ['drive_folder_id'], unique=False)
    
    # Добавляем поле drive_last_sync для отслеживания времени последней синхронизации
    op.add_column('tasks', sa.Column('drive_last_sync', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Удаляем индекс
    op.drop_index('ix_tasks_drive_folder_id', table_name='tasks')
    
    # Удаляем поля
    op.drop_column('tasks', 'drive_last_sync')
    op.drop_column('tasks', 'drive_folder_id')
