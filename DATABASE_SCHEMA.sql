-- ============================================
-- BEST PR System - Database Schema
-- PostgreSQL 15+
-- ============================================

-- Расширения
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- для полнотекстового поиска

-- ============================================
-- ENUMS
-- ============================================

-- Роли пользователей
CREATE TYPE user_role AS ENUM (
    'novice',                    -- Новичок (0-100 баллов)
    'participant',               -- Участник (101-500)
    'active_participant',        -- Активный (501-1500)
    'coordinator_smm',           -- Координатор SMM
    'coordinator_design',        -- Координатор Design
    'coordinator_channel',        -- Координатор Channel
    'coordinator_prfr',          -- Координатор PR-FR
    'vp4pr'                      -- VP4PR (глава отдела)
);

-- Типы задач
CREATE TYPE task_type AS ENUM (
    'smm',
    'design',
    'channel',
    'prfr'
);

-- Приоритеты задач
CREATE TYPE task_priority AS ENUM (
    'low',
    'medium',
    'high',
    'critical'
);

-- Статусы задач
CREATE TYPE task_status AS ENUM (
    'draft',         -- Черновик (только для координаторов)
    'open',          -- Открыта для взятия
    'assigned',      -- Назначена
    'in_progress',   -- В работе
    'review',        -- На проверке
    'completed',     -- Выполнена
    'cancelled'      -- Отменена
);

-- Статусы этапов
CREATE TYPE stage_status AS ENUM (
    'pending',       -- Ожидание
    'in_progress',   -- В работе
    'completed'      -- Завершён
);

-- Статусы назначений
CREATE TYPE assignment_status AS ENUM (
    'assigned',      -- Назначено
    'in_progress',   -- В работе
    'completed',     -- Завершено
    'cancelled'      -- Отменено
);

-- Статусы оборудования
CREATE TYPE equipment_status AS ENUM (
    'available',     -- Доступно
    'rented',        -- В аренде
    'maintenance',   -- На обслуживании
    'broken'         -- Сломано
);

-- Статусы заявок на оборудование
CREATE TYPE equipment_request_status AS ENUM (
    'pending',       -- На рассмотрении
    'approved',      -- Одобрена
    'rejected',      -- Отклонена
    'active',        -- Активна (оборудование выдано)
    'completed',     -- Завершена (возвращено)
    'cancelled'      -- Отменена
);

-- Статусы модерации
CREATE TYPE moderation_status AS ENUM (
    'pending',       -- Ожидает
    'approved',      -- Одобрено
    'rejected'       -- Отклонено
);

-- ============================================
-- ТАБЛИЦЫ
-- ============================================

-- Пользователи
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    full_name TEXT NOT NULL,
    role user_role NOT NULL DEFAULT 'novice',
    level INTEGER NOT NULL DEFAULT 1,
    points INTEGER NOT NULL DEFAULT 0,
    streak_days INTEGER NOT NULL DEFAULT 0,
    last_activity TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Индексы
    CONSTRAINT users_telegram_id_unique UNIQUE (telegram_id)
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_users_points ON users(points DESC);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Мероприятия
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    date_start DATE NOT NULL,
    date_end DATE NOT NULL,
    priority INTEGER NOT NULL DEFAULT 5 CHECK (priority >= 1 AND priority <= 10),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT events_dates_check CHECK (date_end >= date_start)
);

CREATE INDEX idx_events_dates ON events(date_start, date_end);
CREATE INDEX idx_events_priority ON events(priority DESC);

-- Задачи
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    description TEXT,
    type task_type NOT NULL,
    event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    priority task_priority NOT NULL DEFAULT 'medium',
    status task_status NOT NULL DEFAULT 'draft',
    due_date TIMESTAMP WITH TIME ZONE,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT tasks_title_not_empty CHECK (LENGTH(TRIM(title)) > 0)
);

CREATE INDEX idx_tasks_type ON tasks(type);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);
CREATE INDEX idx_tasks_event_id ON tasks(event_id);
CREATE INDEX idx_tasks_created_by ON tasks(created_by);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- Этапы задач
CREATE TABLE task_stages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL, -- 'script', 'shooting', 'editing', 'review', 'publication'
    stage_order INTEGER NOT NULL,
    due_date TIMESTAMP WITH TIME ZONE,
    status stage_status NOT NULL DEFAULT 'pending',
    status_color TEXT NOT NULL DEFAULT 'green', -- 'green', 'yellow', 'red', 'purple', 'blue'
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT task_stages_order_check CHECK (stage_order > 0),
    CONSTRAINT task_stages_color_check CHECK (status_color IN ('green', 'yellow', 'red', 'purple', 'blue'))
);

