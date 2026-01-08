"""Add gallery_items table for project gallery

Revision ID: 014
Revises: 013
Create Date: 2026-01-08 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём enum для категорий галереи
    op.execute("CREATE TYPE gallery_category AS ENUM ('photo', 'video', 'final', 'wip')")
    
    # Создаём таблицу gallery_items
    op.create_table(
        'gallery_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', postgresql.ENUM('photo', 'video', 'final', 'wip', name='gallery_category', create_type=False), nullable=False, server_default='final'),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('files', postgresql.JSON(), nullable=False, server_default='[]'),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint("LENGTH(TRIM(title)) > 0", name="gallery_items_title_not_empty")
    )
    
    # Создаём индексы
    op.create_index('idx_gallery_items_category', 'gallery_items', ['category'])
    op.create_index('idx_gallery_items_task_id', 'gallery_items', ['task_id'])
    op.create_index('idx_gallery_items_created_by', 'gallery_items', ['created_by'])
    op.create_index('idx_gallery_items_sort_order', 'gallery_items', ['sort_order'])
    op.create_index('idx_gallery_items_created_at', 'gallery_items', ['created_at'])


def downgrade():
    # Удаляем индексы
    op.drop_index('idx_gallery_items_created_at', table_name='gallery_items')
    op.drop_index('idx_gallery_items_sort_order', table_name='gallery_items')
    op.drop_index('idx_gallery_items_created_by', table_name='gallery_items')
    op.drop_index('idx_gallery_items_task_id', table_name='gallery_items')
    op.drop_index('idx_gallery_items_category', table_name='gallery_items')
    
    # Удаляем таблицу
    op.drop_table('gallery_items')
    
    # Удаляем enum
    op.execute("DROP TYPE IF EXISTS gallery_category")
