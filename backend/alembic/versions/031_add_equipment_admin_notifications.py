"""add equipment admin notification tracking (delete on approve/reject)

Revision ID: 031
Revises: 030
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '031'
down_revision = '030'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'equipment_admin_notifications',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('request_id', UUID(as_uuid=True), sa.ForeignKey('equipment_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_equipment_admin_notifications_request_id', 'equipment_admin_notifications', ['request_id'])
    op.create_index('ix_equipment_admin_notifications_telegram_id', 'equipment_admin_notifications', ['telegram_id'])


def downgrade():
    op.drop_index('ix_equipment_admin_notifications_telegram_id', table_name='equipment_admin_notifications')
    op.drop_index('ix_equipment_admin_notifications_request_id', table_name='equipment_admin_notifications')
    op.drop_table('equipment_admin_notifications')
