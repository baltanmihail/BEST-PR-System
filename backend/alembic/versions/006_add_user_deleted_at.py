"""add user deleted_at field

Revision ID: 006
Revises: 005
Create Date: 2026-01-07 20:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем поле deleted_at для мягкого удаления
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    # Создаём индекс для быстрого поиска
    op.create_index('idx_users_deleted_at', 'users', ['deleted_at'])


def downgrade() -> None:
    # Удаляем индекс и поле
    op.drop_index('idx_users_deleted_at', table_name='users')
    op.drop_column('users', 'deleted_at')
