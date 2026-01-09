"""Add task templates table

Revision ID: 021
Revises: 020
Create Date: 2026-01-09 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '021'
down_revision = '020'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём enum для категорий шаблонов (используем DO блок для обработки дубликатов)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE templatecategory AS ENUM (
                'coordinator_smm', 'coordinator_design', 'coordinator_channel', 
                'coordinator_prfr', 'vp4pr', 'custom'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаём таблицу task_templates
    op.create_table(
        'task_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', postgresql.ENUM(
            'coordinator_smm', 'coordinator_design', 'coordinator_channel', 
            'coordinator_prfr', 'vp4pr', 'custom',
            name='templatecategory',
            create_type=False
        ), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('task_type', postgresql.ENUM('smm', 'design', 'channel', 'prfr', name='task_type', create_type=False), nullable=False),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'critical', name='task_priority', create_type=False), nullable=False),
        sa.Column('default_description', sa.Text(), nullable=True),
        sa.Column('equipment_available', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('role_specific_requirements', postgresql.JSON(), nullable=True),
        sa.Column('questions', postgresql.JSON(), nullable=True),
        sa.Column('example_project_ids', postgresql.JSON(), nullable=True),
        sa.Column('stages_template', postgresql.JSON(), nullable=True),
        sa.Column('drive_file_id', sa.String(), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Создаём индексы
    op.create_index('ix_task_templates_category', 'task_templates', ['category'])
    op.create_index('ix_task_templates_created_by', 'task_templates', ['created_by'])
    op.create_index('ix_task_templates_drive_file_id', 'task_templates', ['drive_file_id'])


def downgrade():
    op.drop_index('ix_task_templates_drive_file_id', table_name='task_templates')
    op.drop_index('ix_task_templates_created_by', table_name='task_templates')
    op.drop_index('ix_task_templates_category', table_name='task_templates')
    op.drop_table('task_templates')
    
    # Удаляем enum
    op.execute('DROP TYPE IF EXISTS templatecategory')
