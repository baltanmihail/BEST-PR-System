"""Add task_suggestions table

Revision ID: 004
Revises: 003
Create Date: 2026-01-07 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём ENUM типы для предложений
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE suggestion_type AS ENUM (
                'concept',
                'idea',
                'script',
                'text',
                'other'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE suggestion_status AS ENUM (
                'pending',
                'approved',
                'rejected',
                'in_use'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создаём таблицу task_suggestions
    op.create_table(
        'task_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', postgresql.ENUM('concept', 'idea', 'script', 'text', 'other', name='suggestion_type', create_type=False), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('files', postgresql.JSONB(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'in_use', name='suggestion_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('ai_analysis', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('reviewed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Индексы
    op.create_index('idx_task_suggestions_task_id', 'task_suggestions', ['task_id'])
    op.create_index('idx_task_suggestions_user_id', 'task_suggestions', ['user_id'])
    op.create_index('idx_task_suggestions_type', 'task_suggestions', ['type'])
    op.create_index('idx_task_suggestions_status', 'task_suggestions', ['status'])
    op.create_index('idx_task_suggestions_created_at', 'task_suggestions', ['created_at'], postgresql_ops={'created_at': 'DESC'})


def downgrade():
    op.drop_index('idx_task_suggestions_created_at', table_name='task_suggestions')
    op.drop_index('idx_task_suggestions_status', table_name='task_suggestions')
    op.drop_index('idx_task_suggestions_type', table_name='task_suggestions')
    op.drop_index('idx_task_suggestions_user_id', table_name='task_suggestions')
    op.drop_index('idx_task_suggestions_task_id', table_name='task_suggestions')
    op.drop_table('task_suggestions')
    op.execute('DROP TYPE IF EXISTS suggestion_status')
    op.execute('DROP TYPE IF EXISTS suggestion_type')
