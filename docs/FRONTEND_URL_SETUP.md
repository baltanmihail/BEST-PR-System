# 🌐 Настройка URL фронтенда и красивого домена

## Проблема: "Вижу только JSON на сайте"

**Сейчас**: `https://best-pr-system.up.railway.app/` → JSON от бэкенда  
**Нужно**: `https://best-pr-system.up.railway.app/` → React фронтенд

---

## Решение 1: Настроить домены на Railway (рекомендуется)

### Вариант A: Два сервиса на разных поддоменах

1. **Backend**: `best-pr-api.up.railway.app` (API)
2. **Frontend**: `best-pr-system.up.railway.app` (сайт)

### Вариант B: Один красивый домен для фронтенда

1. **Frontend**: `best-pr-system.up.railway.app` (сайт)
2. **Backend**: оставить дефолтный Railway URL или `best-pr-api.up.railway.app`

---

## Как настроить на Railway

### Шаг 1: Создать frontend сервис

```bash
# В Railway UI:
1. New Service → Deploy from GitHub
2. Выбери репозиторий: BESTMoscowBot
3. Root Directory: BEST PR System/frontend
4. Name: best-pr-frontend
```

### Шаг 2: Настроить переменные для frontend

```bash
VITE_API_URL=https://best-pr-system.up.railway.app/api/v1
```

### Шаг 3: Настроить домен для frontend

```bash
# В Railway UI:
1. Frontend Service → Settings → Networking
2. Custom Domain → Generate Domain
3. Введи: best-pr-system
4. Railway даст: best-pr-system.up.railway.app
```

### Шаг 4: Переименовать backend домен (опционально)

```bash
# В Railway UI:
1. Backend Service → Settings → Networking
2. Custom Domain → Generate Domain
3. Введи: best-pr-api
4. Railway даст: best-pr-api.up.railway.app
```

### Шаг 5: Обновить переменные

```bash
# Backend сервис:
FRONTEND_URL=https://best-pr-system.up.railway.app
CORS_ORIGINS=https://best-pr-system.up.railway.app

# Frontend сервис (если сменил backend URL):
VITE_API_URL=https://best-pr-api.up.railway.app/api/v1
```

---

## Результат

- **Пользователи** открывают `https://best-pr-system.up.railway.app/` → видят **React фронтенд**
- **API** доступен на `https://best-pr-api.up.railway.app/` (или `/api/v1` через фронтенд)
- **Бот** отправляет ссылку на **фронтенд**, а не на JSON бэкенда

---

## Альтернатива: Использовать Vercel для фронтенда

Frontend → Vercel (бесплатно, быстрее):
```bash
1. Vercel → New Project → Import Git
2. Root Directory: BEST PR System/frontend
3. Build Command: npm run build
4. Output Directory: dist
5. Environment Variables:
   VITE_API_URL=https://best-pr-api.up.railway.app/api/v1
```

Тогда фронтенд будет на `best-pr-system.vercel.app`, а бэкенд на Railway.

---

## Проверка после настройки

1. Открой `https://best-pr-system.up.railway.app/` → должен быть **React** (не JSON)
2. В боте `/start` → кнопка "Зарегистрироваться" → открывается **сайт** (не JSON)
3. Инлайн-кнопки работают (после исправления `/public/*`)

---

## ✅ Что уже сделано в коде

- Добавлена переменная `FRONTEND_URL` в config.py
- Все ссылки в боте используют `settings.FRONTEND_URL` вместо хардкода
- После настройки домена нужно только задать переменную на Railway
