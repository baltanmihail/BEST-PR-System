# ✅ Решение проблемы с psycopg2-binary

## 🔧 Быстрое решение

### Проблема
Ошибка при установке: `Error: pg_config executable not found`

### Решение

**Установите пакеты БЕЗ psycopg2-binary:**

```powershell
# Активируйте venv
cd "BEST PR System\backend"
.\venv\Scripts\Activate.ps1

# Установите основные пакеты
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings python-multipart aiohttp aiofiles python-dateutil pytz
```

**Почему это работает:**
- `psycopg2-binary` нужен только для **синхронных** миграций
- Мы используем **async** драйверы (`asyncpg`, `aiosqlite`)
- Для разработки используйте SQLite (уже настроено)

---

## 📝 После установки

1. Создайте `.env` файл в `backend/`:
```env
DATABASE_URL=sqlite:///./best_pr_system.db
SECRET_KEY=your-secret-key
TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_ADMIN_IDS=5079636941
ENVIRONMENT=development
LOG_LEVEL=INFO
```

2. Примените миграции:
```powershell
alembic upgrade head
```

3. Запустите сервер:
```powershell
uvicorn app.main:app --reload
```

---

## ✅ Готово!

Откройте: http://localhost:8000/docs

**Подробнее**: [FIX_PSYCOPG2.md](./FIX_PSYCOPG2.md)
