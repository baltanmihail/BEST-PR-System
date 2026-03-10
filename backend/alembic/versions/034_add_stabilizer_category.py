"""add stabilizer to equipmentcategory enum

Revision ID: 034
Revises: 033
Create Date: 2026-03-10
"""
from alembic import op

revision = '034'
down_revision = '033'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE equipmentcategory ADD VALUE IF NOT EXISTS 'stabilizer'")


def downgrade():
    pass
