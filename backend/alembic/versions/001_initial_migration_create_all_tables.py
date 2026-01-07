"""Initial migration: create all tables

Revision ID: 001
Revises: 
Create Date: 2026-01-05 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание расширений
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')
    
    # Создание ENUM типов (с проверкой существования)
    # Важно: создаём типы ПЕРЕД использованием в таблицах,
    # чтобы SQLAlchemy не пытался их создать автоматически
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM (
                'novice',
                'participant',
                'active_participant',
                'coordinator_smm',
                'coordinator_design',
                'coordinator_channel',
                'coordinator_prfr',
                'vp4pr'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_type AS ENUM (
                'smm',
                'design',
                'channel',
                'prfr'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_priority AS ENUM (
                'low',
                'medium',
                'high',
                'critical'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE task_status AS ENUM (
                'draft',
                'open',
                'assigned',
                'in_progress',
                'review',
                'completed',
                'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE stage_status AS ENUM (
                'pending',
                'in_progress',
                'completed'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE assignment_status AS ENUM (
                'assigned',
                'in_progress',
                'completed',
                'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE equipment_status AS ENUM (
                'available',
                'rented',
                'maintenance',
                'broken'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE equipment_request_status AS ENUM (
                'pending',
                'approved',
                'rejected',
                'active',
                'completed',
                'cancelled'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE moderation_status AS ENUM (
                'pending',
                'approved',
                'rejected'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    # Создание таблиц
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('username', sa.Text(), nullable=True),
        sa.Column('full_name', sa.Text(), nullable=False),
        sa.Column('role', postgresql.ENUM('novice', 'participant', 'active_participant', 'coordinator_smm', 'coordinator_design', 'coordinator_channel', 'coordinator_prfr', 'vp4pr', name='user_role', create_type=False), nullable=False, server_default='novice'),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('streak_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_activity', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    )
    
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('date_start', sa.Date(), nullable=False),
        sa.Column('date_end', sa.Date(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.CheckConstraint('priority >= 1 AND priority <= 10', name='events_priority_check'),
        sa.CheckConstraint('date_end >= date_start', name='events_dates_check'),
    )
    
    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', postgresql.ENUM('smm', 'design', 'channel', 'prfr', name='task_type', create_type=False), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('priority', postgresql.ENUM('low', 'medium', 'high', 'critical', name='task_priority', create_type=False), nullable=False, server_default='medium'),
        sa.Column('status', postgresql.ENUM('draft', 'open', 'assigned', 'in_progress', 'review', 'completed', 'cancelled', name='task_status', create_type=False), nullable=False, server_default='draft'),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('LENGTH(TRIM(title)) > 0', name='tasks_title_not_empty'),
    )
    
    op.create_table(
        'task_stages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('stage_name', sa.Text(), nullable=False),
        sa.Column('stage_order', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'completed', name='stage_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('status_color', sa.Text(), nullable=False, server_default='green'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.CheckConstraint('stage_order > 0', name='task_stages_order_check'),
        sa.CheckConstraint("status_color IN ('green', 'yellow', 'red', 'purple', 'blue')", name='task_stages_color_check'),
    )
    
    op.create_table(
        'task_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_in_task', sa.Text(), nullable=False),
        sa.Column('status', postgresql.ENUM('assigned', 'in_progress', 'completed', 'cancelled', name='assignment_status', create_type=False), nullable=False, server_default='assigned'),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('task_id', 'user_id', 'role_in_task', name='task_assignments_unique'),
        sa.CheckConstraint('rating IS NULL OR (rating >= 1 AND rating <= 5)', name='task_assignments_rating_check'),
    )
    
    op.create_table(
        'equipment',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('category', sa.Text(), nullable=False),
        sa.Column('specs', postgresql.JSONB(), nullable=True),
        sa.Column('status', postgresql.ENUM('available', 'rented', 'maintenance', 'broken', name='equipment_status', create_type=False), nullable=False, server_default='available'),
        sa.Column('current_holder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['current_holder_id'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint('LENGTH(TRIM(name)) > 0', name='equipment_name_not_empty'),
    )
    
    op.create_table(
        'equipment_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('equipment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'active', 'completed', 'cancelled', name='equipment_request_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['equipment_id'], ['equipment.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.CheckConstraint('end_date >= start_date', name='equipment_requests_dates_check'),
    )
    
    op.create_table(
        'telegram_chats',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chat_id', sa.BigInteger(), nullable=False),
        sa.Column('chat_type', sa.Text(), nullable=False, server_default='group'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('task_id', name='telegram_chats_task_unique'),
    )
    
    op.create_table(
        'points_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('points', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('awarded_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='SET NULL'),
    )
    
    op.create_table(
        'achievements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('achievement_type', sa.Text(), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'achievement_type', name='achievements_unique'),
    )
    
    op.create_table(
        'files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('drive_id', sa.Text(), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('file_type', sa.Text(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('LENGTH(TRIM(file_name)) > 0', name='files_file_name_not_empty'),
    )
    
    op.create_table(
        'moderation_queue',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('application_data', postgresql.JSONB(), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', name='moderation_status', create_type=False), nullable=False, server_default='pending'),
        sa.Column('decision_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('decision_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decision_by'], ['users.id'], ondelete='SET NULL'),
    )
    
    op.create_table(
        'activity_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    )
    
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE notification_type AS ENUM (
                'task_assigned',
                'task_completed',
                'task_deadline',
                'equipment_request',
                'equipment_approved',
                'equipment_rejected',
                'moderation_approved',
                'moderation_rejected',
                'new_task',
                'task_review',
                'achievement_unlocked'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)
    
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('type', postgresql.ENUM('task_assigned', 'task_completed', 'task_deadline', 'equipment_request', 'equipment_approved', 'equipment_rejected', 'moderation_approved', 'moderation_rejected', 'new_task', 'task_review', 'achievement_unlocked', name='notification_type', create_type=False), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', sa.String(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Создание индексов
    op.create_index('idx_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_points', 'users', ['points'], postgresql_ops={'points': 'DESC'})
    op.create_index('idx_users_is_active', 'users', ['is_active'])
    
    op.create_index('idx_events_dates', 'events', ['date_start', 'date_end'])
    op.create_index('idx_events_priority', 'events', ['priority'], postgresql_ops={'priority': 'DESC'})
    
    op.create_index('idx_tasks_type', 'tasks', ['type'])
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_priority', 'tasks', ['priority'])
    op.create_index('idx_tasks_due_date', 'tasks', ['due_date'])
    op.create_index('idx_tasks_event_id', 'tasks', ['event_id'])
    op.create_index('idx_tasks_created_by', 'tasks', ['created_by'])
    op.create_index('idx_tasks_created_at', 'tasks', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    op.create_index('idx_task_stages_task_id', 'task_stages', ['task_id'])
    op.create_index('idx_task_stages_status', 'task_stages', ['status'])
    op.create_index('idx_task_stages_due_date', 'task_stages', ['due_date'])
    
    op.create_index('idx_task_assignments_task_id', 'task_assignments', ['task_id'])
    op.create_index('idx_task_assignments_user_id', 'task_assignments', ['user_id'])
    op.create_index('idx_task_assignments_status', 'task_assignments', ['status'])
    
    op.create_index('idx_equipment_category', 'equipment', ['category'])
    op.create_index('idx_equipment_status', 'equipment', ['status'])
    op.create_index('idx_equipment_current_holder', 'equipment', ['current_holder_id'])
    
    op.create_index('idx_equipment_requests_task_id', 'equipment_requests', ['task_id'])
    op.create_index('idx_equipment_requests_equipment_id', 'equipment_requests', ['equipment_id'])
    op.create_index('idx_equipment_requests_user_id', 'equipment_requests', ['user_id'])
    op.create_index('idx_equipment_requests_dates', 'equipment_requests', ['start_date', 'end_date'])
    op.create_index('idx_equipment_requests_status', 'equipment_requests', ['status'])
    
    op.create_index('idx_telegram_chats_task_id', 'telegram_chats', ['task_id'])
    op.create_index('idx_telegram_chats_chat_id', 'telegram_chats', ['chat_id'])
    
    op.create_index('idx_points_log_user_id', 'points_log', ['user_id'])
    op.create_index('idx_points_log_task_id', 'points_log', ['task_id'])
    op.create_index('idx_points_log_awarded_at', 'points_log', ['awarded_at'], postgresql_ops={'awarded_at': 'DESC'})
    
    op.create_index('idx_achievements_user_id', 'achievements', ['user_id'])
    op.create_index('idx_achievements_type', 'achievements', ['achievement_type'])
    
    op.create_index('idx_files_task_id', 'files', ['task_id'])
    op.create_index('idx_files_uploaded_by', 'files', ['uploaded_by'])
    op.create_index('idx_files_file_type', 'files', ['file_type'])
    
    op.create_index('idx_moderation_queue_status', 'moderation_queue', ['status'])
    op.create_index('idx_moderation_queue_user_id', 'moderation_queue', ['user_id'])
    op.create_index('idx_moderation_queue_task_id', 'moderation_queue', ['task_id'])
    op.create_index('idx_moderation_queue_created_at', 'moderation_queue', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    
    op.create_index('idx_activity_log_user_id', 'activity_log', ['user_id'])
    op.create_index('idx_activity_log_timestamp', 'activity_log', ['timestamp'], postgresql_ops={'timestamp': 'DESC'})
    op.create_index('idx_activity_log_action', 'activity_log', ['action'])
    
    op.create_index('idx_notifications_user_id', 'notifications', ['user_id'])
    op.create_index('idx_notifications_type', 'notifications', ['type'])
    op.create_index('idx_notifications_is_read', 'notifications', ['is_read'])
    op.create_index('idx_notifications_created_at', 'notifications', ['created_at'], postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    # Удаление индексов
    op.drop_index('idx_notifications_created_at', table_name='notifications')
    op.drop_index('idx_notifications_is_read', table_name='notifications')
    op.drop_index('idx_notifications_type', table_name='notifications')
    op.drop_index('idx_notifications_user_id', table_name='notifications')
    op.drop_index('idx_activity_log_action', table_name='activity_log')
    op.drop_index('idx_activity_log_timestamp', table_name='activity_log')
    op.drop_index('idx_activity_log_user_id', table_name='activity_log')
    op.drop_index('idx_moderation_queue_created_at', table_name='moderation_queue')
    op.drop_index('idx_moderation_queue_task_id', table_name='moderation_queue')
    op.drop_index('idx_moderation_queue_user_id', table_name='moderation_queue')
    op.drop_index('idx_moderation_queue_status', table_name='moderation_queue')
    op.drop_index('idx_files_file_type', table_name='files')
    op.drop_index('idx_files_uploaded_by', table_name='files')
    op.drop_index('idx_files_task_id', table_name='files')
    op.drop_index('idx_achievements_type', table_name='achievements')
    op.drop_index('idx_achievements_user_id', table_name='achievements')
    op.drop_index('idx_points_log_awarded_at', table_name='points_log')
    op.drop_index('idx_points_log_task_id', table_name='points_log')
    op.drop_index('idx_points_log_user_id', table_name='points_log')
    op.drop_index('idx_telegram_chats_chat_id', table_name='telegram_chats')
    op.drop_index('idx_telegram_chats_task_id', table_name='telegram_chats')
    op.drop_index('idx_equipment_requests_status', table_name='equipment_requests')
    op.drop_index('idx_equipment_requests_dates', table_name='equipment_requests')
    op.drop_index('idx_equipment_requests_user_id', table_name='equipment_requests')
    op.drop_index('idx_equipment_requests_equipment_id', table_name='equipment_requests')
    op.drop_index('idx_equipment_requests_task_id', table_name='equipment_requests')
    op.drop_index('idx_equipment_current_holder', table_name='equipment')
    op.drop_index('idx_equipment_status', table_name='equipment')
    op.drop_index('idx_equipment_category', table_name='equipment')
    op.drop_index('idx_task_assignments_status', table_name='task_assignments')
    op.drop_index('idx_task_assignments_user_id', table_name='task_assignments')
    op.drop_index('idx_task_assignments_task_id', table_name='task_assignments')
    op.drop_index('idx_task_stages_due_date', table_name='task_stages')
    op.drop_index('idx_task_stages_status', table_name='task_stages')
    op.drop_index('idx_task_stages_task_id', table_name='task_stages')
    op.drop_index('idx_tasks_created_at', table_name='tasks')
    op.drop_index('idx_tasks_created_by', table_name='tasks')
    op.drop_index('idx_tasks_event_id', table_name='tasks')
    op.drop_index('idx_tasks_due_date', table_name='tasks')
    op.drop_index('idx_tasks_priority', table_name='tasks')
    op.drop_index('idx_tasks_status', table_name='tasks')
    op.drop_index('idx_tasks_type', table_name='tasks')
    op.drop_index('idx_events_priority', table_name='events')
    op.drop_index('idx_events_dates', table_name='events')
    op.drop_index('idx_users_is_active', table_name='users')
    op.drop_index('idx_users_points', table_name='users')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_telegram_id', table_name='users')
    
    # Удаление таблиц
    op.drop_table('notifications')
    op.drop_table('activity_log')
    op.drop_table('moderation_queue')
    op.drop_table('files')
    op.drop_table('achievements')
    op.drop_table('points_log')
    op.drop_table('telegram_chats')
    op.drop_table('equipment_requests')
    op.drop_table('equipment')
    op.drop_table('task_assignments')
    op.drop_table('task_stages')
    op.drop_table('tasks')
    op.drop_table('events')
    op.drop_table('users')
    
    # Удаление ENUM типов
    op.execute('DROP TYPE IF EXISTS notification_type')
    op.execute('DROP TYPE IF EXISTS moderation_status')
    op.execute('DROP TYPE IF EXISTS equipment_request_status')
    op.execute('DROP TYPE IF EXISTS equipment_status')
    op.execute('DROP TYPE IF EXISTS assignment_status')
    op.execute('DROP TYPE IF EXISTS stage_status')
    op.execute('DROP TYPE IF EXISTS task_status')
    op.execute('DROP TYPE IF EXISTS task_priority')
    op.execute('DROP TYPE IF EXISTS task_type')
    op.execute('DROP TYPE IF EXISTS user_role')
