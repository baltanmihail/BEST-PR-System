"""add admin role to userrole enum and update trigger

Revision ID: 039_add_admin_role
Revises: 038_add_daily_task_priority_time
Create Date: 2026-03-23
"""
from alembic import op

revision = '039_add_admin_role'
down_revision = '038_add_daily_task_priority_time'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'admin'")

    op.execute("""
        CREATE OR REPLACE FUNCTION update_user_level()
        RETURNS TRIGGER AS $$
        DECLARE
            is_special_role_old BOOLEAN := FALSE;
            is_special_role_new BOOLEAN := FALSE;
        BEGIN
            is_special_role_old := OLD.role IN (
                'coordinator_smm', 'coordinator_design',
                'coordinator_channel', 'coordinator_prfr',
                'vp4pr', 'admin'
            );
            is_special_role_new := NEW.role IN (
                'coordinator_smm', 'coordinator_design',
                'coordinator_channel', 'coordinator_prfr',
                'vp4pr', 'admin'
            );

            IF NEW.points < 101 THEN NEW.level := 1;
            ELSIF NEW.points < 501 THEN NEW.level := 2;
            ELSIF NEW.points < 1501 THEN NEW.level := 3;
            ELSIF NEW.points < 3001 THEN NEW.level := 4;
            ELSE NEW.level := 5;
            END IF;

            IF is_special_role_new THEN
                NULL;
            ELSIF is_special_role_old THEN
                NEW.role := OLD.role;
            ELSE
                IF NEW.points < 101 THEN NEW.role := 'novice';
                ELSIF NEW.points < 501 THEN NEW.role := 'participant';
                ELSE NEW.role := 'active_participant';
                END IF;
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    pass
