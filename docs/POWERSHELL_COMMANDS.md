# 💻 Команды PowerShell для работы с проектом

## 📍 Правильные пути

**ВАЖНО**: Используйте кавычки для путей с пробелами и кириллицей!

### Переход в папку проекта:
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System"
```

### Переход в backend:
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System\backend"
```

---

## 🚀 Установка и запуск

### 1. Создание виртуального окружения:
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System\backend"
python -m venv venv
```

### 2. Активация виртуального окружения:
```powershell
.\venv\Scripts\Activate.ps1
```

**Если ошибка с политикой выполнения:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. Установка зависимостей:
```powershell
# Сначала обновить pip
python -m pip install --upgrade pip

# Установить зависимости (psycopg2-binary можно пропустить если ошибка)
pip install -r requirements.txt
```

**Если ошибка с psycopg2-binary:**
```powershell
# Установить без psycopg2-binary (он не критичен для разработки)
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings
```

### 4. Создание .env файла:
```powershell
# Создать файл .env в папке backend
New-Item -Path ".env" -ItemType File -Force
```

Затем откройте `.env` и добавьте (см. SETUP_INSTRUCTIONS.md)

### 5. Создание миграций:
```powershell
alembic revision --autogenerate -m "Initial migration"
```

### 6. Применение миграций:
```powershell
alembic upgrade head
```

### 7. Запуск сервера:
```powershell
uvicorn app.main:app --reload
```

Или через run.py:
```powershell
python run.py
```

---

## 🔧 Проверка установки

### Проверить Python:
```powershell
python --version
```

### Проверить установленные пакеты:
```powershell
pip list | Select-String "fastapi|alembic|sqlalchemy"
```

### Проверить структуру:
```powershell
Get-ChildItem app\models\
```

---

## 📝 Git команды

### Инициализация (если ещё не сделано):
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System"
git init
```

### Добавление файлов:
```powershell
git add .
```

### Проверка статуса:
```powershell
git status
```

### Создание коммита:
```powershell
git commit -m "feat: Initial project setup with backend structure and models"
```

См. [GIT_COMMIT_INFO.md](./GIT_COMMIT_INFO.md) для полного сообщения коммита.

---

## 🚂 Railway команды

### Установка Railway CLI:
```powershell
# Через npm (если установлен Node.js)
npm install -g @railway/cli

# Или через scoop
scoop install railway
```

### Вход в Railway:
```powershell
railway login
```

### Инициализация проекта:
```powershell
cd "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System"
railway init
```

### Деплой:
```powershell
railway up
```

### Просмотр логов:
```powershell
railway logs
```

### Выполнение команд:
```powershell
railway run alembic upgrade head
```

---

## ⚠️ Решение проблем

### Проблема: "alembic не распознан"
**Решение:**
```powershell
# Убедитесь, что venv активирован
.\venv\Scripts\Activate.ps1

# Проверьте установку
pip show alembic

# Если не установлен
pip install alembic
```

### Проблема: "uvicorn не распознан"
**Решение:**
```powershell
.\venv\Scripts\Activate.ps1
pip install uvicorn[standard]
```

### Проблема: Ошибка с psycopg2-binary
**Решение:**
```powershell
# Это нормально для Windows без PostgreSQL
# Установите остальные пакеты без psycopg2-binary
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings

# psycopg2-binary нужен только для синхронных миграций
# Мы используем async, поэтому можно пропустить
```

### Проблема: Ошибки с путями
**Решение**: Всегда используйте кавычки:
```powershell
cd "путь с пробелами"
```

### Проблема: Ошибка кодировки
**Решение**: Установите UTF-8:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['*:Encoding'] = 'utf8'
```

---

## 📋 Чеклист перед запуском

- [ ] Python 3.11+ установлен
- [ ] Виртуальное окружение создано и активировано
- [ ] Зависимости установлены (`pip install -r requirements.txt`)
- [ ] Файл `.env` создан в папке `backend/`
- [ ] Миграции применены (`alembic upgrade head`)
- [ ] Сервер запускается без ошибок

---

## 🎯 Быстрая команда для всего сразу

Создайте файл `setup.ps1` в папке `backend/`:

```powershell
# setup.ps1
$projectPath = "C:\Users\click\OneDrive\Рабочий стол\МГТУ\Python Projects\BESTMoscowBot\BEST PR System\backend"

Set-Location $projectPath

# Создать venv если не существует
if (-not (Test-Path "venv")) {
    python -m venv venv
}

# Активировать
.\venv\Scripts\Activate.ps1

# Обновить pip
python -m pip install --upgrade pip

# Установить зависимости (пропуская psycopg2-binary если ошибка)
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings python-multipart

Write-Host "✅ Установка завершена!" -ForegroundColor Green
Write-Host "Следующие шаги:" -ForegroundColor Yellow
Write-Host "1. Создайте .env файл (см. SETUP_INSTRUCTIONS.md)" -ForegroundColor Cyan
Write-Host "2. Запустите: alembic upgrade head" -ForegroundColor Cyan
Write-Host "3. Запустите: uvicorn app.main:app --reload" -ForegroundColor Cyan
```

Затем запустите:
```powershell
.\setup.ps1
```
