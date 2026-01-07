"""Add new notification types

Revision ID: 003
Revises: 002
Create Date: 2026-01-07 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем новые типы уведомлений
    op.execute("""
        DO $$ 
        BEGIN
            -- Добавляем 'moderation_request' если его нет
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'moderation_request' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'notification_type')
            ) THEN
                ALTER TYPE notification_type ADD VALUE 'moderation_request';
            END IF;
            
            -- Добавляем 'support_request' если его нет
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'support_request' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'notification_type')
            ) THEN
                ALTER TYPE notification_type ADD VALUE 'support_request';
            END IF;
        END $$;
    """)


def downgrade():
    # В PostgreSQL нельзя удалить значение из ENUM напрямую
    # Нужно пересоздать тип, но это сложно и может сломать данные
    # Оставляем как есть - новые типы не мешают работе
    pass
