"""Add user consent fields

Revision ID: 005
Revises: 004
Create Date: 2026-01-07 15:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем поля согласия на обработку персональных данных
    op.add_column('users', sa.Column('personal_data_consent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('consent_date', sa.DateTime(timezone=True), nullable=True))
    
    # Добавляем поля пользовательского соглашения
    op.add_column('users', sa.Column('user_agreement_accepted', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('agreement_version', sa.String(), nullable=True))
    op.add_column('users', sa.Column('agreement_accepted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column('users', 'agreement_accepted_at')
    op.drop_column('users', 'agreement_version')
    op.drop_column('users', 'user_agreement_accepted')
    op.drop_column('users', 'consent_date')
    op.drop_column('users', 'personal_data_consent')