CREATE INDEX idx_task_stages_task_id ON task_stages(task_id);
CREATE INDEX idx_task_stages_status ON task_stages(status);
CREATE INDEX idx_task_stages_due_date ON task_stages(due_date);

-- Назначения задач
CREATE TABLE task_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_in_task TEXT NOT NULL, -- 'executor', 'designer', 'videographer', 'reviewer'
    status assignment_status NOT NULL DEFAULT 'assigned',
    rating INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    feedback TEXT,
    assigned_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT task_assignments_unique UNIQUE (task_id, user_id, role_in_task)
);

CREATE INDEX idx_task_assignments_task_id ON task_assignments(task_id);
CREATE INDEX idx_task_assignments_user_id ON task_assignments(user_id);
CREATE INDEX idx_task_assignments_status ON task_assignments(status);

-- Оборудование
CREATE TABLE equipment (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- 'camera', 'audio', 'lighting', 'accessories'
    specs JSONB, -- Дополнительные характеристики
    status equipment_status NOT NULL DEFAULT 'available',
    current_holder_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT equipment_name_not_empty CHECK (LENGTH(TRIM(name)) > 0)
);

CREATE INDEX idx_equipment_category ON equipment(category);
CREATE INDEX idx_equipment_status ON equipment(status);
CREATE INDEX idx_equipment_current_holder ON equipment(current_holder_id);

-- Заявки на оборудование
CREATE TABLE equipment_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL, -- Связь с задачей
    equipment_id UUID NOT NULL REFERENCES equipment(id) ON DELETE RESTRICT,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status equipment_request_status NOT NULL DEFAULT 'pending',
    rejection_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT equipment_requests_dates_check CHECK (end_date >= start_date)
);

CREATE INDEX idx_equipment_requests_task_id ON equipment_requests(task_id);
CREATE INDEX idx_equipment_requests_equipment_id ON equipment_requests(equipment_id);
CREATE INDEX idx_equipment_requests_user_id ON equipment_requests(user_id);
CREATE INDEX idx_equipment_requests_dates ON equipment_requests(start_date, end_date);
CREATE INDEX idx_equipment_requests_status ON equipment_requests(status);

-- Telegram чаты
CREATE TABLE telegram_chats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL, -- Telegram chat ID
    chat_type TEXT NOT NULL DEFAULT 'group', -- 'group', 'supergroup'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT telegram_chats_task_unique UNIQUE (task_id)
);

CREATE INDEX idx_telegram_chats_task_id ON telegram_chats(task_id);
CREATE INDEX idx_telegram_chats_chat_id ON telegram_chats(chat_id);

-- Логи баллов
CREATE TABLE points_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE SET NULL,
    points INTEGER NOT NULL, -- может быть отрицательным
    reason TEXT NOT NULL, -- 'task_completed', 'early_completion', 'quality_bonus', etc.
    awarded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_points_log_user_id ON points_log(user_id);
CREATE INDEX idx_points_log_task_id ON points_log(task_id);
CREATE INDEX idx_points_log_awarded_at ON points_log(awarded_at DESC);

-- Ачивки
CREATE TABLE achievements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    achievement_type TEXT NOT NULL, -- 'first_task', 'speedster', 'reliable', etc.
    unlocked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT achievements_unique UNIQUE (user_id, achievement_type)
);

CREATE INDEX idx_achievements_user_id ON achievements(user_id);
CREATE INDEX idx_achievements_type ON achievements(achievement_type);

-- Файлы
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    drive_id TEXT NOT NULL, -- Google Drive file ID
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL, -- 'script', 'video', 'image', 'document'
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    CONSTRAINT files_file_name_not_empty CHECK (LENGTH(TRIM(file_name)) > 0)
);

CREATE INDEX idx_files_task_id ON files(task_id);
CREATE INDEX idx_files_uploaded_by ON files(uploaded_by);
CREATE INDEX idx_files_file_type ON files(file_type);

