"""add equipment reminder sent dates for deduplication

Revision ID: 030
Revises: 029
Create Date: 2026-01-31

"""
from alembic import op
import sqlalchemy as sa


revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('equipment_requests', sa.Column('issue_reminder_sent_for', sa.Date(), nullable=True))
    op.add_column('equipment_requests', sa.Column('return_reminder_sent_for', sa.Date(), nullable=True))


def downgrade():
    op.drop_column('equipment_requests', 'return_reminder_sent_for')
    op.drop_column('equipment_requests', 'issue_reminder_sent_for')
