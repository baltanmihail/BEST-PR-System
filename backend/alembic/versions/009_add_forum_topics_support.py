"""Add forum topics support

Revision ID: 009
Revises: 008
Create Date: 2026-01-07 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля для работы с темами (Topics)
    op.add_column('telegram_chats', sa.Column('topic_id', sa.BigInteger(), nullable=True))
    op.add_column('telegram_chats', sa.Column('topic_name', sa.String(), nullable=True))
    op.add_column('telegram_chats', sa.Column('is_open_topic', sa.Boolean(), nullable=False, server_default='true'))
    
    # Создаём индекс для topic_id
    op.create_index('idx_telegram_chats_topic_id', 'telegram_chats', ['topic_id'])


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_telegram_chats_topic_id', table_name='telegram_chats')
    
    # Удаляем поля
    op.drop_column('telegram_chats', 'is_open_topic')
    op.drop_column('telegram_chats', 'topic_name')
    op.drop_column('telegram_chats', 'topic_id')
