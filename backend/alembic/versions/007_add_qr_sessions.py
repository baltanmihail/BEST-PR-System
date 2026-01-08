"""Add QR sessions table

Revision ID: 007
Revises: 006
Create Date: 2026-01-08 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём таблицу qr_sessions
    op.create_table(
        'qr_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('session_token', sa.String(64), nullable=False, unique=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('telegram_id', sa.BigInteger(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    # Создаём индексы
    op.create_index('idx_qr_sessions_token', 'qr_sessions', ['session_token'])
    op.create_index('idx_qr_sessions_status', 'qr_sessions', ['status'])
    op.create_index('idx_qr_sessions_telegram_id', 'qr_sessions', ['telegram_id'])
    op.create_index('idx_qr_sessions_expires_at', 'qr_sessions', ['expires_at'])


def downgrade() -> None:
    # Удаляем индексы
    op.drop_index('idx_qr_sessions_expires_at', table_name='qr_sessions')
    op.drop_index('idx_qr_sessions_telegram_id', table_name='qr_sessions')
    op.drop_index('idx_qr_sessions_status', table_name='qr_sessions')
    op.drop_index('idx_qr_sessions_token', table_name='qr_sessions')
    
    # Удаляем таблицу
    op.drop_table('qr_sessions')
