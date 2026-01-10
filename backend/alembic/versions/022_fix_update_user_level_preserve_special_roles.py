"""Fix update_user_level trigger to preserve coordinator and VP4PR roles

Revision ID: 022
Revises: 021
Create Date: 2026-01-09 23:30:00.000000

Fixed critical bug: The update_user_level() trigger function was overwriting
coordinator and VP4PR roles when users received points, demoting them to
regular participants. This fix preserves special roles while still updating
the level based on points.

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '022'
down_revision = '021'
branch_labels = None
depends_on = None


def upgrade():
    """
    Исправляем функцию update_user_level() чтобы сохранять специальные роли
    (координаторы и VP4PR) при обновлении баллов.
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION update_user_level()
        RETURNS TRIGGER AS $$
        DECLARE
            is_special_role_old BOOLEAN := FALSE;
            is_special_role_new BOOLEAN := FALSE;
        BEGIN
            -- Проверяем, является ли старая роль специальной (координатор или VP4PR)
            is_special_role_old := OLD.role IN (
                'coordinator_smm',
                'coordinator_design',
                'coordinator_channel',
                'coordinator_prfr',
                'vp4pr'
            );
            
            -- Проверяем, является ли новая роль специальной (на случай, если роль меняется явно вместе с баллами)
            is_special_role_new := NEW.role IN (
                'coordinator_smm',
                'coordinator_design',
                'coordinator_channel',
                'coordinator_prfr',
                'vp4pr'
            );
            
            -- Обновляем level на основе баллов (всегда)
            IF NEW.points < 101 THEN
                NEW.level := 1;
            ELSIF NEW.points < 501 THEN
                NEW.level := 2;
            ELSIF NEW.points < 1501 THEN
                NEW.level := 3;
            ELSIF NEW.points < 3001 THEN
                NEW.level := 4;
            ELSE
                NEW.level := 5;
            END IF;
            
            -- Обновляем role только если это НЕ специальная роль (ни старая, ни новая)
            -- Если роль специальная (в OLD или NEW) - сохраняем её, обновляем только level
            IF is_special_role_new THEN
                -- Новая роль явно установлена как специальная - сохраняем её (явное назначение координатора)
                -- NEW.role уже правильная, ничего не меняем
                NULL;
            ELSIF is_special_role_old THEN
                -- Была специальная роль, новая не специальная - сохраняем специальную (защита от случайного понижения)
                -- Если нужно действительно понизить координатора, это нужно делать в отдельном UPDATE без изменения баллов
                NEW.role := OLD.role;
            ELSE
                -- Роль не специальная (ни в OLD, ни в NEW) - можем обновить на основе баллов
                IF NEW.points < 101 THEN
                    NEW.role := 'novice';
                ELSIF NEW.points < 501 THEN
                    NEW.role := 'participant';
                ELSIF NEW.points < 1501 THEN
                    NEW.role := 'active_participant';
                ELSIF NEW.points < 3001 THEN
                    NEW.role := 'active_participant';
                ELSE
                    NEW.role := 'active_participant';
                END IF;
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Создаём триггер, если его ещё нет (для новых БД или если он был удалён)
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger 
                WHERE tgname = 'update_level_on_points_change'
            ) THEN
                CREATE TRIGGER update_level_on_points_change 
                    BEFORE UPDATE OF points ON users
                    FOR EACH ROW 
                    WHEN (NEW.points IS DISTINCT FROM OLD.points)
                    EXECUTE FUNCTION update_user_level();
            END IF;
        END $$;
    """)


def downgrade():
    """
    Возвращаем старую версию функции (которая перезаписывала все роли)
    ВНИМАНИЕ: Это вернёт баг, который перезаписывает роли координаторов!
    """
    op.execute("""
        CREATE OR REPLACE FUNCTION update_user_level()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Обновляем уровень на основе баллов
            IF NEW.points < 101 THEN
                NEW.level := 1;
                NEW.role := 'novice';
            ELSIF NEW.points < 501 THEN
                NEW.level := 2;
                NEW.role := 'participant';
            ELSIF NEW.points < 1501 THEN
                NEW.level := 3;
                NEW.role := 'active_participant';
            ELSIF NEW.points < 3001 THEN
                NEW.level := 4;
                NEW.role := 'active_participant';
            ELSE
                NEW.level := 5;
                NEW.role := 'active_participant';
            END IF;
            
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # При откате триггер остаётся, но функция возвращается к старой версии
    # Триггер не нужно удалять - он будет использовать старую версию функции
