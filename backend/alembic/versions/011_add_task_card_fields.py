"""Add task card fields (thumbnail, role requirements, questions, examples)

Revision ID: 011
Revises: 010
Create Date: 2026-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011'
down_revision = '010'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля для карточки задачи
    op.add_column('tasks', sa.Column('thumbnail_image_url', sa.String(), nullable=True))
    op.add_column('tasks', sa.Column('role_specific_requirements', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('tasks', sa.Column('questions', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    op.add_column('tasks', sa.Column('example_project_ids', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    
    # Создаём индекс для thumbnail_image_url (для быстрого поиска задач с превью)
    op.create_index('idx_tasks_thumbnail_image_url', 'tasks', ['thumbnail_image_url'], unique=False, postgresql_where=sa.text('thumbnail_image_url IS NOT NULL'))


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_tasks_thumbnail_image_url', table_name='tasks')
    
    # Удаляем поля из tasks
    op.drop_column('tasks', 'example_project_ids')
    op.drop_column('tasks', 'questions')
    op.drop_column('tasks', 'role_specific_requirements')
    op.drop_column('tasks', 'thumbnail_image_url')
