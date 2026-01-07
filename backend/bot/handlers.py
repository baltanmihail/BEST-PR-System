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
import os

logger = logging.getLogger(__name__)

router = Router()

# URL API - используем переменную окружения или дефолт
# Если запускаем локально - используем localhost, иначе Railway URL
def get_api_url():
    """Получить URL API"""
    api_url = os.getenv('API_URL')
    if api_url:
        return api_url + settings.API_V1_PREFIX
    
    # Если бот и API в одном сервисе на Railway - используем localhost
    environment = os.getenv('ENVIRONMENT', 'development')
    port = os.getenv('PORT', '8080')
    
    if environment == 'production':
        # На Railway в одном сервисе используем localhost
        # Если нужен внешний URL - установите API_URL в переменных окружения
        api_url_local = f'http://localhost:{port}' + settings.API_V1_PREFIX
        logger.info(f"🔗 API URL для бота: {api_url_local}")
        return api_url_local
    
    return 'http://localhost:8000' + settings.API_V1_PREFIX

API_URL = get_api_url()
logger.info(f"📡 Bot will use API URL: {API_URL}")


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
    
    logger.debug(f"Calling API: {method} {url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if method.upper() == "GET":
                response = await client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = await client.post(url, json=data, headers=headers)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json() if response.content else {}
    except httpx.ConnectError as e:
        logger.error(f"API connection error: {e}. URL: {url}")
        logger.error("Возможно, API ещё не запустился. Попробуйте позже.")
        return {"error": "API недоступен. Попробуйте позже."}
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
    
    # Проверяем статус активации
    is_active = user_data.get("is_active", False)
    
    if not is_active:
        # Получаем статус заявки
        headers = {"Authorization": f"Bearer {access_token}"}
        app_response = await call_api("GET", "/moderation/my-application", headers=headers)
        
        # Обрабатываем ошибку 403 (пользователь неактивен, заявки нет)
        if "error" in app_response or app_response.get("status_code") == 403:
            # Заявки ещё нет, пользователь только что зарегистрировался
            welcome_text = (
                f"👋 Привет, {user.first_name}!\n\n"
                f"📝 Пожалуйста, заполни заявку на регистрацию через веб-интерфейс:\n"
                f"https://best-pr-system.up.railway.app/\n\n"
                f"После одобрения заявки ты получишь полный доступ к системе."
            )
        elif app_response.get("status") == "pending":
            welcome_text = (
                f"👋 Привет, {user.first_name}!\n\n"
                f"⏳ Твоя заявка на регистрацию находится на рассмотрении.\n"
                f"Мы уведомим тебя, когда она будет одобрена!\n\n"
                f"💡 Пока можешь заполнить заявку через веб-интерфейс:\n"
                f"https://best-pr-system.up.railway.app/"
            )
        elif app_response.get("status") == "rejected":
            reason = app_response.get("application_data", {}).get("rejection_reason", "не указана")
            welcome_text = (
                f"👋 Привет, {user.first_name}!\n\n"
                f"❌ Твоя заявка была отклонена.\n"
                f"Причина: {reason}\n\n"
                f"💡 Ты можешь подать новую заявку через веб-интерфейс."
            )
        else:
            welcome_text = (
                f"👋 Привет, {user.first_name}!\n\n"
                f"📝 Пожалуйста, заполни заявку на регистрацию через веб-интерфейс:\n"
                f"https://best-pr-system.up.railway.app/\n\n"
                f"После одобрения заявки ты получишь полный доступ к системе."
            )
    else:
        welcome_text = (
            f"👋 Привет, {user.first_name}!\n\n"
            f"✅ Добро пожаловать в BEST PR System!\n\n"
            f"📊 Твоя статистика:\n"
            f"• Уровень: {user_data.get('level', 1)}\n"
            f"• Баллы: {user_data.get('points', 0)}\n"
            f"• Роль: {user_data.get('role', 'novice')}\n\n"
            f"💡 Используй команды:\n"
            f"/tasks - мои задачи\n"
            f"/stats - статистика\n"
            f"/leaderboard - рейтинг\n"
            f"/equipment - оборудование\n"
            f"/notifications - уведомления\n"
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
    
    # Получаем статистику через API геймификации
    stats_response = await call_api("GET", "/gamification/stats", headers=headers)
    
    if "error" in stats_response:
        await message.answer("❌ Ошибка при загрузке статистики.")
        return
    
    stats = stats_response
    
    stats_text = (
        f"📊 Твоя статистика:\n\n"
        f"🎯 Уровень: {stats.get('level', 1)}\n"
        f"⭐ Баллы: {stats.get('points', 0)}\n"
        f"👤 Роль: {stats.get('role', 'novice')}\n"
        f"📋 Активных задач: {stats.get('active_tasks', 0)}\n"
        f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
        f"🏆 Ачивок: {stats.get('achievements_count', 0)}"
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
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await call_api("GET", "/gamification/leaderboard?limit=10", headers=headers)
    
    if "error" in response or not response:
        await message.answer("❌ Ошибка при загрузке рейтинга.")
        return
    
    leaderboard = response if isinstance(response, list) else []
    
    if not leaderboard:
        await message.answer("📊 Рейтинг пока пуст.")
        return
    
    text = "🏆 ТОП-10 участников:\n\n"
    
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    
    for i, user in enumerate(leaderboard[:10], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += (
            f"{medal} {user.get('full_name', 'Unknown')}\n"
            f"   ⭐ {user.get('points', 0)} баллов | "
            f"Уровень {user.get('level', 1)} | "
            f"✅ {user.get('completed_tasks', 0)} задач\n\n"
        )
    
    await message.answer(text)


@router.message(Command("equipment"))
async def cmd_equipment(message: Message, state: FSMContext):
    """Команда /equipment - работа с оборудованием"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "⚠️ Сначала выполните команду /start для авторизации."
        )
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Получаем мои заявки на оборудование
    requests_response = await call_api("GET", "/equipment/requests", headers=headers)
    
    if "error" in requests_response:
        await message.answer("❌ Ошибка при загрузке заявок.")
        return
    
    requests = requests_response if isinstance(requests_response, list) else []
    
    if not requests:
        text = (
            "📦 У тебя нет заявок на оборудование.\n\n"
            "💡 Для создания заявки используй веб-интерфейс:\n"
            "https://best-pr-system.up.railway.app/\n\n"
            "Или возьми задачу типа Channel - система автоматически предложит оборудование."
        )
    else:
        text = f"📦 Твои заявки на оборудование ({len(requests)}):\n\n"
        
        status_emoji = {
            "pending": "⏳",
            "approved": "✅",
            "rejected": "❌",
            "active": "📦",
            "completed": "✔️",
            "cancelled": "🚫"
        }
        
        for i, req in enumerate(requests[:5], 1):  # Показываем первые 5
            emoji = status_emoji.get(req.get("status"), "❓")
            text += (
                f"{i}. {emoji} {req.get('equipment_name', 'Unknown')}\n"
                f"   Статус: {req.get('status')}\n"
                f"   Даты: {req.get('start_date')} - {req.get('end_date')}\n\n"
            )
    
    await message.answer(text)


@router.message(Command("notifications"))
async def cmd_notifications(message: Message, state: FSMContext):
    """Команда /notifications - уведомления"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "⚠️ Сначала выполните команду /start для авторизации."
        )
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Получаем непрочитанные уведомления
    response = await call_api("GET", "/notifications?unread_only=true&limit=10", headers=headers)
    
    if "error" in response:
        await message.answer("❌ Ошибка при загрузке уведомлений.")
        return
    
    unread_count = response.get("unread_count", 0)
    notifications = response.get("items", [])
    
    if unread_count == 0:
        await message.answer("✅ Нет непрочитанных уведомлений!")
        return
    
    text = f"🔔 Непрочитанных уведомлений: {unread_count}\n\n"
    
    type_emoji = {
        "task_assigned": "📋",
        "task_completed": "✅",
        "task_deadline": "⏰",
        "equipment_request": "📦",
        "equipment_approved": "✅",
        "equipment_rejected": "❌",
        "moderation_approved": "🎉",
        "moderation_rejected": "😔",
        "new_task": "🆕",
        "task_review": "👁️",
        "achievement_unlocked": "🏆"
    }
    
    for i, notif in enumerate(notifications[:5], 1):  # Показываем первые 5
        emoji = type_emoji.get(notif.get("type"), "📢")
        text += (
            f"{i}. {emoji} {notif.get('title')}\n"
            f"   {notif.get('message')}\n\n"
        )
    
    if unread_count > 5:
        text += f"... и ещё {unread_count - 5} уведомлений"
    
    text += "\n💡 Используй веб-интерфейс для просмотра всех уведомлений."
    
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - помощь"""
    help_text = (
        "📖 Доступные команды:\n\n"
        "/start - регистрация в системе\n"
        "/tasks - список моих задач\n"
        "/stats - моя статистика\n"
        "/leaderboard - рейтинг участников\n"
        "/equipment - мои заявки на оборудование\n"
        "/notifications - уведомления\n"
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
