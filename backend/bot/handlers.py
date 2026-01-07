"""
Обработчики команд для Telegram бота
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from typing import Optional
import httpx
import logging

from app.config import settings
import hmac
import hashlib

logger = logging.getLogger(__name__)

router = Router()

# URL API - используем переменную окружения или дефолт
# Если запускаем локально - используем localhost, иначе Railway URL
def get_api_url():
    """Получить URL API"""
    api_url = os.getenv('API_URL')
    if api_url:
        return api_url + settings.API_V1_PREFIX
    
    # Проверяем, есть ли Railway URL в DATABASE_URL
    db_url = settings.DATABASE_URL
    if 'railway' in db_url.lower():
        # Предполагаем, что API на том же домене
        return 'https://best-pr-system.up.railway.app' + settings.API_V1_PREFIX
    
    return 'http://localhost:8000' + settings.API_V1_PREFIX

API_URL = get_api_url()


def generate_telegram_hash(data: dict, bot_token: str) -> str:
    """
    Генерирует hash для проверки данных Telegram Web App
    
    В реальном боте это делается на клиенте (фронтенд),
    но здесь мы симулируем для тестирования
    """
    # Создаём копию данных без hash
    data_copy = {k: v for k, v in data.items() if k != 'hash'}
    
    # Создаём строку для проверки (как в verify_telegram_auth)
    data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(data_copy.items()))
    
    # Получаем секретный ключ от Telegram Bot API
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Вычисляем hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return calculated_hash


async def call_api(method: str, endpoint: str, data: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
    """Вызов API endpoint"""
    url = f"{API_URL}{endpoint}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.HTTPStatusError as e:
        logger.error(f"API error: {e.response.status_code} - {e.response.text}")
        return {"error": f"API error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"API call error: {e}")
        return {"error": str(e)}


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """Команда /start - регистрация/авторизация пользователя"""
    user = message.from_user
    
    # Подготавливаем данные для авторизации через Telegram
    auth_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "username": user.username or "",
        "auth_date": int(message.date.timestamp()),
    }
    
    # Генерируем hash для проверки подлинности
    auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
    
    # Авторизуемся через API
    response = await call_api("POST", "/auth/telegram", data=auth_data)
    
    if "error" in response:
        await message.answer(
            "❌ Ошибка авторизации. Попробуйте позже или обратитесь к администратору."
        )
        return
    
    access_token = response.get("access_token")
    user_data = response.get("user", {})
    
    # Сохраняем токен для последующих запросов
    await state.update_data(access_token=access_token)
    
    welcome_text = (
        f"👋 Привет, {user.first_name}!\n\n"
        f"✅ Ты успешно зарегистрирован в BEST PR System.\n\n"
        f"📊 Твоя статистика:\n"
        f"• Уровень: {user_data.get('level', 1)}\n"
        f"• Баллы: {user_data.get('points', 0)}\n\n"
        f"💡 Используй команды:\n"
        f"/tasks - мои задачи\n"
        f"/stats - статистика\n"
        f"/leaderboard - рейтинг\n"
        f"/help - помощь"
    )
    
    await message.answer(welcome_text)


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, state: FSMContext):
    """Команда /tasks - список задач пользователя"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "⚠️ Сначала выполните команду /start для авторизации."
        )
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await call_api("GET", "/tasks", headers=headers)
    
    if "error" in response:
        await message.answer("❌ Ошибка при загрузке задач.")
        return
    
    tasks = response.get("items", [])
    
    if not tasks:
        await message.answer("📋 У тебя пока нет задач.")
        return
    
    # Фильтруем активные задачи
    active_tasks = [t for t in tasks if t.get("status") not in ["completed", "cancelled"]]
    
    if not active_tasks:
        await message.answer("✅ Все задачи выполнены!")
        return
    
    text = f"📋 Твои активные задачи ({len(active_tasks)}):\n\n"
    
    for i, task in enumerate(active_tasks[:10], 1):  # Показываем первые 10
        status_emoji = {
            "draft": "📝",
            "open": "🟢",
            "assigned": "👤",
            "in_progress": "⚙️",
            "review": "👁️",
        }.get(task.get("status"), "❓")
        
        text += (
            f"{i}. {status_emoji} {task.get('title', 'Без названия')}\n"
            f"   Тип: {task.get('type', 'unknown')}\n"
            f"   Статус: {task.get('status', 'unknown')}\n\n"
        )
    
    await message.answer(text)


@router.message(Command("stats"))
async def cmd_stats(message: Message, state: FSMContext):
    """Команда /stats - статистика пользователя"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "⚠️ Сначала выполните команду /start для авторизации."
        )
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Получаем информацию о пользователе
    user_response = await call_api("GET", "/auth/me", headers=headers)
    
    if "error" in user_response:
        await message.answer("❌ Ошибка при загрузке статистики.")
        return
    
    user = user_response
    
    # Получаем задачи пользователя
    tasks_response = await call_api("GET", "/tasks", headers=headers)
    tasks = tasks_response.get("items", []) if "error" not in tasks_response else []
    
    active_tasks = len([t for t in tasks if t.get("status") not in ["completed", "cancelled"]])
    completed_tasks = len([t for t in tasks if t.get("status") == "completed"])
    
    stats_text = (
        f"📊 Твоя статистика:\n\n"
        f"🎯 Уровень: {user.get('level', 1)}\n"
        f"⭐ Баллы: {user.get('points', 0)}\n"
        f"📋 Активных задач: {active_tasks}\n"
        f"✅ Выполнено: {completed_tasks}\n"
        f"🔥 Серия дней: {user.get('streak_days', 0)}"
    )
    
    await message.answer(stats_text)


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, state: FSMContext):
    """Команда /leaderboard - рейтинг пользователей"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "⚠️ Сначала выполните команду /start для авторизации."
        )
        return
    
    # TODO: Добавить endpoint /api/v1/gamification/leaderboard
    await message.answer(
        "🏆 Рейтинг временно недоступен. "
        "Используй веб-интерфейс для просмотра рейтинга."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - помощь"""
    help_text = (
        "📖 Доступные команды:\n\n"
        "/start - регистрация в системе\n"
        "/tasks - список моих задач\n"
        "/stats - моя статистика\n"
        "/leaderboard - рейтинг участников\n"
        "/help - эта справка\n\n"
        "💡 Также можно использовать веб-интерфейс для более удобной работы."
    )
    
    await message.answer(help_text)


@router.message()
async def handle_unknown(message: Message):
    """Обработка неизвестных сообщений"""
    await message.answer(
        "❓ Неизвестная команда. Используйте /help для списка доступных команд."
    )
