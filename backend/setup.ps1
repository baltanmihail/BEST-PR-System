# Скрипт автоматической установки для Windows PowerShell

Write-Host "🚀 Установка BEST PR System Backend" -ForegroundColor Cyan
Write-Host ""

# Проверка Python
Write-Host "Проверка Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Python не найден! Установите Python 3.11+" -ForegroundColor Red
    exit 1
}
Write-Host "✅ $pythonVersion" -ForegroundColor Green
Write-Host ""

# Создание виртуального окружения
Write-Host "Создание виртуального окружения..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "✅ Виртуальное окружение создано" -ForegroundColor Green
} else {
    Write-Host "✅ Виртуальное окружение уже существует" -ForegroundColor Green
}
Write-Host ""

# Активация виртуального окружения
Write-Host "Активация виртуального окружения..." -ForegroundColor Yellow
try {
    & .\venv\Scripts\Activate.ps1
    Write-Host "✅ Виртуальное окружение активировано" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Ошибка активации. Попробуйте вручную:" -ForegroundColor Yellow
    Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
    Write-Host "   Или выполните:" -ForegroundColor Yellow
    Write-Host "   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser" -ForegroundColor Cyan
}
Write-Host ""

# Обновление pip
Write-Host "Обновление pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip
Write-Host ""

# Установка зависимостей
Write-Host "Установка зависимостей..." -ForegroundColor Yellow
Write-Host "⚠️  Если возникнет ошибка с psycopg2-binary - это нормально для Windows!" -ForegroundColor Yellow
Write-Host "   Устанавливаем основные пакеты..." -ForegroundColor Yellow

# Устанавливаем основные пакеты (psycopg2-binary опционален)
pip install fastapi uvicorn sqlalchemy alembic asyncpg aiosqlite python-jose python-dotenv pydantic pydantic-settings python-multipart aiohttp aiofiles python-dateutil pytz

# Пробуем установить psycopg2-binary (не критично)
Write-Host ""
Write-Host "Попытка установить psycopg2-binary (не критично)..." -ForegroundColor Yellow
pip install psycopg2-binary 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ psycopg2-binary установлен" -ForegroundColor Green
} else {
    Write-Host "⚠️  psycopg2-binary не установлен (это нормально для Windows)" -ForegroundColor Yellow
    Write-Host "   Для разработки используйте SQLite" -ForegroundColor Cyan
}

Write-Host "✅ Основные зависимости установлены" -ForegroundColor Green
Write-Host ""

# Проверка .env файла
Write-Host "Проверка .env файла..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  Файл .env не найден!" -ForegroundColor Yellow
    Write-Host "Создайте файл .env в папке backend/ с содержимым:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "DATABASE_URL=sqlite:///./best_pr_system.db" -ForegroundColor Gray
    Write-Host "SECRET_KEY=your-secret-key-change-in-production" -ForegroundColor Gray
    Write-Host "TELEGRAM_BOT_TOKEN=your-token" -ForegroundColor Gray
    Write-Host "TELEGRAM_ADMIN_IDS=5079636941" -ForegroundColor Gray
    Write-Host "ENVIRONMENT=development" -ForegroundColor Gray
    Write-Host "LOG_LEVEL=INFO" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "✅ Файл .env найден" -ForegroundColor Green
}
Write-Host ""

Write-Host "✅ Установка завершена!" -ForegroundColor Green
Write-Host ""
Write-Host "Следующие шаги:" -ForegroundColor Yellow
Write-Host "1. Создайте/проверьте .env файл" -ForegroundColor Cyan
Write-Host "2. Создайте миграции: alembic revision --autogenerate -m 'Initial migration'" -ForegroundColor Cyan
Write-Host "3. Примените миграции: alembic upgrade head" -ForegroundColor Cyan
Write-Host "4. Запустите сервер: uvicorn app.main:app --reload" -ForegroundColor Cyan
Write-Host ""
Write-Host "Документация будет доступна по адресу: http://localhost:8000/docs" -ForegroundColor Magenta
