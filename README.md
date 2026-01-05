# 🚀 BEST PR System

Комплексная система управления PR-отделом BEST Москва с прогрессивным раскрытием функционала, геймификацией и автоматизацией процессов.

## 📋 Описание

Система для управления задачами PR-отдела, включающая:
- 📝 Управление задачами (SMM, Design, Channel, PR-FR)
- 🎬 Видеопроизводство с этапами
- 📦 Интеграция аренды оборудования
- 🏆 Геймификация и рейтинг
- 📅 Календарь и таймлайн
- 🤖 Telegram-бот интеграция
- 📁 Google Drive интеграция

## 🏗️ Архитектура

- **Backend**: FastAPI + PostgreSQL + SQLAlchemy
- **Frontend**: React + TypeScript + Tailwind CSS + Shadcn/UI
- **Bot**: Aiogram 3.x
- **Infrastructure**: Railway + Docker

Подробнее: [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)

## 📚 Документация

Вся документация находится в папке [docs/](./docs/):

### 🚀 Быстрый старт
- **[START_HERE.md](./docs/START_HERE.md)** - Начните отсюда! 🎯
- **[QUICK_START.md](./docs/QUICK_START.md)** - Быстрый старт
- **[SETUP_INSTRUCTIONS.md](./docs/SETUP_INSTRUCTIONS.md)** - Подробная установка
- **[POWERSHELL_COMMANDS.md](./docs/POWERSHELL_COMMANDS.md)** - Все команды PowerShell

### 📝 Git и деплой
- **[RAILWAY_COMPLETE_GUIDE.md](./docs/RAILWAY_COMPLETE_GUIDE.md)** - ⭐ **Полное руководство по Railway** (всё в одном месте)
- **[GIT_SETUP.md](./docs/GIT_SETUP.md)** - Настройка Git и GitHub
- **[GIT_COMMIT_INFO.md](./docs/GIT_COMMIT_INFO.md)** - Информация для коммитов

### 🏗️ Техническая документация
- **[ARCHITECTURE.md](./docs/ARCHITECTURE.md)** - Детальное описание архитектуры
- **[DEVELOPMENT_PLAN.md](./docs/DEVELOPMENT_PLAN.md)** - Поэтапный план
- **[UI_UX_CONCEPT.md](./docs/UI_UX_CONCEPT.md)** - Дизайн и пользовательский опыт
- **[DATABASE_SCHEMA.sql](./docs/DATABASE_SCHEMA.sql)** - Схема БД
- **[ANSWERS_AND_RECOMMENDATIONS.md](./docs/ANSWERS_AND_RECOMMENDATIONS.md)** - FAQ и советы

## 🚀 Быстрый старт

### ⚡ Самый быстрый способ

1. **Откройте PowerShell в папке `backend/`**
2. **Запустите скрипт установки:**
   ```powershell
   .\setup.ps1
   ```
3. **Следуйте инструкциям на экране**

### 📖 Подробные инструкции

- **Быстрый старт**: [docs/QUICK_START.md](./docs/QUICK_START.md)
- **Установка и настройка**: [docs/SETUP_INSTRUCTIONS.md](./docs/SETUP_INSTRUCTIONS.md)
- **Команды PowerShell**: [docs/POWERSHELL_COMMANDS.md](./docs/POWERSHELL_COMMANDS.md)
- **Git коммиты**: [docs/GIT_COMMIT_INFO.md](./docs/GIT_COMMIT_INFO.md)
- **Деплой на Railway**: [docs/RAILWAY_DEPLOY.md](./docs/RAILWAY_DEPLOY.md)
- **Проблема с psycopg2-binary?**: [FIX_PSYCOPG2.md](./FIX_PSYCOPG2.md)

### Требования
- Python 3.11+
- Node.js 18+ (для frontend)
- PostgreSQL 15+ (или SQLite для разработки)
- Docker (опционально)

### Установка

#### Backend (автоматическая)
```powershell
cd "BEST PR System\backend"
.\setup.ps1
```

#### Backend (ручная)
```powershell
cd "BEST PR System\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings python-multipart
```

**Примечание**: Если возникает ошибка с `psycopg2-binary` - это нормально для Windows. Он не нужен для разработки с SQLite. См. [FIX_PSYCOPG2.md](./FIX_PSYCOPG2.md)

#### Frontend
```bash
cd frontend
npm install
```

### Настройка

1. Создайте файл `.env` в папке `backend/` (см. [SETUP_INSTRUCTIONS.md](./docs/SETUP_INSTRUCTIONS.md))
2. Заполните переменные окружения (минимум: DATABASE_URL, SECRET_KEY)
3. Настройте Google API credentials (можно позже)
4. Примените миграции: `alembic upgrade head`

### Запуск

#### Development
```powershell
# Backend
cd "BEST PR System\backend"
.\venv\Scripts\Activate.ps1

# Применить миграции (первый раз)
alembic upgrade head

# Запустить сервер
uvicorn app.main:app --reload
```

#### Frontend (в другом терминале)
```bash
cd frontend
npm run dev
```

#### Bot (в другом терминале)
```powershell
cd "BEST PR System\backend\bot"
python main.py
```

#### Production (Docker)
```bash
docker-compose up -d
```

## 📁 Структура проекта

```
BEST_PR_System/
├── backend/          # FastAPI backend
│   ├── app/          # Приложение
│   ├── bot/          # Telegram бот
│   ├── alembic/      # Миграции БД
│   └── setup.ps1     # Скрипт установки
├── frontend/         # React frontend
├── docs/             # Документация
├── Procfile          # Для Railway
├── railway.json      # Конфигурация Railway
└── README.md
```

## 🎯 Статус разработки

- [x] Архитектура и планирование
- [x] Структура проекта (День 1)
- [x] Модели базы данных (День 1)
- [x] Alembic миграции (День 2)
- [x] Базовая аутентификация (День 2)
- [ ] Backend API (День 3-4)
- [ ] Frontend
- [ ] Telegram Bot
- [ ] Интеграции
- [ ] Деплой

## 👥 Команда

- **VP4PR**: Стратегическое управление
- **Координаторы**: Управление направлениями
- **Участники**: Выполнение задач

## 📝 Лицензия

Внутренний проект BEST Москва

## 🤝 Вклад

Проект разрабатывается для PR-отдела BEST Москва.
