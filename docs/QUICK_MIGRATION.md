# 🚀 Быстрое создание миграции

## Проблема
Ошибка: `relation "tasks" does not exist` - таблицы не созданы в базе данных.

---

## ✅ Быстрое решение

### Шаг 1: Создать миграцию через Python скрипт

```powershell
cd "BEST PR System\backend"
python create_migration.py
```

Это создаст файл миграции в `alembic/versions/`

### Шаг 2: Закоммитить миграцию

```powershell
cd ..
git add backend/alembic/versions/*.py
git commit -m "Add initial Alembic migration"
git push origin main
```

### Шаг 3: Railway автоматически выполнит миграцию

Railway автоматически выполнит миграцию при деплое через `Procfile`:
```
web: cd backend && python -m alembic upgrade head && python run.py
```

---

## ✅ Проверка

После деплоя проверьте:
1. Логи в Railway Dashboard - должны быть сообщения от Alembic
2. API: https://best-pr-system.up.railway.app/test
3. Календарь: https://best-pr-system.up.railway.app/api/v1/calendar?view=month&start_date=2026-01-01

---

**Готово! 🚀**
