"""Add task_number field to tasks table

Revision ID: 023
Revises: 022
Create Date: 2026-01-11 01:00:00.000000

Adds task_number field for human-readable task identifiers (TASK-001, TASK-002, ...)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '023'
down_revision = '022'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поле task_number (Integer, уникальное, с индексом)
    op.add_column('tasks', sa.Column('task_number', sa.Integer(), nullable=True))
    
    # Создаём уникальный индекс
    op.create_index('ix_tasks_task_number', 'tasks', ['task_number'], unique=True)
    
    # Заполняем существующие задачи номерами (начиная с 1)
    # Используем PostgreSQL sequence для автоинкремента
    op.execute("""
        DO $$
        DECLARE
            rec RECORD;
            num INTEGER := 1;
        BEGIN
            -- Создаём временную последовательность
            CREATE SEQUENCE IF NOT EXISTS temp_task_number_seq START 1;
            
            -- Обновляем все существующие задачи
            FOR rec IN SELECT id FROM tasks ORDER BY created_at ASC
            LOOP
                UPDATE tasks SET task_number = num WHERE id = rec.id;
                num := num + 1;
            END LOOP;
            
            -- Создаём постоянную последовательность для будущих задач
            DROP SEQUENCE IF EXISTS task_number_seq;
            CREATE SEQUENCE task_number_seq START WITH num;
            
            -- Удаляем временную последовательность
            DROP SEQUENCE IF EXISTS temp_task_number_seq;
        END $$;
    """)
    
    # Создаём функцию для автоматического присвоения номера при создании задачи
    op.execute("""
        CREATE OR REPLACE FUNCTION assign_task_number()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.task_number IS NULL THEN
                NEW.task_number := nextval('task_number_seq');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Создаём триггер для автоматического присвоения номера
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_assign_task_number ON tasks;
        CREATE TRIGGER trigger_assign_task_number
            BEFORE INSERT ON tasks
            FOR EACH ROW
            EXECUTE FUNCTION assign_task_number();
    """)


def downgrade():
    # Удаляем триггер и функцию
    op.execute("DROP TRIGGER IF EXISTS trigger_assign_task_number ON tasks;")
    op.execute("DROP FUNCTION IF EXISTS assign_task_number();")
    
    # Удаляем последовательность
    op.execute("DROP SEQUENCE IF EXISTS task_number_seq;")
    
    # Удаляем индекс и колонку
    op.drop_index('ix_tasks_task_number', table_name='tasks')
    op.drop_column('tasks', 'task_number')
