"""Add file_uploads table for file upload moderation

Revision ID: 024
Revises: 023
Create Date: 2026-01-11 14:00:00.000000

Adds file_uploads table for moderating file uploads before they're stored permanently.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '024'
down_revision = '023'
branch_labels = None
depends_on = None


def upgrade():
    # Проверяем и создаём enum для статусов
    conn = op.get_bind()
    
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'file_upload_status'"
    ))
    if not result.fetchone():
        op.execute("CREATE TYPE file_upload_status AS ENUM ('pending', 'approved', 'rejected')")
    
    # Проверяем и создаём enum для категорий
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'file_upload_category'"
    ))
    if not result.fetchone():
        op.execute(
            "CREATE TYPE file_upload_category AS ENUM "
            "('task_material', 'gallery', 'template', 'equipment_photo', 'other')"
        )
    
    # Создаём таблицу
    op.create_table(
        'file_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('uploaded_by_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('temp_drive_id', sa.String(100), nullable=True),
        sa.Column('final_drive_id', sa.String(100), nullable=True),
        sa.Column('drive_url', sa.String(500), nullable=True),
        sa.Column('category', postgresql.ENUM(
            'task_material', 'gallery', 'template', 'equipment_photo', 'other',
            name='file_upload_category', create_type=False
        ), nullable=False, server_default='other'),
        sa.Column('task_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'pending', 'approved', 'rejected',
            name='file_upload_status', create_type=False
        ), nullable=False, server_default='pending'),
        sa.Column('moderated_by_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('moderated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    
    # Создаём индексы
    op.create_index('ix_file_uploads_uploaded_by_id', 'file_uploads', ['uploaded_by_id'])
    op.create_index('ix_file_uploads_task_id', 'file_uploads', ['task_id'])
    op.create_index('ix_file_uploads_status', 'file_uploads', ['status'])
    op.create_index('ix_file_uploads_created_at', 'file_uploads', ['created_at'])


def downgrade():
    # Удаляем индексы
    op.drop_index('ix_file_uploads_created_at', table_name='file_uploads')
    op.drop_index('ix_file_uploads_status', table_name='file_uploads')
    op.drop_index('ix_file_uploads_task_id', table_name='file_uploads')
    op.drop_index('ix_file_uploads_uploaded_by_id', table_name='file_uploads')
    
    # Удаляем таблицу
    op.drop_table('file_uploads')
    
    # Удаляем enum'ы
    op.execute("DROP TYPE IF EXISTS file_upload_status")
    op.execute("DROP TYPE IF EXISTS file_upload_category")
