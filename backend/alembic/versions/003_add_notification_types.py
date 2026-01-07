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
            -- Сначала проверяем, существует ли ENUM notification_type
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_type') THEN
                -- Если ENUM не существует, создаём его со всеми значениями
                CREATE TYPE notification_type AS ENUM (
                    'task_assigned',
                    'task_completed',
                    'task_deadline',
                    'equipment_request',
                    'equipment_approved',
                    'equipment_rejected',
                    'moderation_request',
                    'moderation_approved',
                    'moderation_rejected',
                    'new_task',
                    'task_review',
                    'achievement_unlocked',
                    'support_request'
                );
            ELSE
                -- Если ENUM существует, добавляем только новые значения
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
            END IF;
        END $$;
    """)


def downgrade():
    # В PostgreSQL нельзя удалить значение из ENUM напрямую
    # Нужно пересоздать тип, но это сложно и может сломать данные
    # Оставляем как есть - новые типы не мешают работе
    pass
