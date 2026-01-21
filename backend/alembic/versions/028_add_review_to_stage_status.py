"""add review to stage_status enum

Revision ID: 028
Revises: 027
Create Date: 2026-01-18 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL требует специальной команды для добавления значения в ENUM
    # Мы используем execute для raw SQL
    # В транзакционном режиме (который по умолчанию в alembic) ALTER TYPE ... ADD VALUE нельзя запускать
    # Поэтому мы используем commit() перед этим, если возможно, или просто надеемся, что autocommit включен
    # Но в Alembic обычно проще пересоздать тип или использовать хак
    
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE stage_status ADD VALUE IF NOT EXISTS 'review'")


def downgrade():
    # Удаление значения из ENUM в Postgres сложно (требует пересоздания типа)
    # Мы оставим как есть, так как это не критично для отката
    pass
