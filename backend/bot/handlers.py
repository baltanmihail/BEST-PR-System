"""
Обработчики команд для Telegram бота
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from typing import Optional
from pathlib import Path
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


def get_welcome_greeting(user_name: str, role: str, points: int = 0) -> str:
    """Генерирует вариативное приветствие"""
    import random
    
    greetings = [
        f"👋 Привет, {user_name}!",
        f"🎉 Добро пожаловать, {user_name}!",
        f"🚀 Рады видеть, {user_name}!",
        f"✨ Здравствуй, {user_name}!",
    ]
    
    if role == "vp4pr":
        return random.choice([
            f"👑 Приветствую, {user_name}!",
            f"🎯 Добро пожаловать, {user_name}!",
        ])
    elif "coordinator" in role:
        return random.choice([
            f"💼 Привет, {user_name}!",
            f"🎯 Здравствуй, {user_name}!",
        ])
    elif points > 1000:
        return random.choice([
            f"⭐ Привет, чемпион {user_name}!",
            f"🏆 Здравствуй, {user_name}!",
        ])
    else:
        return random.choice(greetings)


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
    
    # Проверяем статус активации и роль
    is_active = user_data.get("is_active", False)
    user_role = user_data.get("role", "novice")
    points = user_data.get("points", 0)
    
    # Путь к приветственному фото
    # Пробуем разные пути для локальной разработки и Railway
    base_path = Path(__file__).parent.parent.parent
    welcome_photo_path = None
    
    # Варианты путей
    possible_paths = [
        base_path / "BEST logos" / "best_welcome.jpg",  # Локально
        base_path.parent / "BEST logos" / "best_welcome.jpg",  # Альтернативный локальный
        Path("/app") / "BEST logos" / "best_welcome.jpg",  # Railway
        Path("/app/backend") / ".." / "BEST logos" / "best_welcome.jpg",  # Railway альтернативный
    ]
    
    for path in possible_paths:
        if path.exists():
            welcome_photo_path = path
            break
    
    # Создаём клавиатуру с инлайн-кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    if not is_active:
        # Незарегистрированный пользователь
        headers = {"Authorization": f"Bearer {access_token}"}
        app_response = await call_api("GET", "/moderation/my-application", headers=headers)
        
        greeting = get_welcome_greeting(user.first_name, "unregistered")
        
        if "error" in app_response or app_response.get("status_code") == 403:
            # Заявки ещё нет
            welcome_text = (
                f"{greeting}\n\n"
                f"🎯 Добро пожаловать в BEST PR System!\n\n"
                f"📋 Ты можешь:\n"
                f"• 👀 Просматривать доступные задачи\n"
                f"• 🏆 Смотреть рейтинг участников\n"
                f"• 📊 Изучать статистику системы\n\n"
                f"💡 Для взятия задач и работы с оборудованием нужно зарегистрироваться."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="view_stats"),
                ],
                [
                    InlineKeyboardButton(text="📝 Зарегистрироваться", url="https://best-pr-system.up.railway.app/"),
                ],
            ]
        elif app_response.get("status") == "pending":
            welcome_text = (
                f"{greeting}\n\n"
                f"⏳ Твоя заявка на рассмотрении.\n"
                f"Мы уведомим тебя, когда она будет одобрена!\n\n"
                f"💡 Пока можешь просматривать доступные задачи и рейтинг."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
            ]
        elif app_response.get("status") == "rejected":
            reason = app_response.get("application_data", {}).get("rejection_reason", "не указана")
            welcome_text = (
                f"{greeting}\n\n"
                f"❌ Твоя заявка была отклонена.\n"
                f"Причина: {reason}\n\n"
                f"💡 Ты можешь подать новую заявку."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📝 Подать заявку", url="https://best-pr-system.up.railway.app/"),
                ],
            ]
        else:
            welcome_text = (
                f"{greeting}\n\n"
                f"🎯 Добро пожаловать в BEST PR System!\n\n"
                f"📋 Ты можешь:\n"
                f"• 👀 Просматривать доступные задачи\n"
                f"• 🏆 Смотреть рейтинг участников\n"
                f"• 📊 Изучать статистику системы\n\n"
                f"💡 Для взятия задач и работы с оборудованием нужно зарегистрироваться."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="view_stats"),
                ],
                [
                    InlineKeyboardButton(text="📝 Зарегистрироваться", url="https://best-pr-system.up.railway.app/"),
                ],
            ]
    else:
        # Зарегистрированный пользователь
        greeting = get_welcome_greeting(user.first_name, user_role, points)
        
        if user_role == "vp4pr":
            welcome_text = (
                f"{greeting}\n\n"
                f"👑 Добро пожаловать в панель управления!\n\n"
                f"📊 Статистика:\n"
                f"• Уровень: {user_data.get('level', 1)}\n"
                f"• Баллы: {points}\n"
                f"• Выполнено задач: {user_data.get('completed_tasks', 0)}\n\n"
                f"💼 Доступные функции управления системой."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks"),
                    InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
                ],
                [
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                    InlineKeyboardButton(text="⚙️ Управление", callback_data="admin_panel"),
                ],
                [
                    InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
                    InlineKeyboardButton(text="📦 Оборудование", callback_data="equipment"),
                ],
            ]
        elif "coordinator" in user_role:
            welcome_text = (
                f"{greeting}\n\n"
                f"💼 Добро пожаловать, координатор!\n\n"
                f"📊 Твоя статистика:\n"
                f"• Уровень: {user_data.get('level', 1)}\n"
                f"• Баллы: {points}\n"
                f"• Выполнено задач: {user_data.get('completed_tasks', 0)}\n\n"
                f"🎯 Управляй задачами и модерацией."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="my_tasks"),
                    InlineKeyboardButton(text="✅ Модерация", callback_data="moderation"),
                ],
                [
                    InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
                [
                    InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
                ],
            ]
        else:
            # Обычный зарегистрированный пользователь
            welcome_text = (
                f"{greeting}\n\n"
                f"✅ Добро пожаловать в BEST PR System!\n\n"
                f"📊 Твоя статистика:\n"
                f"• Уровень: {user_data.get('level', 1)}\n"
                f"• Баллы: {points}\n"
                f"• Роль: {user_role}\n"
                f"• Выполнено: {user_data.get('completed_tasks', 0)} задач\n"
                f"• 🏆 Ачивок: {user_data.get('achievements_count', 0)}\n\n"
                f"💡 Выбери действие ниже:"
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks"),
                    InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
                ],
                [
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                    InlineKeyboardButton(text="📦 Оборудование", callback_data="equipment"),
                ],
                [
                    InlineKeyboardButton(text="🔔 Уведомления", callback_data="notifications"),
                ],
            ]
    
    # Отправляем фото с текстом и кнопками
    try:
        if welcome_photo_path and welcome_photo_path.exists():
            photo = FSInputFile(str(welcome_photo_path))
            await message.answer_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=keyboard
            )
        else:
            # Если фото нет, отправляем только текст
            logger.info(f"Welcome photo not found at {welcome_photo_path}, sending text only")
            await message.answer(
                welcome_text,
                reply_markup=keyboard
            )
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        # Fallback - отправляем только текст
        await message.answer(
            welcome_text,
            reply_markup=keyboard
        )


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


@router.callback_query(F.data == "view_tasks")
async def callback_view_tasks(callback: CallbackQuery, state: FSMContext):
    """Просмотр задач (для незарегистрированных)"""
    # Получаем публичные задачи
    response = await call_api("GET", "/public/tasks?limit=5")
    
    if "error" in response or not response.get("items"):
        await callback.answer("❌ Ошибка при загрузке задач.", show_alert=True)
        return
    
    tasks = response.get("items", [])[:5]
    text = "📋 Доступные задачи:\n\n"
    
    for i, task in enumerate(tasks, 1):
        text += f"{i}. {task.get('title', 'Без названия')}\n"
        text += f"   Тип: {task.get('type', 'unknown')}\n\n"
    
    text += "💡 Для взятия задачи зарегистрируйся!"
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "view_leaderboard")
async def callback_view_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Просмотр рейтинга (публичный)"""
    response = await call_api("GET", "/public/leaderboard?limit=10")
    
    if "error" in response or not response:
        await callback.answer("❌ Ошибка при загрузке рейтинга.", show_alert=True)
        return
    
    leaderboard = response if isinstance(response, list) else []
    
    if not leaderboard:
        await callback.message.answer("📊 Рейтинг пока пуст.")
        await callback.answer()
        return
    
    text = "🏆 ТОП-10 участников:\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    
    for i, user in enumerate(leaderboard[:10], 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += (
            f"{medal} {user.get('full_name', 'Unknown')}\n"
            f"   ⭐ {user.get('points', 0)} баллов | "
            f"Уровень {user.get('level', 1)}\n\n"
        )
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "view_stats")
async def callback_view_stats(callback: CallbackQuery, state: FSMContext):
    """Просмотр статистики системы (публичный)"""
    response = await call_api("GET", "/public/stats")
    
    if "error" in response:
        await callback.answer("❌ Ошибка при загрузке статистики.", show_alert=True)
        return
    
    stats = response
    text = (
        f"📊 Статистика системы:\n\n"
        f"👥 Пользователей: {stats.get('total_users', 0)}\n"
        f"📋 Всего задач: {stats.get('total_tasks', 0)}\n"
        f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
        f"⭐ Всего баллов: {stats.get('total_points', 0)}\n"
    )
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery, state: FSMContext):
    """Мои задачи (для зарегистрированных)"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.answer("⚠️ Сначала выполните /start для авторизации.", show_alert=True)
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await call_api("GET", "/tasks", headers=headers)
    
    if "error" in response:
        await callback.answer("❌ Ошибка при загрузке задач.", show_alert=True)
        return
    
    tasks = response.get("items", [])
    active_tasks = [t for t in tasks if t.get("status") not in ["completed", "cancelled"]]
    
    if not active_tasks:
        await callback.message.answer("✅ Все задачи выполнены!")
        await callback.answer()
        return
    
    text = f"📋 Твои активные задачи ({len(active_tasks)}):\n\n"
    
    for i, task in enumerate(active_tasks[:10], 1):
        status_emoji = {
            "draft": "📝", "open": "🟢", "assigned": "👤",
            "in_progress": "⚙️", "review": "👁️",
        }.get(task.get("status"), "❓")
        
        text += (
            f"{i}. {status_emoji} {task.get('title', 'Без названия')}\n"
            f"   Тип: {task.get('type', 'unknown')}\n\n"
        )
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "my_stats")
async def callback_my_stats(callback: CallbackQuery, state: FSMContext):
    """Моя статистика"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.answer("⚠️ Сначала выполните /start для авторизации.", show_alert=True)
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    stats_response = await call_api("GET", "/gamification/stats", headers=headers)
    
    if "error" in stats_response:
        await callback.answer("❌ Ошибка при загрузке статистики.", show_alert=True)
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
    
    await callback.message.answer(stats_text)
    await callback.answer()


