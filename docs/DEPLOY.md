# Инструкция по развёртыванию

## VPS (Ubuntu) — основной деплой

### Быстрый старт

```bash
# 1. SSH на сервер
ssh misha_b@192.144.12.196

# 2. Настройка сервера (Docker, nginx, certbot) — один раз
cd /tmp
git clone https://github.com/baltanmihail/BEST-PR-System.git setup-tmp
bash setup-tmp/deploy/setup-server.sh
rm -rf setup-tmp
exit  # перелогиниться для docker group

# 3. Первый деплой
ssh misha_b@192.144.12.196
bash /home/misha_b/best-pr-system/deploy/first-deploy.sh

# 4. SSL сертификат (после настройки DNS)
sudo certbot --nginx -d pr.bmstu-best.ru

# 5. Последующие деплои — просто:
cd /home/misha_b/best-pr-system && bash deploy/deploy.sh
```

### Переменные окружения

Скопировать `.env.example` в `.env` и заполнить. Обязательные:
- `POSTGRES_PASSWORD` — пароль базы данных
- `SECRET_KEY` — секрет для JWT (`openssl rand -hex 32`)
- `TELEGRAM_BOT_TOKEN` — токен бота
- `FRONTEND_URL=https://pr.bmstu-best.ru`

Остальные — см. `.env.example`.

### Миграция БД из Railway

```bash
# На локальной машине (или Railway CLI):
pg_dump 'postgresql://USER:PASS@HOST:PORT/DB' -Fc > railway_dump.sql
scp railway_dump.sql misha_b@192.144.12.196:~/best-pr-system/

# На сервере:
cd ~/best-pr-system
bash deploy/migrate-db.sh railway_dump.sql
```

---

# Railway (legacy)

> Railway используется как fallback. Основной деплой — VPS выше.

# 🚀 Инструкция по развёртыванию на Railway

## 📋 Быстрый старт

### 1. Подготовка Telegram чата

1. **Создай супергруппу** в Telegram с включёнными Topics (темами)
2. **Добавь бота как администратора** с правами:
   - ✅ Управлять темами (`can_manage_topics`)
   - ✅ Добавлять участников
   - ✅ Приглашать пользователей по ссылке
3. **Получи ID чата** через @userinfobot (формат: `3545542173`)

### 2. Настройка Railway

#### Backend сервис (`best-pr-api`)

**Builder:** `DOCKERFILE` (используется `backend/Dockerfile`)  
**Start Command:** Оставить ПУСТЫМ (команда в Dockerfile)  
**Port:** `8080` (или другой, который Railway назначает)

**Обязательные переменные окружения:**
```env
DATABASE_URL=postgresql://...
ENVIRONMENT=production
TELEGRAM_BOT_TOKEN=ваш_токен_бота
TELEGRAM_ADMIN_IDS=5079636941
TELEGRAM_GENERAL_CHAT_ID=3545542173
FRONTEND_URL=https://best-pr-system.up.railway.app
```

**Google Drive и Sheets (для синхронизации):**
```env
# Минимум 1 credentials обязателен для работы с Google Drive
GOOGLE_CREDENTIALS_1_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"...","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}

# Опционально: дополнительные credentials для ротации (до 5 штук)
GOOGLE_CREDENTIALS_2_JSON={...}
GOOGLE_CREDENTIALS_3_JSON={...}
GOOGLE_CREDENTIALS_4_JSON={...}
GOOGLE_CREDENTIALS_5_JSON={...}

# ID папки в Google Drive (опционально)
# Если указано - система использует эту папку
# Если НЕ указано или папка недоступна - система создаст папку "BEST PR System" в корне Google Drive сервисного аккаунта
# Пример для Shared Drive: GOOGLE_DRIVE_FOLDER_ID=1Zxtqs4otBMhltOFCJG0-y8gBHWXvQGzI
# Для работы без Shared Drive: оставьте пустым GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_DRIVE_FOLDER_ID=

# ID таблицы таймлайна (создаётся автоматически, но можно указать вручную)
GOOGLE_TIMELINE_SHEETS_ID=опционально

# Email пользователя для автоматического sharing файлов
# 
# Для Shared Drive (Team Drive) - РЕКОМЕНДУЕТСЯ:
# - Укажите аккаунт в том же домене организации (например, mikhail.baltyan@bmstu-best.ru)
# - Ownership можно передать между аккаунтами одного домена
# - Файлы используют квоту организации (Shared Drive), а не сервисного аккаунта
# - Убедитесь, что сервисный аккаунт имеет права "Content Manager" или "Manager" на Shared Drive
#
# Для обычного Google Drive (без Shared Drive):
# - Ownership передать между разными доменами НЕВОЗМОЖНО (ограничение Google Drive API)
# - Пользователь получит только права "Редактор" (Editor), файлы останутся собственностью сервисного аккаунта
# - Файлы используют квоту сервисного аккаунта (обычно 15 ГБ на аккаунт)
# - Можно указать email для автоматического sharing (например, baltanmihail@gmail.com)
# - Или оставить пустым, если sharing не нужен
#
# Подробнее: см. docs/NO_SHARED_DRIVE_SETUP.md для настройки без Shared Drive
# Подробнее: см. docs/SHARED_DRIVE_SETUP.md для настройки с Shared Drive
GOOGLE_DRIVE_OWNER_EMAIL=
```

