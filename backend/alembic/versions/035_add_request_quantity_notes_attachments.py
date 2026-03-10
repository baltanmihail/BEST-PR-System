"""Add quantity, notes, attachments to equipment_requests"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '035'
down_revision = '034'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('equipment_requests', sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('equipment_requests', sa.Column('notes', sa.String(), nullable=True))
    op.add_column('equipment_requests', sa.Column('attachments', JSONB(), nullable=True))


def downgrade():
    op.drop_column('equipment_requests', 'attachments')
    op.drop_column('equipment_requests', 'notes')
    op.drop_column('equipment_requests', 'quantity')