@router.callback_query(F.data == "equipment")
async def callback_equipment(callback: CallbackQuery, state: FSMContext):
    """Оборудование - требует регистрации"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.answer("⚠️ Для работы с оборудованием нужно зарегистрироваться!", show_alert=True)
        await callback.message.answer(
            "📦 Работа с оборудованием доступна только зарегистрированным пользователям.\n\n"
            "💡 Зарегистрируйся через веб-интерфейс:\n"
            "https://best-pr-system.up.railway.app/"
        )
        return
    
    # Проверяем, активен ли пользователь
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = await call_api("GET", "/auth/me", headers=headers)
    
    if "error" in user_response or not user_response.get("is_active"):
        await callback.answer("⚠️ Для работы с оборудованием нужно быть активным пользователем!", show_alert=True)
        return
    
    # Получаем оборудование
    equipment_response = await call_api("GET", "/equipment", headers=headers)
    
    if "error" in equipment_response:
        await callback.answer("❌ Ошибка при загрузке оборудования.", show_alert=True)
        return
    
    equipment_list = equipment_response.get("items", [])
    
    if not equipment_list:
        await callback.message.answer("📦 Оборудование пока не добавлено.")
        await callback.answer()
        return
    
    text = "📦 Доступное оборудование:\n\n"
    for i, eq in enumerate(equipment_list[:10], 1):
        status_emoji = {
            "available": "✅",
            "rented": "🔴",
            "maintenance": "🔧",
            "broken": "❌",
        }.get(eq.get("status"), "❓")
        
        text += f"{i}. {status_emoji} {eq.get('name', 'Unknown')}\n"
        text += f"   Категория: {eq.get('category', 'unknown')}\n\n"
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "notifications")
async def callback_notifications(callback: CallbackQuery, state: FSMContext):
    """Уведомления"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.answer("⚠️ Сначала выполните /start для авторизации.", show_alert=True)
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await call_api("GET", "/notifications?limit=5", headers=headers)
    
    if "error" in response:
        await callback.answer("❌ Ошибка при загрузке уведомлений.", show_alert=True)
        return
    
    notifications = response.get("items", [])
    
    if not notifications:
        await callback.message.answer("🔔 У тебя нет уведомлений.")
        await callback.answer()
        return
    
    text = "🔔 Последние уведомления:\n\n"
    for notif in notifications[:5]:
        emoji = "🔴" if notif.get("is_read") == False else "⚪"
        text += f"{emoji} {notif.get('title', 'Без названия')}\n"
        text += f"   {notif.get('message', '')[:50]}...\n\n"
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "moderation")
async def callback_moderation(callback: CallbackQuery, state: FSMContext):
    """Модерация (только для координаторов)"""
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.answer("⚠️ Сначала выполните /start для авторизации.", show_alert=True)
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await call_api("GET", "/moderation/applications", headers=headers)
    
    if "error" in response:
        await callback.answer("❌ Ошибка при загрузке заявок.", show_alert=True)
        return
    
    applications = response.get("items", [])
    pending = [a for a in applications if a.get("status") == "pending"]
    
    if not pending:
        await callback.message.answer("✅ Нет заявок на рассмотрении.")
        await callback.answer()
        return
    
    text = f"📋 Заявки на модерацию ({len(pending)}):\n\n"
    for i, app in enumerate(pending[:5], 1):
        user_name = app.get("application_data", {}).get("full_name", "Unknown")
        text += f"{i}. 👤 {user_name}\n"
        text += f"   Статус: ожидает рассмотрения\n\n"
    
    text += "💡 Используй веб-интерфейс для одобрения/отклонения."
    
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def callback_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Админ-панель (только для VP4PR)"""
    await callback.message.answer(
        "⚙️ Панель управления доступна через веб-интерфейс:\n"
        "https://best-pr-system.up.railway.app/\n\n"
        "💡 Там ты можешь управлять всеми аспектами системы."
    )
    await callback.answer()


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