-- Очередь модерации
CREATE TABLE moderation_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    application_data JSONB NOT NULL, -- данные заявки
    status moderation_status NOT NULL DEFAULT 'pending',
    decision_by UUID REFERENCES users(id) ON DELETE SET NULL,
    decision_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_moderation_queue_status ON moderation_queue(status);
CREATE INDEX idx_moderation_queue_user_id ON moderation_queue(user_id);
CREATE INDEX idx_moderation_queue_task_id ON moderation_queue(task_id);
CREATE INDEX idx_moderation_queue_created_at ON moderation_queue(created_at DESC);

-- Логи активности
CREATE TABLE activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    details JSONB
);

CREATE INDEX idx_activity_log_user_id ON activity_log(user_id);
CREATE INDEX idx_activity_log_timestamp ON activity_log(timestamp DESC);
CREATE INDEX idx_activity_log_action ON activity_log(action);

-- ============================================
-- ТРИГГЕРЫ
-- ============================================

-- Автоматическое обновление updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_task_stages_updated_at BEFORE UPDATE ON task_stages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_equipment_updated_at BEFORE UPDATE ON equipment
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_equipment_requests_updated_at BEFORE UPDATE ON equipment_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_moderation_queue_updated_at BEFORE UPDATE ON moderation_queue
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Автоматическое обновление last_activity пользователя
CREATE OR REPLACE FUNCTION update_user_activity()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.user_id IS NOT NULL THEN
        UPDATE users SET last_activity = NOW() WHERE id = NEW.user_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_activity_on_task_assignment AFTER INSERT ON task_assignments
    FOR EACH ROW EXECUTE FUNCTION update_user_activity();

-- ============================================
-- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ УРОВНЯ ПОЛЬЗОВАТЕЛЯ
-- ============================================
-- ВАЖНО: Эта функция была исправлена для сохранения специальных ролей (координаторы и VP4PR).
-- Старая версия перезаписывала все роли на основе баллов, что приводило к потере прав координаторов.
-- 
-- ИСПРАВЛЕННАЯ ВЕРСИЯ (текущая):
-- - Сохраняет специальные роли: coordinator_smm, coordinator_design, coordinator_channel, coordinator_prfr, vp4pr
-- - Обновляет только level на основе баллов для всех пользователей
-- - Обновляет role ТОЛЬКО для обычных пользователей (не координаторов и не VP4PR)
--
-- Миграция: 022_fix_update_user_level_preserve_special_roles.py
-- Дата исправления: 2026-01-09
-- ============================================
CREATE OR REPLACE FUNCTION update_user_level()
RETURNS TRIGGER AS $$
DECLARE
    is_special_role_old BOOLEAN := FALSE;
    is_special_role_new BOOLEAN := FALSE;
