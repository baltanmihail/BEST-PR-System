"""add equipment admin digest (one editable message per coordinator)

Revision ID: 032
Revises: 031
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


revision = '032'
down_revision = '031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'equipment_admin_digest',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_equipment_admin_digest_telegram_id', 'equipment_admin_digest', ['telegram_id'], unique=True)


def downgrade():
    op.drop_index('ix_equipment_admin_digest_telegram_id', table_name='equipment_admin_digest')
    op.drop_table('equipment_admin_digest')
