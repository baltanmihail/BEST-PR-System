# 🔧 Создание миграций Alembic

## Проблема: Таблицы не созданы в базе данных

Ошибка: `relation "tasks" does not exist`

Это означает, что миграции Alembic не были созданы или выполнены.

---

## ✅ Решение: Создать и выполнить миграции

### Вариант 1: Через Railway CLI (рекомендуется)

1. Установите Railway CLI (если не установлен):
   ```bash
   npm i -g @railway/cli
   ```

2. Войдите в Railway:
   ```bash
   railway login
   ```

3. Подключитесь к проекту:
   ```bash
   railway link
   ```

4. Выполните миграции:
   ```bash
   cd "BEST PR System/backend"
   railway run alembic revision --autogenerate -m "Initial migration: create all tables"
   railway run alembic upgrade head
   ```

---

### Вариант 2: Локально (если подключены к Railway БД)

1. Убедитесь, что `.env` содержит `DATABASE_URL` от Railway
2. Перейдите в папку `backend`:
   ```powershell
   cd "BEST PR System\backend"
   ```

3. Создайте миграцию:
   ```powershell
   python -m alembic revision --autogenerate -m "Initial migration: create all tables"
   ```

4. Выполните миграцию:
   ```powershell
   python -m alembic upgrade head
   ```

5. Закоммитьте файл миграции:
   ```powershell
   cd ..
   git add backend/alembic/versions/*.py
   git commit -m "Add initial Alembic migration"
   git push origin main
   ```

---

### Вариант 3: Автоматически при деплое

Миграции должны выполняться автоматически при каждом деплое через `Procfile`:
```
web: cd backend && python -m alembic upgrade head && python run.py
```

Но сначала нужно создать файл миграции и закоммитить его в Git.

---

## 🔍 Проверка после создания миграции

1. Проверьте, что файл миграции создан:
   ```
   backend/alembic/versions/xxxxx_initial_migration_create_all_tables.py
   ```

2. Проверьте, что миграция выполнилась:
   - Откройте Railway Dashboard
   - Посмотрите логи деплоя
   - Должны быть сообщения от Alembic:
     ```
     INFO  [alembic.runtime.migration] Running upgrade -> xxxxx, Initial migration
     ```

3. Проверьте API:
   - Откройте: https://best-pr-system.up.railway.app/test
   - Должен вернуться успешный ответ

---

## 🐛 Если миграция не создаётся

### Проблема: "Target database is not up to date"

**Решение:**
```bash
railway run alembic stamp head
railway run alembic revision --autogenerate -m "Initial migration"
railway run alembic upgrade head
```

### Проблема: "No changes detected"

**Решение:**
1. Проверьте, что все модели импортированы в `alembic/env.py`:
   ```python
   from app.models import *  # Import all models
   ```

2. Убедитесь, что модели используют `Base`:
   ```python
   from app.database import Base
   ```

---

## 📝 Чеклист

- [ ] Миграция создана (`backend/alembic/versions/*.py`)
- [ ] Миграция закоммичена в Git
- [ ] Миграция выполнена (в логах Railway)
- [ ] API работает (`/test` возвращает успешный ответ)
- [ ] Календарь работает (`/api/v1/calendar` возвращает данные)

---

**После создания миграции всё должно заработать! 🚀**
