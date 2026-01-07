# ✅ Настройка фронтенда завершена

## Текущая конфигурация

### Frontend:
- **Service**: `best-pr-crm`
- **Public URL**: `https://best-pr-system.up.railway.app` ✅
- **Port**: `8080` ✅
- **Private URL**: `best-pr-crm.railway.internal` (для внутреннего использования)

### Backend:
- **Service**: `best-pr-api`
- **Public URL**: `https://best-pr-api.up.railway.app` ✅

---

## Что сделано

✅ **Public Networking** включен  
✅ **Домен**: `best-pr-system.up.railway.app`  
✅ **Порт**: `8080` (Railway автоматически устанавливает `PORT=8080`)  
✅ **Скрипт**: `npx serve -s dist -l $PORT` (из `package.json`)

---

## Что нужно сделать дальше

### 1. Добавить переменную `VITE_API_URL` во фронтенд

**Railway** → `best-pr-crm` → **Variables** → **New Variable**:
```
VITE_API_URL = https://best-pr-api.up.railway.app/api/v1
```

### 2. Обновить переменную `FRONTEND_URL` в бэкенде

**Railway** → `best-pr-api` → **Variables** → обнови:
```
FRONTEND_URL = https://best-pr-system.up.railway.app
```

(Если её ещё нет, добавь)

---

## Проверка

После добавления переменных:

1. **Открой фронтенд** в браузере:
   ```
   https://best-pr-system.up.railway.app
   ```
   → должен быть **React сайт** (не JSON, не ошибка)

2. **Открой Telegram бота** → `/start` → кнопка "Зарегистрироваться"
   → должна открываться **сайт**, а не JSON

3. **API документация**:
   ```
   https://best-pr-api.up.railway.app/docs
   ```
   → должен быть Swagger UI

---

## Важно

- **Port 8080** — это правильно! Railway устанавливает `PORT=8080`, и `serve` слушает на этом порту через переменную `$PORT`.
- **Public Networking** — обязательно для фронтенда (чтобы пользователи могли открыть сайт в браузере).
- **Private Networking** (`railway.internal`) — можно оставить для внутреннего использования, не мешает.

---

## Итоговая конфигурация

### Frontend (`best-pr-crm`):
```bash
Variables:
  VITE_API_URL = https://best-pr-api.up.railway.app/api/v1

Networking:
  Public: https://best-pr-system.up.railway.app (port 8080) ✅
  Private: best-pr-crm.railway.internal
```

### Backend (`best-pr-api`):
```bash
Variables:
  FRONTEND_URL = https://best-pr-system.up.railway.app
  TELEGRAM_ADMIN_IDS = ...
  GOOGLE_* = ...
  # и т.д.

Networking:
  Public: https://best-pr-api.up.railway.app ✅
```

---

Всё готово! 🎉
