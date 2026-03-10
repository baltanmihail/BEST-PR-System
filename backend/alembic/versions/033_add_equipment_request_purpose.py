"""add purpose field to equipment_requests

Revision ID: 033
Revises: 032
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa


revision = '033'
down_revision = '032'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('equipment_requests', sa.Column('purpose', sa.String(), nullable=True))


def downgrade():
    op.drop_column('equipment_requests', 'purpose')
