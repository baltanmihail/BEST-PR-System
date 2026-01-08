"""Fix user profile fields types and rename last_activity

Revision ID: 018
Revises: 017
Create Date: 2026-01-08 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade():
    # Переименовываем last_activity в last_activity_at
    op.alter_column('users', 'last_activity', new_column_name='last_activity_at')
    
    # Переименовываем profile_photo_url в avatar_url
    op.alter_column('users', 'profile_photo_url', new_column_name='avatar_url')
    
    # Изменяем тип bio с String на Text
    op.alter_column('users', 'bio', type_=sa.Text(), existing_type=sa.String(), existing_nullable=True)
    
    # Изменяем тип contacts с String на JSON
    # Сначала создаём временную колонку с правильным типом
    op.add_column('users', sa.Column('contacts_json', postgresql.JSON(), nullable=True))
    # Копируем данные (если есть JSON в строке, парсим, иначе null)
    op.execute("""
        UPDATE users 
        SET contacts_json = CASE 
            WHEN contacts IS NOT NULL AND contacts != '' THEN contacts::json
            ELSE NULL
        END
    """)
    # Удаляем старую колонку
    op.drop_column('users', 'contacts')
    # Переименовываем новую колонку
    op.alter_column('users', 'contacts_json', new_column_name='contacts')
    
    # Изменяем тип skills с String на ARRAY(String)
    op.add_column('users', sa.Column('skills_array', postgresql.ARRAY(sa.String()), nullable=True))
    # Копируем данные (если есть JSON массив в строке, парсим, иначе null)
    op.execute("""
        UPDATE users 
        SET skills_array = CASE 
            WHEN skills IS NOT NULL AND skills != '' THEN ARRAY(SELECT json_array_elements_text(skills::json))
            ELSE NULL
        END
    """)
    op.drop_column('users', 'skills')
    op.alter_column('users', 'skills_array', new_column_name='skills')
    
    # Изменяем тип portfolio_links с String на JSON
    op.add_column('users', sa.Column('portfolio', postgresql.JSON(), nullable=True))
    op.execute("""
        UPDATE users 
        SET portfolio = CASE 
            WHEN portfolio_links IS NOT NULL AND portfolio_links != '' THEN portfolio_links::json
            ELSE NULL
        END
    """)
    op.drop_column('users', 'portfolio_links')
    
    # Удаляем is_online (будем использовать last_activity_at для определения онлайн-статуса)
    op.drop_index('idx_users_is_online', table_name='users')
    op.drop_column('users', 'is_online')
    
    # Создаём индекс для last_activity_at
    op.create_index('idx_users_last_activity_at', 'users', ['last_activity_at'])


def downgrade():
    # Удаляем индекс
    op.drop_index('idx_users_last_activity_at', table_name='users')
    
    # Восстанавливаем is_online
    op.add_column('users', sa.Column('is_online', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index('idx_users_is_online', 'users', ['is_online'])
    
    # Восстанавливаем portfolio_links
    op.add_column('users', sa.Column('portfolio_links', sa.String(), nullable=True))
    op.execute("""
        UPDATE users 
        SET portfolio_links = CASE 
            WHEN portfolio IS NOT NULL THEN portfolio::text
            ELSE NULL
        END
    """)
    op.drop_column('users', 'portfolio')
    
    # Восстанавливаем skills как String
    op.add_column('users', sa.Column('skills_string', sa.String(), nullable=True))
    op.execute("""
        UPDATE users 
        SET skills_string = CASE 
            WHEN skills IS NOT NULL THEN array_to_json(skills)::text
            ELSE NULL
        END
    """)
    op.drop_column('users', 'skills')
    op.alter_column('users', 'skills_string', new_column_name='skills')
    
    # Восстанавливаем contacts как String
    op.add_column('users', sa.Column('contacts_string', sa.String(), nullable=True))
    op.execute("""
        UPDATE users 
        SET contacts_string = CASE 
            WHEN contacts IS NOT NULL THEN contacts::text
            ELSE NULL
        END
    """)
    op.drop_column('users', 'contacts')
    op.alter_column('users', 'contacts_string', new_column_name='contacts')
    
    # Восстанавливаем bio как String
    op.alter_column('users', 'bio', type_=sa.String(), existing_type=sa.Text(), existing_nullable=True)
    
    # Восстанавливаем profile_photo_url
    op.alter_column('users', 'avatar_url', new_column_name='profile_photo_url')
    
    # Восстанавливаем last_activity
    op.alter_column('users', 'last_activity_at', new_column_name='last_activity')
