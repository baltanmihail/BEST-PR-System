"""Add tour completed and telegram chat fields

Revision ID: 008
Revises: 007
Create Date: 2026-01-07 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля для интерактивного гайда в users
    op.add_column('users', sa.Column('tour_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('tour_completed_at', sa.DateTime(timezone=True), nullable=True))
    
    # Обновляем таблицу telegram_chats для поддержки общего чата
    # Делаем task_id nullable для общего чата
    op.alter_column('telegram_chats', 'task_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=True)
    
    # Удаляем уникальное ограничение на task_id (так как теперь может быть общий чат без task_id)
    op.drop_constraint('telegram_chats_task_unique', 'telegram_chats', type_='unique')
    
    # Добавляем новые поля в telegram_chats
    op.add_column('telegram_chats', sa.Column('chat_name', sa.String(), nullable=True))
    op.add_column('telegram_chats', sa.Column('invite_link', sa.String(), nullable=True))
    op.add_column('telegram_chats', sa.Column('is_general', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('telegram_chats', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('telegram_chats', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')))
    
    # Создаём индексы для новых полей
    op.create_index('idx_telegram_chats_is_general', 'telegram_chats', ['is_general'])
    op.create_index('idx_users_tour_completed', 'users', ['tour_completed'])


def downgrade():
    # Удаляем индексы
    op.drop_index('idx_users_tour_completed', table_name='users')
    op.drop_index('idx_telegram_chats_is_general', table_name='telegram_chats')
    
    # Удаляем поля из telegram_chats
    op.drop_column('telegram_chats', 'updated_at')
    op.drop_column('telegram_chats', 'is_active')
    op.drop_column('telegram_chats', 'is_general')
    op.drop_column('telegram_chats', 'invite_link')
    op.drop_column('telegram_chats', 'chat_name')
    
    # Восстанавливаем уникальное ограничение
    op.create_unique_constraint('telegram_chats_task_unique', 'telegram_chats', ['task_id'])
    
    # Возвращаем task_id как обязательное поле
    op.alter_column('telegram_chats', 'task_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False)
    
    # Удаляем поля из users
    op.drop_column('users', 'tour_completed_at')
    op.drop_column('users', 'tour_completed')
