"""Fix userrole enum name

Revision ID: 002
Revises: 001
Create Date: 2026-01-07 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Проверяем, существует ли старый тип user_role
    op.execute("""
        DO $$ 
        BEGIN
            -- Если существует user_role, переименовываем в userrole
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                -- Сначала переименовываем тип
                ALTER TYPE user_role RENAME TO userrole;
            END IF;
            
            -- Если userrole не существует, создаём его
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                CREATE TYPE userrole AS ENUM (
                    'novice',
                    'participant',
                    'active_participant',
                    'coordinator_smm',
                    'coordinator_design',
                    'coordinator_channel',
                    'coordinator_prfr',
                    'vp4pr'
                );
            END IF;
        END $$;
    """)


def downgrade():
    # Переименовываем обратно в user_role
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                ALTER TYPE userrole RENAME TO user_role;
            END IF;
        END $$;
    """)
