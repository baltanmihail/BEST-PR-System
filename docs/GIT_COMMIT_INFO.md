# 1. Перейдите в папку проекта
cd "BEST PR System"

# 2. Проверьте, что изменения есть
git status

# 3. Добавьте все изменения
git add .

# 4. Создайте коммит
git commit -m "chore: Consolidate Railway docs into single guide, remove duplicates"

# 5. Отправьте в GitHub
git push origin main

# 📝 Информация для Git коммита

## 🎯 Первый коммит

### Название коммита:
```
feat: Initial project setup with backend structure and models
```

### Описание коммита:
```
Initial commit for BEST PR System project

- Created project structure (backend, frontend, docs)
- Implemented SQLAlchemy models (User, Task, Equipment, etc.)
- Set up FastAPI application with basic auth
- Configured Alembic for database migrations
- Added Pydantic schemas for API validation
- Created authentication utilities (JWT, Telegram auth)
- Added permission system with role-based access control

Features:
- User authentication via Telegram
- Task management models
- Equipment rental models
- Gamification models (points, achievements)
- Event management
- File management with Google Drive integration

Tech stack:
- FastAPI 0.104+
- SQLAlchemy 2.0+ (async)
- Alembic for migrations
- PostgreSQL/SQLite support
- JWT authentication
```

---

## 📦 Что включить в коммит

### ✅ Включить:
- Все файлы в `backend/app/`
- `backend/alembic/`
- `backend/requirements.txt`
- `backend/Makefile`
- `backend/alembic.ini`
- `backend/setup.ps1`
- `backend/run.py`
- `docs/` (вся документация)
- `README.md`
- `.gitignore`
- `docker-compose.yml`
- `Procfile`
- `railway.json`
- `nixpacks.toml`

### ❌ НЕ включать (уже в .gitignore):
- `venv/` или `env/`
- `__pycache__/`
- `*.pyc`
- `.env` файлы
- `*.db` (SQLite базы данных)
- `credentials*.json` (Google API credentials)

---

## 🔄 Команды для Git

### Инициализация репозитория (если ещё не сделано):
```powershell
cd "BEST PR System"
git init
```

### Добавление файлов:
```powershell
# Добавить все файлы (кроме игнорируемых)
git add .

# Или выборочно:
git add backend/
git add docs/
git add README.md
git add .gitignore
git add docker-compose.yml
git add Procfile
git add railway.json
```

### Проверка что будет закоммичено:
```powershell
git status
```

### Создание коммита:
```powershell
git commit -m "feat: Initial project setup with backend structure and models

Initial commit for BEST PR System project

- Created project structure (backend, frontend, docs)
- Implemented SQLAlchemy models (User, Task, Equipment, etc.)
- Set up FastAPI application with basic auth
- Configured Alembic for database migrations
- Added Pydantic schemas for API validation
- Created authentication utilities (JWT, Telegram auth)
- Added permission system with role-based access control"
```

### Настройка удалённого репозитория (если нужно):

**⚠️ ВАЖНО**: Сначала создайте репозиторий на GitHub, затем используйте его реальный URL!

```powershell
# 1. Удалить пример remote (если был добавлен)
git remote remove origin

# 2. Добавить remote с РЕАЛЬНЫМ URL (замените на ваш!)
git remote add origin https://github.com/ВАШ-USERNAME/best-pr-system.git

# 3. Отправить коммиты
git branch -M main
git push -u origin main
```

**📖 Подробная инструкция**: [GIT_SETUP.md](./GIT_SETUP.md) - как создать репозиторий и настроить remote

---

## 📋 Последующие коммиты

### Формат коммитов:
```
<type>: <subject>

<body>
```

### Типы коммитов:
- `feat:` - новая функциональность
- `fix:` - исправление бага
- `docs:` - изменения в документации
- `style:` - форматирование кода
- `refactor:` - рефакторинг
- `test:` - добавление тестов
- `chore:` - обновление зависимостей, конфигов

### Примеры:
```
feat: Add task CRUD endpoints

- Implemented GET /api/v1/tasks endpoint
- Added POST /api/v1/tasks for task creation
- Created task service with business logic
- Added task filtering and pagination
```

```
fix: Resolve authentication token expiration issue

- Fixed JWT token validation
- Updated token refresh logic
- Added proper error handling
```

---

## 🔐 Безопасность

**ВАЖНО**: Никогда не коммитьте:
- `.env` файлы с реальными токенами
- `credentials*.json` файлы
- Пароли и секретные ключи
- Личные данные пользователей

Проверьте `.gitignore` перед коммитом!
