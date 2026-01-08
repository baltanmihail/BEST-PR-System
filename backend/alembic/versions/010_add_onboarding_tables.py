"""Add onboarding tables

Revision ID: 010
Revises: 009
Create Date: 2026-01-08 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём таблицу onboarding_responses
    op.create_table(
        'onboarding_responses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_id', sa.String(20), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('experience', sa.Text(), nullable=True),
        sa.Column('goals', sa.Text(), nullable=True),
        sa.Column('motivation', sa.Text(), nullable=True),
        sa.Column('additional_info', postgresql.JSONB(), nullable=True),
        sa.Column('from_website', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('from_qr', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('website_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Создаём индекс для telegram_id
    op.create_index('ix_onboarding_responses_telegram_id', 'onboarding_responses', ['telegram_id'])
    
    # Создаём таблицу onboarding_reminders
    op.create_table(
        'onboarding_reminders',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_id', sa.String(20), nullable=False),
        sa.Column('first_visit_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_reminder_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reminder_count', sa.String(10), nullable=False, server_default='0'),
        sa.Column('time_on_site', sa.String(20), nullable=False, server_default='0'),
        sa.Column('last_visit_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('responded', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('registered', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    
    # Создаём индекс для telegram_id
    op.create_index('ix_onboarding_reminders_telegram_id', 'onboarding_reminders', ['telegram_id'])


def downgrade():
    # Удаляем индексы
    op.drop_index('ix_onboarding_reminders_telegram_id', table_name='onboarding_reminders')
    op.drop_index('ix_onboarding_responses_telegram_id', table_name='onboarding_responses')
    
    # Удаляем таблицы
    op.drop_table('onboarding_reminders')
    op.drop_table('onboarding_responses')
