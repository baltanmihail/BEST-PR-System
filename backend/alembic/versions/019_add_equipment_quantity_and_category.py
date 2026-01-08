"""Add quantity and category enum to equipment

Revision ID: 019
Revises: 018
Create Date: 2026-01-08 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '019'
down_revision = '018'
branch_labels = None
depends_on = None


def upgrade():
    # Создаём enum для категорий оборудования
    equipment_category_enum = postgresql.ENUM(
        'camera', 'lens', 'lighting', 'audio', 'tripod', 'accessories', 'storage', 'other',
        name='equipmentcategory',
        create_type=True
    )
    equipment_category_enum.create(op.get_bind(), checkfirst=True)
    
    # Добавляем поле quantity с дефолтным значением 1
    op.add_column('equipment', sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))
    
    # Изменяем тип category с String на ENUM
    # Сначала создаём временную колонку с правильным типом
    op.add_column('equipment', sa.Column('category_new', equipment_category_enum, nullable=True))
    
    # Копируем данные, конвертируя старые значения в новые
    op.execute("""
        UPDATE equipment 
        SET category_new = CASE 
            WHEN category = 'camera' THEN 'camera'::equipmentcategory
            WHEN category = 'lens' THEN 'lens'::equipmentcategory
            WHEN category = 'lighting' THEN 'lighting'::equipmentcategory
            WHEN category = 'audio' THEN 'audio'::equipmentcategory
            WHEN category = 'tripod' THEN 'tripod'::equipmentcategory
            WHEN category = 'accessories' THEN 'accessories'::equipmentcategory
            WHEN category = 'storage' THEN 'storage'::equipmentcategory
            ELSE 'other'::equipmentcategory
        END
    """)
    
    # Удаляем старую колонку
    op.drop_column('equipment', 'category')
    # Переименовываем новую колонку
    op.alter_column('equipment', 'category_new', new_column_name='category')
    op.alter_column('equipment', 'category', nullable=False)
    
    # Добавляем constraint для quantity
    op.create_check_constraint(
        'equipment_quantity_positive',
        'equipment',
        'quantity > 0'
    )


def downgrade():
    # Удаляем constraint
    op.drop_constraint('equipment_quantity_positive', 'equipment', type_='check')
    
    # Изменяем тип category обратно на String
    op.add_column('equipment', sa.Column('category_string', sa.String(), nullable=True))
    op.execute("""
        UPDATE equipment 
        SET category_string = category::text
    """)
    op.drop_column('equipment', 'category')
    op.alter_column('equipment', 'category_string', new_column_name='category')
    op.alter_column('equipment', 'category', nullable=False)
    
    # Удаляем поле quantity
    op.drop_column('equipment', 'quantity')
    
    # Удаляем enum
    op.execute("DROP TYPE IF EXISTS equipmentcategory")