**Опциональные:**
```env
CORS_ORIGINS=https://best-pr-system.up.railway.app
LOG_LEVEL=INFO
API_V1_PREFIX=/api/v1
```

#### Frontend сервис (`best-pr-system`)

**Root Directory:** `frontend/`  
**Build Command:** `npm ci && npm run build`  
**Start Command:** `npm run preview`  
**Port:** `8080`

**Переменные окружения:**
```env
VITE_API_URL=https://best-pr-api.up.railway.app/api/v1
```

### 3. Деплой

```bash
cd "BEST PR System"
git add .
git commit -m "Что я делаю не так в своей жизни?"
git push origin main
```

Миграции БД применяются автоматически при старте.

## ✅ Проверка после деплоя

1. **Проверь логи в Railway Dashboard:**
   - ✅ Миграции применились: `INFO: Running migration`
   - ✅ Бот запустился: `INFO: Telegram bot started`
   - ✅ Google Drive структура создана: `✅ Google Drive структура инициализирована`
   - ✅ Таблица таймлайна создана: `✅ Google таблица таймлайна задач готова`
   - ✅ Системные шаблоны созданы: `✅ Системные шаблоны созданы`

2. **Проверь Google Drive:**
   - **Если используется Shared Drive:**
     - Открой Shared Drive и найди папку "BEST PR System" (или папку, указанную в GOOGLE_DRIVE_FOLDER_ID)
     - Внутри должны быть папки: Tasks, Gallery, Equipment, Support, Users, **Admin**
   - **Если используется обычный Google Drive (без Shared Drive):**
     - Файлы находятся в Google Drive сервисного аккаунта
     - Для доступа к файлам см. инструкцию: [docs/NO_SHARED_DRIVE_SETUP.md](./NO_SHARED_DRIVE_SETUP.md)
     - В логах должна быть строка: `✅ Папка создана в корне Google Drive: [folder_id]`
   - В папке **Admin** должны быть:
     - **Coordinators/** с подпапками: SMM, Design, Channel, PR-FR
     - **VP4PR/** (отдельная папка для VP4PR)
   - В папках координаторов и VP4PR можно добавлять шаблоны задач и другую информацию
   - Должна быть таблица "BEST PR System - Таймлайны"

3. **Проверь API endpoints:**
   - `GET /health` - должен вернуть 200
   - `GET /api/v1/registration/agreement` - должен вернуть соглашение
   - `POST /api/v1/calendar/sync/sheets` - синхронизация таймлайна (требует авторизации координатора)

4. **Если что-то не создалось:**
   - Проверь, что GOOGLE_CREDENTIALS_1_JSON установлен корректно (валидный JSON)
   - Проверь, что сервисный аккаунт имеет доступ к Google Drive API
   - **Если нет доступа к Shared Drive:** См. [docs/NO_SHARED_DRIVE_SETUP.md](./NO_SHARED_DRIVE_SETUP.md)
   - **Если используешь Shared Drive:** См. [docs/SHARED_DRIVE_SETUP.md](./SHARED_DRIVE_SETUP.md)
   - Проверь логи на ошибки инициализации

## 🏗️ Архитектура

- **Один супергруппа** с Topics для всех пользователей
- **Открытые темы** (видны всем): Общий чат, Информация
- **Закрытые темы** (только для координаторов и исполнителей): создаются автоматически для каждой задачи

## ⚠️ Важно

- Общий чат должен быть **супергруппой** с включёнными **Topics**
- Бот должен иметь право **`can_manage_topics`** для создания тем
- Миграции выполняются автоматически, не нужно запускать вручную

### Google Drive и Sheets

- **При первом запуске** автоматически создаются:
  - Папка "BEST PR System" в Google Drive (в указанной папке или в корне Google Drive сервисного аккаунта)
  - Подпапки: Tasks, Gallery, Equipment, Support, Users, **Admin**
  - В папке **Admin**:
    - **Coordinators/** (для координаторов)
      - SMM/ (шаблоны и информация для координатора SMM)
      - Design/ (шаблоны и информация для координатора Design)
      - Channel/ (шаблоны и информация для координатора Channel)
      - PR-FR/ (шаблоны и информация для координатора PR-FR)
    - **VP4PR/** (шаблоны и информация для VP4PR)
  - Таблица "BEST PR System - Таймлайны" с листами: Общий, SMM, Design, Channel, PR-FR
  
- **Сервисный аккаунт Google** должен иметь доступ к:
  - Google Drive API (создание папок и файлов)
  - Google Sheets API (чтение/запись таблиц)
  - Google Docs API (для работы с описаниями задач)
  
- **Два варианта настройки:**
  
  **Вариант 1: С Shared Drive (Team Drive)** - рекомендуется для организаций
  - 📖 Подробная инструкция: [docs/SHARED_DRIVE_SETUP.md](./SHARED_DRIVE_SETUP.md)
  - Требуется: Права "Content Manager" или "Manager" на Shared Drive для сервисного аккаунта
  - Преимущества: Квота организации, можно передавать ownership между аккаунтами одного домена
  - Установите `GOOGLE_DRIVE_FOLDER_ID` (ID папки в Shared Drive) или оставьте пустым (система попробует использовать ROOT_FOLDER_ID)
  
  **Вариант 2: Без Shared Drive (обычный Google Drive)** - для личных проектов или если нет доступа к Shared Drive
  - 📖 Подробная инструкция: [docs/NO_SHARED_DRIVE_SETUP.md](./NO_SHARED_DRIVE_SETUP.md)
  - Требуется: Только Google credentials (GOOGLE_CREDENTIALS_1_JSON)
  - Особенности: Файлы в Google Drive сервисного аккаунта (квота 15 ГБ на аккаунт), ownership передать нельзя
  - Оставьте `GOOGLE_DRIVE_FOLDER_ID` пустым - система автоматически создаст папку в корне Google Drive сервисного аккаунта
  
- **Автоматический fallback:**
  - Если `GOOGLE_DRIVE_FOLDER_ID` указан, но папка недоступна → система создаст папку в корне Google Drive
  - Если ROOT_FOLDER_ID (захардкоженный в коде) недоступен → система создаст папку в корне Google Drive
  - В логах будет предупреждение: `⚠️ ROOT_FOLDER_ID недоступен (возможно, нет доступа к Shared Drive)`
  
- **После создания** сохрани ID папки и таблицы в переменные окружения (опционально):
  - `GOOGLE_DRIVE_FOLDER_ID` - ID папки "BEST PR System" (ускорит последующие запуски)
  - `GOOGLE_TIMELINE_SHEETS_ID` - ID таблицы таймлайна (ускорит последующие запуски)
  
- **Формат GOOGLE_CREDENTIALS_*_JSON:**
  - Это полный JSON файл credentials сервисного аккаунта
  - В Railway нужно вставить как одну строку (без переносов)
  - Можно использовать до 5 credentials для ротации и увеличения лимитов API
  - Для увеличения квоты без Shared Drive: создайте несколько сервисных аккаунтов (каждый даёт 15 ГБ)
  
- **Очистка старой папки:**
  - Если была создана папка "BEST PR System" в Shared Drive, к которому нет доступа:
    - Система автоматически создаст новую папку в корне Google Drive сервисного аккаунта
    - Старая папка останется в Shared Drive (для удаления обратитесь к администратору Shared Drive)

## 📱 Настройка Mini App (WebApp)

После деплоя нужно включить Mini App в BotFather:

1. Откройте [@BotFather](https://t.me/BotFather)
2. Отправьте `/mybots` и выберите вашего бота
3. Выберите **"Bot Settings"** → **"Mini App"**
4. Укажите URL фронтенда: `https://best-pr-system.up.railway.app`
5. Готово! Кнопка "Open App" появится в интерфейсе бота

📖 Подробная инструкция: [НАСТРОЙКА_MINI_APP.md](./НАСТРОЙКА_MINI_APP.md)
