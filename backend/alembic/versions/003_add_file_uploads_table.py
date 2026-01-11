"""Add file_uploads table for moderation

Revision ID: 003_file_uploads
Revises: 002
Create Date: 2026-01-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_file_uploads'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    file_upload_status = postgresql.ENUM(
        'pending', 'approved', 'rejected',
        name='file_upload_status'
    )
    file_upload_category = postgresql.ENUM(
        'task_material', 'gallery', 'template', 'equipment_photo', 'other',
        name='file_upload_category'
    )
    
    # Check and create enums
    conn = op.get_bind()
    
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'file_upload_status'"
    ))
    if not result.fetchone():
        file_upload_status.create(conn)
    
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'file_upload_category'"
    ))
    if not result.fetchone():
        file_upload_category.create(conn)
    
    # Create table
    op.create_table(
        'file_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('uploaded_by_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size', sa.BigInteger(), nullable=False),
        sa.Column('temp_drive_id', sa.String(100), nullable=True),
        sa.Column('final_drive_id', sa.String(100), nullable=True),
        sa.Column('drive_url', sa.String(500), nullable=True),
        sa.Column('category', postgresql.ENUM(
            'task_material', 'gallery', 'template', 'equipment_photo', 'other',
            name='file_upload_category', create_type=False
        ), nullable=False, default='other'),
        sa.Column('task_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('tasks.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM(
            'pending', 'approved', 'rejected',
            name='file_upload_status', create_type=False
        ), nullable=False, default='pending', index=True),
        sa.Column('moderated_by_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('moderated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('file_uploads')
