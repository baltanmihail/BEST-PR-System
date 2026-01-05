# ⚡ Быстрый старт

## 🎯 Для тех, кто хочет сразу запустить

### Шаг 1: Установка зависимостей

```powershell
# Перейти в папку backend
cd "BEST PR System\backend"

# Создать виртуальное окружение
python -m venv venv

# Активировать (если ошибка - см. SETUP_INSTRUCTIONS.md)
.\venv\Scripts\Activate.ps1

# Обновить pip
python -m pip install --upgrade pip

# Установить зависимости (без psycopg2-binary если ошибка)
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings python-multipart
```

### Шаг 2: Настройка .env

Создайте файл `backend/.env`:

```env
DATABASE_URL=sqlite:///./best_pr_system.db
SECRET_KEY=change-me-in-production-12345
TELEGRAM_BOT_TOKEN=your-token-here
TELEGRAM_ADMIN_IDS=5079636941
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Шаг 3: Миграции и запуск

```powershell
# Создать миграции
alembic revision --autogenerate -m "Initial migration"

# Применить миграции
alembic upgrade head

# Запустить сервер
uvicorn app.main:app --reload
```

### Шаг 4: Проверка

Откройте: http://localhost:8000/docs

---

## 📚 Подробные инструкции

- **Установка и настройка**: [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)
- **Git коммиты**: [GIT_COMMIT_INFO.md](./GIT_COMMIT_INFO.md)
- **Деплой на Railway**: [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)
- **Команды PowerShell**: [POWERSHELL_COMMANDS.md](./POWERSHELL_COMMANDS.md)
