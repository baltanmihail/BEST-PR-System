"""Add user profile fields and online status

Revision ID: 015
Revises: 014
Create Date: 2026-01-08 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля профиля пользователя
    op.add_column('users', sa.Column('profile_photo_url', sa.String(), nullable=True))
    op.add_column('users', sa.Column('bio', sa.String(), nullable=True))
    op.add_column('users', sa.Column('contacts', sa.String(), nullable=True))
    op.add_column('users', sa.Column('skills', sa.String(), nullable=True))
    op.add_column('users', sa.Column('portfolio_links', sa.String(), nullable=True))
    
    # Добавляем онлайн-статус
    op.add_column('users', sa.Column('is_online', sa.Boolean(), nullable=False, server_default='false'))
    
    # Создаём индекс для онлайн-статуса
    op.create_index('idx_users_is_online', 'users', ['is_online'])


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_users_is_online', table_name='users')
    
    # Удаляем поля
    op.drop_column('users', 'is_online')
    op.drop_column('users', 'portfolio_links')
    op.drop_column('users', 'skills')
    op.drop_column('users', 'contacts')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'profile_photo_url')
