"""add task_questions table

Revision ID: 025
Revises: 024
Create Date: 2026-01-11 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '025'
down_revision = '024'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём таблицу task_questions
    op.create_table(
        'task_questions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asked_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('answered_by_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('is_answered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('asked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asked_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['answered_by_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создаём индексы
    op.create_index('ix_task_questions_task_id', 'task_questions', ['task_id'])
    op.create_index('ix_task_questions_asked_by_id', 'task_questions', ['asked_by_id'])
    op.create_index('ix_task_questions_is_answered', 'task_questions', ['is_answered'])
    op.create_index('ix_task_questions_asked_at', 'task_questions', ['asked_at'])


def downgrade():
    # Удаляем индексы
    op.drop_index('ix_task_questions_is_answered', table_name='task_questions')
    op.drop_index('ix_task_questions_asked_by_id', table_name='task_questions')
    op.drop_index('ix_task_questions_task_id', table_name='task_questions')
    
    # Удаляем таблицу
    op.drop_table('task_questions')
