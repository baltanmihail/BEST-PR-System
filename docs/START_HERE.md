# 🎯 НАЧНИТЕ ОТСЮДА!

## 🚀 Самый быстрый способ запустить проект

### Шаг 1: Установка (автоматическая)

Откройте PowerShell в папке `backend/` и выполните:

```powershell
.\setup.ps1
```

Скрипт автоматически:
- ✅ Проверит Python
- ✅ Создаст виртуальное окружение
- ✅ Установит все зависимости
- ✅ Проверит наличие .env файла

### Шаг 2: Создание .env файла

Если скрипт сообщил, что `.env` не найден, создайте файл `backend/.env`:

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
# Убедитесь, что venv активирован
.\venv\Scripts\Activate.ps1

# Создать миграции
alembic revision --autogenerate -m "Initial migration"

# Применить миграции
alembic upgrade head

# Запустить сервер
uvicorn app.main:app --reload
```

### Шаг 4: Проверка

Откройте в браузере: http://localhost:8000/docs

---

## 📚 Дополнительная документация

- **Проблемы с установкой?** → [SETUP_INSTRUCTIONS.md](./SETUP_INSTRUCTIONS.md)
- **Нужны команды PowerShell?** → [POWERSHELL_COMMANDS.md](./POWERSHELL_COMMANDS.md)
- **Хотите закоммитить в Git?** → [GIT_COMMIT_INFO.md](./GIT_COMMIT_INFO.md)
- **Нужно задеплоить на Railway?** → [RAILWAY_DEPLOY.md](./RAILWAY_DEPLOY.md)

---

## ⚠️ Частые проблемы

### "alembic не распознан"
**Решение**: Активируйте venv:
```powershell
.\venv\Scripts\Activate.ps1
```

### "Ошибка выполнения скриптов"
**Решение**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Ошибка с psycopg2-binary"
**Решение**: Это нормально! Установите остальные пакеты:
```powershell
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings
```

### "Не могу найти путь"
**Решение**: Используйте полный путь с кавычками:
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System\backend"
```

---

## ✅ Готово!

После успешного запуска вы увидите:
- Сервер работает на http://localhost:8000
- Документация API на http://localhost:8000/docs
- Health check на http://localhost:8000/health

**Удачи в разработке! 🚀**
