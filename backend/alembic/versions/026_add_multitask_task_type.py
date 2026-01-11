"""add multitask task type

Revision ID: 026
Revises: 025
Create Date: 2026-01-11 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '026'
down_revision = '025'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем значение 'multitask' в ENUM task_type
    op.execute("""
        DO $$ 
        BEGIN
            -- Проверяем, существует ли значение 'multitask'
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'multitask' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'task_type')
            ) THEN
                ALTER TYPE task_type ADD VALUE 'multitask';
            END IF;
        END $$;
    """)


def downgrade():
    # В PostgreSQL нельзя удалить значение из ENUM напрямую
    # Нужно пересоздать тип, но это сложно и может сломать данные
    # Оставляем как есть - новое значение не мешает работе
    pass