BEGIN
    -- ШАГ 1: Проверяем, является ли старая роль специальной (координатор или VP4PR)
    -- Это важно для защиты от случайного понижения координатора при обновлении баллов
    is_special_role_old := OLD.role IN (
        'coordinator_smm',
        'coordinator_design',
        'coordinator_channel',
        'coordinator_prfr',
        'vp4pr'
    );
    
    -- ШАГ 2: Проверяем, является ли новая роль специальной
    -- Это необходимо на случай, если роль меняется явно вместе с баллами (явное назначение координатора)
    is_special_role_new := NEW.role IN (
        'coordinator_smm',
        'coordinator_design',
        'coordinator_channel',
        'coordinator_prfr',
        'vp4pr'
    );
    
    -- ШАГ 3: Обновляем level на основе баллов (ВСЕГДА для всех пользователей)
    -- Level обновляется независимо от роли, так как это просто числовой показатель
    IF NEW.points < 101 THEN
        NEW.level := 1;
    ELSIF NEW.points < 501 THEN
        NEW.level := 2;
    ELSIF NEW.points < 1501 THEN
        NEW.level := 3;
    ELSIF NEW.points < 3001 THEN
        NEW.level := 4;
    ELSE
        NEW.level := 5;
    END IF;
    
    -- ШАГ 4: Обновляем role ТОЛЬКО для обычных пользователей
    -- КРИТИЧЕСКИ ВАЖНО: Специальные роли (координаторы и VP4PR) НЕ должны перезаписываться!
    -- Это предотвращает потерю прав доступа при начислении баллов координаторам
    
    IF is_special_role_new THEN
        -- Случай 1: Новая роль явно установлена как специальная (явное назначение координатора)
        -- NEW.role уже правильная, сохраняем её без изменений
        -- Пример: UPDATE users SET role = 'coordinator_smm', points = 500 WHERE id = ...
        NULL; -- Ничего не делаем, роль уже правильная
    ELSIF is_special_role_old THEN
        -- Случай 2: Была специальная роль, но NEW.role не специальная
        -- Это защита от случайного понижения координатора при обновлении только баллов
        -- Восстанавливаем специальную роль из OLD.role
        -- Пример: UPDATE users SET points = 1000 WHERE id = ... (role не указан, но был coordinator_smm)
        NEW.role := OLD.role;
    ELSE
        -- Случай 3: Роль не специальная (ни в OLD, ни в NEW) - обычный пользователь
        -- В этом случае можем безопасно обновить роль на основе баллов
        -- Это стандартное поведение для участников системы
        IF NEW.points < 101 THEN
            NEW.role := 'novice';
        ELSIF NEW.points < 501 THEN
            NEW.role := 'participant';
        ELSIF NEW.points < 1501 THEN
            NEW.role := 'active_participant';
        ELSIF NEW.points < 3001 THEN
            NEW.role := 'active_participant';
        ELSE
            NEW.role := 'active_participant';
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_level_on_points_change BEFORE UPDATE OF points ON users
    FOR EACH ROW 
    WHEN (NEW.points IS DISTINCT FROM OLD.points)
    EXECUTE FUNCTION update_user_level();

-- ============================================
-- VIEWS (представления)
-- ============================================

-- Статистика пользователя
CREATE OR REPLACE VIEW user_stats AS
SELECT 
    u.id,
    u.telegram_id,
    u.full_name,
    u.role,
    u.level,
    u.points,
    u.streak_days,
    COUNT(DISTINCT ta.task_id) FILTER (WHERE ta.status = 'completed') as completed_tasks,
    COUNT(DISTINCT ta.task_id) FILTER (WHERE ta.status = 'in_progress') as active_tasks,
    COUNT(DISTINCT a.id) as achievements_count
FROM users u
LEFT JOIN task_assignments ta ON u.id = ta.user_id
LEFT JOIN achievements a ON u.id = a.user_id
GROUP BY u.id;

-- Статистика задач по типам
CREATE OR REPLACE VIEW task_stats_by_type AS
SELECT 
    type,
    status,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE due_date < NOW()) as overdue_count
FROM tasks
GROUP BY type, status;

-- Рейтинг пользователей (только исполнители, без координаторов и VP4PR)
CREATE OR REPLACE VIEW leaderboard AS
SELECT 
    u.id,
    u.telegram_id,
    u.full_name,
    u.points,
    u.level,
    COUNT(DISTINCT ta.task_id) FILTER (WHERE ta.status = 'completed') as completed_tasks,
    ROW_NUMBER() OVER (ORDER BY u.points DESC) as rank
FROM users u
LEFT JOIN task_assignments ta ON u.id = ta.user_id
WHERE u.role IN ('novice', 'participant', 'active_participant')
GROUP BY u.id
ORDER BY u.points DESC;

-- ============================================
-- ИНИЦИАЛЬНЫЕ ДАННЫЕ
-- ============================================

-- Мероприятия семестра
INSERT INTO events (name, date_start, date_end, priority, description) VALUES
('BIP', '2024-02-19', '2024-02-20', 10, 'Презентация BEST и набор в организацию'),
('TW', '2024-03-13', '2024-03-14', 8, 'Выезд в Ступинский Бауманский лагерь'),
('BESTALKS', '2024-03-27', '2024-03-28', 7, 'Мероприятие в формате TED'),
('ЯВ', '2024-04-16', '2024-04-16', 9, 'Ярмарка Вакансий'),
('IDEA', '2024-04-26', '2024-04-26', 6, 'Кейс-чемпионат'),
('MW', '2024-05-01', '2024-05-03', 5, 'Motivation Weekend'),
('Караоке батл', '2024-05-22', '2024-05-22', 4, 'Неформалка PR-отдела'),
('MS', '2024-05-17', '2024-05-17', 7, 'Milestone - переводное мероприятие');
