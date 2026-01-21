"""add stage_id to file_uploads

Revision ID: 027
Revises: 026
Create Date: 2026-01-18 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку stage_id в таблицу file_uploads
    # Используем UUID, так как id в task_stages имеет тип UUID
    op.add_column('file_uploads', sa.Column('stage_id', UUID(as_uuid=True), nullable=True))
    
    # Добавляем внешний ключ на таблицу task_stages
    op.create_foreign_key(
        'fk_file_uploads_stage_id_task_stages',
        'file_uploads', 'task_stages',
        ['stage_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_file_uploads_stage_id_task_stages', 'file_uploads', type_='foreignkey')
    op.drop_column('file_uploads', 'stage_id')
