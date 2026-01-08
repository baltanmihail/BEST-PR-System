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
    
    ВАЖНО: Должно полностью соответствовать логике verify_telegram_auth
    """
    # Создаём копию данных без hash, исключая None значения и пустые строки
    # Это должно точно соответствовать логике verify_telegram_auth
    data_copy = {k: v for k, v in data.items() if k != "hash" and v is not None and v != ""}
    
    # Создаём строку для проверки (как в verify_telegram_auth)
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(data_copy.items())
    )
    
    # Получаем секретный ключ от Telegram Bot API
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    
    # Вычисляем hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return calculated_hash


async def call_api(method: str, endpoint: str, data: Optional[dict] = None, headers: Optional[dict] = None, silent_errors: Optional[list[int]] = None) -> dict:
    """Вызов API endpoint
    
    Args:
        method: HTTP метод (GET, POST, etc.)
        endpoint: API endpoint
        data: Данные для POST запроса
        headers: HTTP заголовки
        silent_errors: Список HTTP статусов, которые не нужно логировать как ошибки (например, [403, 404])
    """
    url = f"{API_URL}{endpoint}"
    
    logger.debug(f"Calling API: {method} {url}")
    
    silent_statuses = silent_errors or []
    
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
        status_code = e.response.status_code
        # Для silent_errors не логируем как ошибку (например, 403 для неактивных пользователей - это ожидаемо)
        if status_code in silent_statuses:
            logger.debug(f"API returned expected status {status_code} for {url}: {e.response.text}")
            # Возвращаем только status_code, без "error", чтобы код мог корректно обработать это
            return {"status_code": status_code}
        else:
            logger.error(f"API error: {status_code} - {e.response.text}")
            return {"error": f"API error: {status_code}", "status_code": status_code}
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


def format_role_title(role: str) -> str:
    """Человекочитаемое название роли/позиции для приветствия."""
    mapping = {
        "vp4pr": "VP4PR (руководитель PR)",
        "coordinator_smm": "Координатор SMM",
        "coordinator_design": "Координатор Design",
        "coordinator_channel": "Глава Channel",
        "coordinator_prfr": "Координатор PR-FR",
        "active_participant": "Активный участник",
        "participant": "Участник",
        "novice": "Новичок",
    }
    return mapping.get(role, role)


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, command: Command = None):
    """Команда /start - регистрация/авторизация пользователя"""
    user = message.from_user
    
    # Проверяем, есть ли параметр в команде (например, /start qr_TOKEN или /start qr_TOKEN_TELEGRAM_ID)
    start_param = None
    if message.text and len(message.text.split()) > 1:
        start_param = message.text.split()[1]
    
    # Если параметр начинается с "qr_", это QR-код авторизация/регистрация
    if start_param and start_param.startswith("qr_"):
        # Парсим параметр: qr_TOKEN или qr_TOKEN_TELEGRAM_ID_USERNAME
        parts = start_param.split("_")
        if len(parts) >= 2:
            qr_token = parts[1]  # Токен QR-сессии
            
            # Проверяем сессию через API
            check_response = await call_api("GET", f"/auth/qr/status/{qr_token}")
            
            if "error" in check_response:
                await message.answer(
                    "❌ Не удалось проверить QR-код.\n\n"
                    "Возможно, сессия истекла. Попробуйте отсканировать QR-код снова на сайте."
                )
                return
            
            # Если сессия уже подтверждена
            if check_response.get("status") == "confirmed":
                await message.answer(
                    "✅ Этот QR-код уже использован.\n\n"
                    "Если вы хотите войти снова, откройте страницу входа на сайте и отсканируйте новый QR-код."
                )
                return
            
            # Если сессия истекла
            if check_response.get("status") == "expired":
                await message.answer(
                    "⏰ QR-код истёк.\n\n"
                    "Пожалуйста, откройте страницу входа на сайте и отсканируйте новый QR-код."
                )
                return
            
            # Если сессия в статусе pending, обрабатываем QR-авторизацию
            if check_response.get("status") == "pending":
                # Сохраняем токен в состояние
                await state.update_data(qr_token=qr_token)
                
                # Формируем данные пользователя
                auth_data = {
                    "id": user.id,
                    "first_name": user.first_name or "User",
                    "auth_date": int(message.date.timestamp()),
                }
                
                if user.last_name:
                    auth_data["last_name"] = user.last_name
                if user.username:
                    auth_data["username"] = user.username
                
                # Генерируем hash
                auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
                
                # Сохраняем данные для подтверждения
                await state.update_data(qr_auth_data=auth_data)
                
                # Проверяем, есть ли данные пользователя в параметре (для упрощённой регистрации)
                is_registration_qr = len(parts) >= 3 and str(user.id) == parts[2]
                
                # Показываем подтверждение
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Подтвердить вход", callback_data=f"qr_confirm_{qr_token}"),
                        InlineKeyboardButton(text="❌ Отменить", callback_data=f"qr_cancel_{qr_token}"),
                    ]
                ])
                
                # Получаем путь к приветственному фото
                base_path = Path(__file__).parent.parent.parent
                welcome_photo_path = None
                possible_paths = [
                    base_path / "BEST logos" / "best_welcome.jpg",
                    base_path.parent / "BEST logos" / "best_welcome.jpg",
                    Path("/app") / "BEST logos" / "best_welcome.jpg",
                    Path("/app/backend") / ".." / "BEST logos" / "best_welcome.jpg",
                    Path("/app") / "backend" / ".." / "BEST logos" / "best_welcome.jpg",
                ]
                for path in possible_paths:
                    path_resolved = path.resolve()
                    if path_resolved.exists():
                        welcome_photo_path = path_resolved
                        break
                
                if is_registration_qr:
                    # Если это QR-код для регистрации, предлагаем зарегистрироваться прямо в боте
                    keyboard.inline_keyboard.append([
                        InlineKeyboardButton(
                            text="📝 Зарегистрироваться", 
                            callback_data=f"qr_register_{qr_token}"
                        ),
                    ])
                    
                    welcome_msg = (
                        f"🚀 <b>Рады видеть, {user.first_name or 'друг'}!</b>\n\n"
                        f"🎯 <b>Добро пожаловать в BEST PR System!</b>\n\n"
                        f"Вы отсканировали QR-код для регистрации.\n\n"
                        f"💡 <b>Что дальше?</b>\n"
                        f"• 📝 Нажмите «Зарегистрироваться» для подачи заявки\n"
                        f"• ✅ Или «Подтвердить вход», если уже зарегистрированы\n\n"
                        f"⚠️ Если это не вы, нажмите «Отменить»."
                    )
                    
                    if welcome_photo_path and welcome_photo_path.exists():
                        await message.answer_photo(
                            photo=FSInputFile(str(welcome_photo_path)),
                            caption=welcome_msg,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                    else:
                        await message.answer(
                            welcome_msg,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )
                else:
                    # Обычное подтверждение входа
                    await message.answer(
                        f"🔐 <b>Подтверждение входа на сайт</b>\n\n"
                        f"Вы хотите войти в аккаунт:\n"
                        f"👤 <b>{user.first_name or 'Пользователь'}</b>\n\n"
                        f"⚠️ Если это не вы, нажмите «Отменить».\n\n"
                        f"Подтвердите вход:",
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )
                return
    
    # Подготавливаем данные для авторизации через Telegram
    # ВАЖНО: first_name обязателен, если его нет - используем "User"
    first_name = user.first_name or "User"
    
    auth_data = {
        "id": user.id,
        "first_name": first_name,
        "auth_date": int(message.date.timestamp()),
    }
    
    # Добавляем опциональные поля только если они не пустые
    # Это важно для совместимости с verify_telegram_auth, который исключает пустые значения
    if user.last_name:
        auth_data["last_name"] = user.last_name
    if user.username:
        auth_data["username"] = user.username
    
    # Генерируем hash для проверки подлинности
    auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
    
    # Авторизуемся через API
    response = await call_api("POST", "/auth/telegram", data=auth_data)
    
    if "error" in response:
        error_msg = response.get("error", "Неизвестная ошибка")
        status_code = response.get("status_code")
        
        # Более информативное сообщение об ошибке
        if status_code == 401:
            await message.answer(
                "❌ Ошибка авторизации: неверные данные Telegram.\n\n"
                "Попробуйте:\n"
                "1. Перезапустить бота командой /start\n"
                "2. Если проблема сохраняется, обратитесь к администратору"
            )
        else:
            await message.answer(
                f"❌ Ошибка авторизации: {error_msg}\n\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        logger.error(f"Auth failed for user {user.id}: {error_msg} (status: {status_code})")
        return
    
    access_token = response.get("access_token")
    user_data = response.get("user", {})
    
    if not access_token:
        logger.error(f"No access_token in response for user {user.id}")
        await message.answer(
            "❌ Ошибка авторизации: не получен токен доступа.\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        return
    
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
        Path("/app") / "BEST logos" / "best_welcome.jpg",  # Railway (корень проекта)
        Path("/app/backend") / ".." / "BEST logos" / "best_welcome.jpg",  # Railway альтернативный
        Path("/app") / "backend" / ".." / "BEST logos" / "best_welcome.jpg",  # Railway (из backend)
    ]
    
    for path in possible_paths:
        path_resolved = path.resolve()
        logger.debug(f"Checking welcome photo path: {path_resolved}")
        if path_resolved.exists():
            welcome_photo_path = path_resolved
            logger.info(f"✅ Welcome photo found at: {welcome_photo_path}")
            break
    
    if not welcome_photo_path:
        logger.warning(f"⚠️ Welcome photo not found. Checked paths: {[str(p.resolve()) for p in possible_paths]}")
    
    # Создаём клавиатуру с инлайн-кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Системная шапка
    system_title = "<b>🎯 Добро пожаловать в BEST PR System!</b>"
    
    if not is_active:
        # Незарегистрированный пользователь
        headers = {"Authorization": f"Bearer {access_token}"}
        # 403 для неактивных пользователей - это ожидаемо, не логируем как ошибку
        app_response = await call_api("GET", "/moderation/my-application", headers=headers, silent_errors=[403])
        
        greeting = get_welcome_greeting(user.first_name, "unregistered")
        
        if "error" in app_response or app_response.get("status_code") == 403:
            # Заявки ещё нет - новое приветственное сообщение с мотивацией
            # Проверяем, перешёл ли пользователь с сайта (через параметр в URL или через отслеживание)
            # Пока используем простую логику - если пользователь запустил бота, он мог перейти с сайта
            
            welcome_text = (
                f"🚀 <b>Привет, {user.first_name or 'друг'}!</b>\n\n"
                f"{system_title}\n\n"
                f"🎯 <b>Что это за система?</b>\n"
                f"Это платформа для управления PR-отделом BEST Москва, где ты можешь:\n"
                f"• 📝 Брать интересные задачи по SMM, дизайну и видеопроизводству\n"
                f"• 🏆 Зарабатывать баллы и подниматься в рейтинге\n"
                f"• 🎬 Бронировать оборудование для съёмок\n"
                f"• 💼 Развиваться вместе с командой энтузиастов\n\n"
                f"💡 <b>Хочешь узнать больше?</b>\n"
                f"Перейди на сайт и посмотри, что у нас есть!"
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(
                        text="🌐 Изучить сайт", 
                        url=f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&username={user.username or ''}&first_name={user.first_name or ''}"
                    ),
                ],
                [
                    InlineKeyboardButton(text="💬 Рассказать о себе", callback_data="onboarding_start"),
                    InlineKeyboardButton(text="❓ Задать вопрос", callback_data="ask_question"),
                ],
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
            ]
        elif app_response.get("status") == "pending":
            welcome_text = (
                f"{greeting}\n\n"
                f"{system_title}\n\n"
                f"🧭 <b>Статус:</b> заявка на рассмотрении ⏳\n\n"
                f"Мы уведомим тебя, когда она будет одобрена.\n"
                f"Пока можешь просматривать задачи и рейтинг."
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
                f"{system_title}\n\n"
                f"🧭 <b>Статус:</b> заявка отклонена ❌\n"
                f"📝 <b>Причина:</b> {reason}\n\n"
                f"Ты можешь подать новую заявку."
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(text="📝 Подать заявку в боте", callback_data="register_in_bot"),
                ],
                [
                    InlineKeyboardButton(text="🌐 Подать заявку на сайте", url=settings.FRONTEND_URL + "/register"),
                ],
            ]
        else:
            # Fallback для неавторизированных
            welcome_text = (
                f"🚀 <b>Рады видеть, {user.first_name or 'друг'}!</b>\n\n"
                f"{system_title}\n\n"
                f"🧭 <b>Статус:</b> гость (без регистрации)\n\n"
                f"📋 <b>Доступно сейчас:</b>\n"
                f"• 👀 Просматривать доступные задачи\n"
                f"• 🏆 Смотреть рейтинг участников\n"
                f"• 📊 Изучать статистику системы\n\n"
                f"💡 <b>Для взятия задач и бронирования оборудования</b> нужно зарегистрироваться.\n\n"
                f"🌐 Перейди на сайт и отсканируй QR-код для регистрации:"
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
                    InlineKeyboardButton(
                        text="🌐 Перейти на сайт", 
                        url=f"{settings.FRONTEND_URL}/login?from=bot&telegram_id={user.id}&username={user.username or ''}&first_name={user.first_name or ''}"
                    ),
                ],
            ]
    else:
        # Зарегистрированный пользователь
        greeting = get_welcome_greeting(user.first_name, user_role, points)
        role_title = format_role_title(user_role)
        
        if user_role == "vp4pr":
            welcome_text = (
                f"{greeting}\n\n"
                f"{system_title}\n\n"
                f"🧭 <b>Позиция:</b> {role_title}\n"
                f"🆔 <b>Твой ID:</b> <code>{user.id}</code>\n\n"
                f"👑 <b>Панель управления</b>\n\n"
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
                f"{system_title}\n\n"
                f"🧭 <b>Позиция:</b> {role_title}\n"
                f"🆔 <b>Твой ID:</b> <code>{user.id}</code>\n\n"
                f"💼 <b>Режим координатора</b>\n\n"
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
                f"{system_title}\n\n"
                f"🧭 <b>Роль:</b> {role_title}\n"
                f"🆔 <b>Твой ID:</b> <code>{user.id}</code>\n\n"
                f"📊 Твоя статистика:\n"
                f"• Уровень: {user_data.get('level', 1)}\n"
                f"• Баллы: {points}\n"
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
    
    # Отправляем фото только для НЕактивных (первое касание/мотивация).
    # Для активных пользователей /start не должен каждый раз слать лого.
    try:
        if (not is_active) and welcome_photo_path and welcome_photo_path.exists():
            photo = FSInputFile(str(welcome_photo_path))
            await message.answer_photo(
                photo=photo,
                caption=welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Если фото нет, отправляем только текст
            logger.info(f"Welcome photo not found at {welcome_photo_path}, sending text only")
            await message.answer(
                welcome_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error sending welcome message: {e}")
        # Fallback - отправляем только текст
        await message.answer(
            welcome_text,
            reply_markup=keyboard,
            parse_mode="HTML"
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
    try:
        await callback.answer()  # Сначала отвечаем на callback
        # Получаем публичные задачи
        response = await call_api("GET", "/public/tasks?limit=5")
        
        if "error" in response or not response.get("items"):
            await callback.message.answer("❌ Ошибка при загрузке задач. Попробуйте позже.")
            return
        
        tasks = response.get("items", [])[:5]
        text = "📋 Доступные задачи:\n\n"
        
        for i, task in enumerate(tasks, 1):
            text += f"{i}. {task.get('title', 'Без названия')}\n"
            text += f"   Тип: {task.get('type', 'unknown')}\n\n"
        
        text += "💡 <b>Для взятия задачи и оборудования BEST Channel</b> зарегистрируйся по ссылке:\n"
        text += f"🔗 <a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>"
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_view_tasks: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


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
            f"{medal} {user.get('name', user.get('full_name', 'Unknown'))}\n"
            f"   ⭐ {user.get('points', 0)} баллов | "
            f"Уровень {user.get('level', 1)}\n\n"
        )
    
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "view_stats")
async def callback_view_stats(callback: CallbackQuery, state: FSMContext):
    """Просмотр статистики системы (публичный)"""
    try:
        await callback.answer()  # Сначала отвечаем на callback
        response = await call_api("GET", "/public/stats")
        
        if "error" in response:
            await callback.message.answer("❌ Ошибка при загрузке статистики. Попробуйте позже.")
            return
        
        stats = response
        text = (
            f"📊 Статистика системы:\n\n"
            f"👥 Пользователей: {stats.get('total_users', 0)}\n"
            f"📋 Всего задач: {stats.get('total_tasks', 0)}\n"
            f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
            f"⭐ Всего баллов: {stats.get('total_points', 0)}\n"
        )
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_view_stats: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "my_tasks")
async def callback_my_tasks(callback: CallbackQuery, state: FSMContext):
    """Мои задачи (для зарегистрированных)"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await call_api("GET", "/tasks", headers=headers)
        
        if "error" in response:
            await callback.message.answer("❌ Ошибка при загрузке задач. Попробуйте позже.")
            return
        
        tasks = response.get("items", [])
        active_tasks = [t for t in tasks if t.get("status") not in ["completed", "cancelled"]]
        
        if not active_tasks:
            await callback.message.answer("✅ Все задачи выполнены!")
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
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_my_tasks: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "my_stats")
async def callback_my_stats(callback: CallbackQuery, state: FSMContext):
    """Моя статистика"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        stats_response = await call_api("GET", "/gamification/stats", headers=headers)
        
        if "error" in stats_response:
            await callback.message.answer("❌ Ошибка при загрузке статистики. Попробуйте позже.")
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
    except Exception as e:
        logger.error(f"Error in callback_my_stats: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "equipment")
async def callback_equipment(callback: CallbackQuery, state: FSMContext):
    """Оборудование - требует регистрации"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer(
                f"📦 Работа с оборудованием доступна только зарегистрированным пользователям.\n\n"
                f"💡 <b>Для работы с оборудованием BEST Channel</b> зарегистрируйся по ссылке:\n"
                f"🔗 <a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>",
                parse_mode="HTML"
            )
            return
        
        # Проверяем, активен ли пользователь
        headers = {"Authorization": f"Bearer {access_token}"}
        user_response = await call_api("GET", "/auth/me", headers=headers)
        
        if "error" in user_response or not user_response.get("is_active"):
            await callback.message.answer("⚠️ Для работы с оборудованием нужно быть активным пользователем!")
            return
        
        # Получаем оборудование
        equipment_response = await call_api("GET", "/equipment", headers=headers)
        
        if "error" in equipment_response:
            await callback.message.answer("❌ Ошибка при загрузке оборудования. Попробуйте позже.")
            return
        
        equipment_list = equipment_response.get("items", [])
        
        if not equipment_list:
            await callback.message.answer("📦 Оборудование пока не добавлено.")
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
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_equipment: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "notifications")
async def callback_notifications(callback: CallbackQuery, state: FSMContext):
    """Уведомления"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await call_api("GET", "/notifications?limit=5", headers=headers)
        
        if "error" in response:
            await callback.message.answer("❌ Ошибка при загрузке уведомлений. Попробуйте позже.")
            return
        
        notifications = response.get("items", [])
        
        if not notifications:
            await callback.message.answer("🔔 У тебя нет уведомлений.")
            return
        
        text = "🔔 Последние уведомления:\n\n"
        for notif in notifications[:5]:
            emoji = "🔴" if notif.get("is_read") == False else "⚪"
            text += f"{emoji} {notif.get('title', 'Без названия')}\n"
            text += f"   {notif.get('message', '')[:50]}...\n\n"
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_notifications: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "moderation")
async def callback_moderation(callback: CallbackQuery, state: FSMContext):
    """Модерация (только для координаторов)"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await call_api("GET", "/moderation/applications", headers=headers)
        
        if "error" in response:
            await callback.message.answer("❌ Ошибка при загрузке заявок. Попробуйте позже.")
            return
        
        applications = response.get("items", [])
        pending = [a for a in applications if a.get("status") == "pending"]
        
        if not pending:
            await callback.message.answer("✅ Нет заявок на рассмотрении.")
            return
        
        text = f"📋 Заявки на модерацию ({len(pending)}):\n\n"
        for i, app in enumerate(pending[:5], 1):
            user_name = app.get("application_data", {}).get("full_name", "Unknown")
            text += f"{i}. 👤 {user_name}\n"
            text += f"   Статус: ожидает рассмотрения\n\n"
        
        text += "💡 Используй веб-интерфейс для одобрения/отклонения."
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_moderation: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "admin_panel")
async def callback_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Админ-панель (только для VP4PR)"""
    try:
        await callback.answer()
        await callback.message.answer(
            f"⚙️ Панель управления доступна через веб-интерфейс:\n"
            f"🔗 <a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>\n\n"
            f"💡 Там ты можешь управлять всеми аспектами системы.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error in callback_admin_panel: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


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
            f"{medal} {user.get('name', user.get('full_name', 'Unknown'))}\n"
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
            f"📦 У тебя нет заявок на оборудование.\n\n"
            f"💡 Для создания заявки используй веб-интерфейс:\n"
            f"🔗 <a href=\"{settings.FRONTEND_URL}\">{settings.FRONTEND_URL}</a>\n\n"
            f"Или возьми задачу типа Channel - система автоматически предложит оборудование."
        )
        parse_mode_val = "HTML"
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
        parse_mode_val = None
    
    await message.answer(text, parse_mode=parse_mode_val if parse_mode_val else None)


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


@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext):
    """Команда /register - регистрация нового пользователя"""
    user = message.from_user
    
    # Проверяем, не зарегистрирован ли уже пользователь
    auth_data = {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "username": user.username or "",
        "auth_date": int(message.date.timestamp()),
    }
    
    auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
    
    # Проверяем, авторизован ли пользователь
    response = await call_api("POST", "/auth/telegram", data=auth_data)
    
    if "error" in response:
        await message.answer(
            "❌ Ошибка авторизации. Попробуйте позже или обратитесь к администратору."
        )
        return
    
    user_data = response.get("user", {})
    
    # Если пользователь уже активен, сообщаем об этом
    if user_data.get("is_active", False):
        await message.answer(
            "✅ Ты уже зарегистрирован и активен в системе!\n\n"
            "💡 Используй /start для доступа к функциям бота."
        )
        return
    
    # Если заявка на рассмотрении
    access_token = response.get("access_token")
    if access_token:
        headers = {"Authorization": f"Bearer {access_token}"}
        app_response = await call_api("GET", "/moderation/my-application", headers=headers, silent_errors=[403])
        
        if app_response.get("status") == "pending":
            await message.answer(
                "⏳ Твоя заявка уже находится на рассмотрении!\n\n"
                "Мы уведомим тебя, когда она будет одобрена.\n"
                "Пока можешь просматривать задачи и рейтинг через /start."
            )
            return
    
    # Если пользователь ещё не зарегистрирован, начинаем процесс регистрации
    await start_registration_flow(message, state, user, auth_data)


async def start_registration_flow(message: Message, state: FSMContext, user, auth_data: dict):
    """Начинает процесс регистрации пользователя в боте"""
    try:
        # Мотивирующее сообщение перед регистрацией
        await message.answer(
            "🎯 <b>Отлично! Ты на правильном пути!</b>\n\n"
            "Осталось ещё чуть-чуть - всего пару минут, и ты станешь частью команды PR-отдела BEST Москва!\n\n"
            "💪 <b>Ты молодец, что решил присоединиться к нам!</b>\n\n"
            "📝 <b>Шаг 1:</b> Напиши своё полное ФИО (например: Иванов Иван Иванович)\n\n"
            "Напиши ФИО текстом:",
            parse_mode="HTML"
        )
        
        # Сохраняем состояние регистрации
        await state.update_data(
            registration_step="full_name",
            registration_auth_data=auth_data
        )
        
    except Exception as e:
        logger.error(f"Error in start_registration_flow: {e}")
        await message.answer(
            "❌ Произошла ошибка при начале регистрации. Попробуйте позже или используй веб-интерфейс:\n"
            f"🔗 {settings.FRONTEND_URL}/register"
        )


@router.callback_query(F.data == "register_in_bot")
async def callback_register_in_bot(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Зарегистрироваться в боте'"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Проверяем, не зарегистрирован ли уже пользователь
        auth_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
            "auth_date": int(callback.message.date.timestamp()),
        }
        
        auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
        
        # Проверяем авторизацию
        response = await call_api("POST", "/auth/telegram", data=auth_data)
        
        if "error" in response:
            await callback.message.answer(
                "❌ Ошибка авторизации. Попробуйте позже или обратитесь к администратору."
            )
            return
        
        user_data = response.get("user", {})
        
        # Если пользователь уже активен
        if user_data.get("is_active", False):
            await callback.message.answer(
                "✅ Ты уже зарегистрирован и активен в системе!\n\n"
                "💡 Используй /start для доступа к функциям бота."
            )
            return
        
        # Если заявка на рассмотрении
        access_token = response.get("access_token")
        if access_token:
            headers = {"Authorization": f"Bearer {access_token}"}
            app_response = await call_api("GET", "/moderation/my-application", headers=headers, silent_errors=[403])
            
            if app_response.get("status") == "pending":
                await callback.message.answer(
                    "⏳ Твоя заявка уже находится на рассмотрении!\n\n"
                    "Мы уведомим тебя, когда она будет одобрена.\n"
                    "Пока можешь просматривать задачи и рейтинг через /start."
                )
                return
        
        # Начинаем процесс регистрации
        await start_registration_flow(callback.message, state, user, auth_data)
        
    except Exception as e:
        logger.error(f"Error in callback_register_in_bot: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "register_accept")
async def callback_register_accept(callback: CallbackQuery, state: FSMContext):
    """Принятие соглашений и завершение обычной регистрации (через /register)"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Получаем данные из состояния
        data = await state.get_data()
        full_name = data.get("full_name")
        auth_data = data.get("registration_auth_data")
        
        if not full_name:
            await callback.message.answer(
                "❌ Ошибка: ФИО не найдено. Пожалуйста, начните регистрацию заново командой /register."
            )
            return
        
        if not auth_data:
            await callback.message.answer(
                "❌ Ошибка: данные авторизации не найдены. Пожалуйста, начните регистрацию заново командой /register."
            )
            return
        
        # Регистрируем пользователя через API
        from datetime import datetime
        
        register_response = await call_api("POST", "/registration/register", data={
            "telegram_auth": auth_data,
            "full_name": full_name,
            "personal_data_consent": {
                "consent": True,
                "date": datetime.utcnow().isoformat()
            },
            "user_agreement": {
                "accepted": True,
                "version": data.get("agreement_version", "1.0")
            }
        })
        
        if "error" in register_response:
            await callback.message.answer(
                f"❌ Ошибка регистрации: {register_response.get('error', 'Неизвестная ошибка')}\n\n"
                "Попробуйте позже или используйте команду /register."
            )
            return
        
        # Успешная регистрация
        access_token = register_response.get("access_token")
        await state.update_data(access_token=access_token)
        
        await callback.message.edit_text(
            "✅ <b>Регистрация успешна!</b>\n\n"
            "Ваша заявка отправлена на рассмотрение модераторам.\n\n"
            "🔔 Мы уведомим вас, когда заявка будет одобрена.\n\n"
            "Пока вы можете просматривать задачи и рейтинг.",
            parse_mode="HTML"
        )
        
        # Показываем кнопки для просмотра задач и рейтинга + автоматическое перенаправление на сайт
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Перейти на сайт", 
                    url=f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&registered=true"
                ),
            ],
            [
                InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="view_stats"),
            ],
        ])
        
        await callback.message.answer(
            "💡 <b>Что дальше?</b>\n\n"
            "Пока ваша заявка на рассмотрении, вы можете:\n"
            "• 🌐 Изучить сайт и посмотреть доступные функции\n"
            "• 👀 Просматривать доступные задачи\n"
            "• 🏆 Смотреть рейтинг участников\n"
            "• 📊 Изучать статистику системы\n\n"
            "🎯 <b>После одобрения заявки</b> вам станут доступны:\n"
            "• Взятие задач\n"
            "• Бронирование оборудования\n"
            "• Участие в рейтинге",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            registration_step=None,
            full_name=None,
            registration_auth_data=None,
            agreement_version=None
        )
        
    except Exception as e:
        logger.error(f"Error confirming registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "register_read")
async def callback_register_read(callback: CallbackQuery, state: FSMContext):
    """Просмотр соглашений перед обычной регистрацией"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Получаем соглашение через API
        agreement_response = await call_api("GET", "/registration/agreement")
        agreement_content = agreement_response.get("content", "")
        agreement_title = agreement_response.get("title", "Пользовательское соглашение")
        
        # Показываем краткую версию соглашения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принимаю и продолжаю", 
                    callback_data="register_accept"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить", 
                    callback_data="register_cancel"
                ),
            ],
        ])
        
        # Показываем первые 1000 символов соглашения
        content_preview = agreement_content[:1000] + "..." if len(agreement_content) > 1000 else agreement_content
        
        await callback.message.edit_text(
            f"📄 <b>{agreement_title}</b>\n\n"
            f"{content_preview}\n\n"
            f"💡 <b>Также вы даёте согласие на обработку персональных данных</b>\n\n"
            f"Нажмите «Принимаю и продолжаю» для завершения регистрации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error reading agreement: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "register_cancel")
async def callback_register_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена обычной регистрации"""
    try:
        await callback.answer()
        
        await callback.message.edit_text(
            "❌ <b>Регистрация отменена</b>\n\n"
            f"Ты можешь зарегистрироваться позже через команду /register или на сайте:\n"
            f"🔗 {settings.FRONTEND_URL}/register",
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            registration_step=None,
            full_name=None,
            registration_auth_data=None,
            agreement_version=None
        )
        
    except Exception as e:
        logger.error(f"Error cancelling registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


# Обработчик cancel_registration удалён - теперь используется register_cancel


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Команда /help - помощь (разная для личного чата и общего чата)"""
    # Проверяем, это группа/супергруппа или личный чат
    is_group = message.chat.type in ("group", "supergroup")
    
    if is_group:
        # Помощь для общего чата
        help_text = (
            "👋 <b>Добро пожаловать в общий чат PR-отдела BEST Москва!</b>\n\n"
            "💬 <b>Это наш командный чат</b>, где мы:\n"
            "• Обсуждаем задачи и проекты\n"
            "• Делимся идеями и опытом\n"
            "• Поддерживаем друг друга\n"
            "• Координируем работу\n\n"
            "📋 <b>Как устроен чат:</b>\n"
            "• <b>Открытые темы</b> (видны всем): Общий чат, Информация\n"
            "• <b>Закрытые темы</b> (только для участников задачи): создаются автоматически для каждой задачи\n\n"
            "🌐 <b>Веб-интерфейс:</b>\n"
            f"• <a href=\"{settings.FRONTEND_URL}\">Открыть сайт</a> - для работы с задачами, рейтингом и статистикой\n\n"
            "💡 <b>Для личных команд</b> (задачи, статистика, рейтинг) напиши боту в личные сообщения: @BESTPRSystemBot"
        )
    else:
        # Помощь для личного чата
        help_text = (
            "📖 <b>Доступные команды:</b>\n\n"
            "/start - авторизация и главное меню\n"
            "/register - регистрация в системе\n"
            "/tasks - список моих задач\n"
            "/stats - моя статистика\n"
            "/leaderboard - рейтинг участников\n"
            "/equipment - мои заявки на оборудование\n"
            "/notifications - уведомления\n"
            "/help - эта справка\n\n"
            "💡 <b>Также можно использовать веб-интерфейс:</b>\n"
            f"<a href=\"{settings.FRONTEND_URL}\">Открыть сайт</a>"
        )
    
    await message.answer(help_text, parse_mode="HTML")




# Убрали обработчик bestpr://auth, так как теперь QR-код содержит HTTPS ссылку на бота
# @router.message(F.text.startswith("bestpr://auth"))
async def handle_qr_auth_old(message: Message, state: FSMContext):
    """Обработка QR-кода авторизации"""
    try:
        user = message.from_user
        text = message.text
        
        # Парсим параметры из URL
        # Формат: bestpr://auth?token=TOKEN&telegram_id=ID&username=USERNAME&first_name=NAME
        if "token=" not in text:
            await message.answer(
                "❌ Неверный формат QR-кода.\n\n"
                "Пожалуйста, отсканируйте QR-код снова на сайте."
            )
            return
        
        # Извлекаем все параметры из URL
        params = {}
        parts = text.split("?")[1].split("&")
        for part in parts:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key] = value
        
        token = params.get("token", "").strip()
        
        if not token:
            await message.answer(
                "❌ Не удалось извлечь токен из QR-кода.\n\n"
                "Пожалуйста, отсканируйте QR-код снова."
            )
            return
        
        # Проверяем, есть ли данные пользователя в QR-коде (для упрощённой регистрации)
        qr_telegram_id = params.get("telegram_id")
        qr_username = params.get("username", "")
        qr_first_name = params.get("first_name", "")
        
        # Проверяем сессию через API
        check_response = await call_api("GET", f"/auth/qr/status/{token}")
        
        if "error" in check_response:
            await message.answer(
                "❌ Не удалось проверить QR-код.\n\n"
                "Возможно, сессия истекла. Попробуйте отсканировать QR-код снова на сайте."
            )
            return
        
        # Если сессия уже подтверждена
        if check_response.get("status") == "confirmed":
            await message.answer(
                "✅ Этот QR-код уже использован.\n\n"
                "Если вы хотите войти снова, откройте страницу входа на сайте и отсканируйте новый QR-код."
            )
            return
        
        # Если сессия истекла
        if check_response.get("status") == "expired":
            await message.answer(
                "⏰ QR-код истёк.\n\n"
                "Пожалуйста, откройте страницу входа на сайте и отсканируйте новый QR-код."
            )
            return
        
        # Если сессия в статусе pending, показываем подтверждение
        if check_response.get("status") == "pending":
            # Сохраняем токен в состояние
            await state.update_data(qr_token=token)
            
            # Формируем данные пользователя
            auth_data = {
                "id": user.id,
                "first_name": user.first_name or "User",
                "auth_date": int(message.date.timestamp()),
            }
            
            if user.last_name:
                auth_data["last_name"] = user.last_name
            if user.username:
                auth_data["username"] = user.username
            
            # Генерируем hash
            auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
            
            # Сохраняем данные для подтверждения
            await state.update_data(qr_auth_data=auth_data)
            
            # Проверяем, есть ли данные пользователя в QR-коде (для упрощённой регистрации)
            is_registration_qr = qr_telegram_id and str(user.id) == qr_telegram_id
            
            # Показываем подтверждение
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Подтвердить вход", callback_data=f"qr_confirm_{token}"),
                    InlineKeyboardButton(text="❌ Отменить", callback_data=f"qr_cancel_{token}"),
                ]
            ])
            
            if is_registration_qr:
                # Если это QR-код для регистрации, предлагаем зарегистрироваться
                keyboard.inline_keyboard.append([
                    InlineKeyboardButton(
                        text="📝 Зарегистрироваться", 
                        callback_data=f"qr_register_{token}"
                    ),
                ])
                
                await message.answer(
                    f"🔐 <b>Подтверждение входа на сайт</b>\n\n"
                    f"Вы отсканировали QR-код для регистрации.\n\n"
                    f"👤 <b>{user.first_name or 'Пользователь'}</b>\n"
                    f"🆔 ID: <code>{user.id}</code>\n\n"
                    f"💡 <b>Вы можете:</b>\n"
                    f"• ✅ Подтвердить вход (если уже зарегистрированы)\n"
                    f"• 📝 Зарегистрироваться (если ещё не зарегистрированы)\n\n"
                    f"⚠️ Если это не вы, нажмите «Отменить».",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Обычное подтверждение входа
                await message.answer(
                    f"🔐 <b>Подтверждение входа на сайт</b>\n\n"
                    f"Вы хотите войти в аккаунт:\n"
                    f"👤 <b>{user.first_name or 'Пользователь'}</b>\n"
                    f"🆔 ID: <code>{user.id}</code>\n\n"
                    f"📍 <b>Устройство:</b> {message.from_user.language_code or 'Unknown'}\n"
                    f"🕐 <b>Время:</b> {message.date.strftime('%H:%M:%S')}\n\n"
                    f"⚠️ Если это не вы, нажмите «Отменить».\n\n"
                    f"Подтвердите вход:",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            await message.answer(
                f"❌ Неизвестный статус QR-кода: {check_response.get('status')}\n\n"
                "Попробуйте отсканировать QR-код снова."
            )
            
    except Exception as e:
        logger.error(f"Error handling QR auth: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке QR-кода.\n\n"
            "Попробуйте позже или обратитесь к администратору."
        )


@router.callback_query(F.data.startswith("qr_confirm_"))
async def callback_qr_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение QR-кода авторизации"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Извлекаем токен из callback_data
        token = callback.data.replace("qr_confirm_", "")
        
        # Получаем данные из состояния
        data = await state.get_data()
        auth_data = data.get("qr_auth_data")
        
        if not auth_data:
            await callback.message.answer(
                "❌ Данные авторизации не найдены.\n\n"
                "Пожалуйста, отсканируйте QR-код снова."
            )
            return
        
        # Отправляем подтверждение на API
        confirm_data = {
            "session_token": token,
            "telegram_id": user.id,
            "first_name": auth_data.get("first_name", user.first_name or "User"),
            "last_name": auth_data.get("last_name"),
            "username": auth_data.get("username")
        }
        
        response = await call_api("POST", "/auth/qr/confirm", data=confirm_data)
        
        if "error" in response:
            await callback.message.answer(
                f"❌ Ошибка подтверждения: {response.get('error', 'Неизвестная ошибка')}\n\n"
                "Попробуйте отсканировать QR-код снова."
            )
            return
        
        # Проверяем, это регистрация или вход
        is_registration = response.get("is_registration", False)
        
        if is_registration:
            # Это регистрация - предлагаем перейти на страницу регистрации
            registration_url = (
                f"{settings.FRONTEND_URL}/register?"
                f"from=bot&"
                f"telegram_id={user.id}&"
                f"username={user.username or ''}&"
                f"first_name={user.first_name or ''}&"
                f"qr_token={token}"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Перейти к регистрации", 
                        url=registration_url
                    ),
                ],
            ])
            
            await callback.message.edit_text(
                "✅ <b>QR-код подтверждён!</b>\n\n"
                "Вы ещё не зарегистрированы. Нажмите кнопку ниже, чтобы перейти к регистрации.\n\n"
                "💡 <b>Преимущества регистрации через QR-код:</b>\n"
                "• ✅ Не нужно подтверждать Telegram ID\n"
                "• ✅ Данные уже заполнены\n"
                "• ✅ Просто согласитесь с условиями",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            # Это вход - пользователь уже зарегистрирован
            # Получаем access_token из ответа подтверждения
            access_token = response.get("access_token")
            
            # Сохраняем токен для последующих запросов
            await state.update_data(access_token=access_token)
            
            # Показываем уведомление (alert) поверх экрана
            await callback.answer(
                "✅ Сессия запущена на устройстве!",
                show_alert=True
            )
            
            # Получаем данные пользователя для краткой сводки
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await call_api("GET", "/auth/me", headers=headers)
            user_data = user_response.get("user", {}) if "error" not in user_response else {}
            
            # Формируем URL для возврата на сайт
            site_url = f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&logged_in=true"
            
            # Получаем статистику для сводки
            stats_response = await call_api("GET", "/gamification/stats", headers=headers)
            stats = stats_response if "error" not in stats_response else {}
            
            # Получаем активные задачи
            tasks_response = await call_api("GET", "/tasks?limit=3", headers=headers)
            active_tasks = tasks_response.get("items", [])[:3] if "error" not in tasks_response else []
            
            # Формируем краткую сводку
            summary_parts = []
            if stats.get("active_tasks", 0) > 0:
                summary_parts.append(f"📋 Активных задач: {stats.get('active_tasks', 0)}")
            if stats.get("points", 0) > 0:
                summary_parts.append(f"⭐ Баллов: {stats.get('points', 0)}")
            if stats.get("level", 1) > 1:
                summary_parts.append(f"🎯 Уровень: {stats.get('level', 1)}")
            
            summary_text = "\n".join(summary_parts) if summary_parts else "Добро пожаловать обратно!"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🌐 Вернуться на сайт",
                        url=site_url
                    ),
                ],
                [
                    InlineKeyboardButton(text="📋 Мои задачи", callback_data="my_tasks"),
                    InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
                ],
            ])
            
            # Отправляем сообщение с информацией и кнопкой
            await callback.message.answer(
                f"✅ <b>Сессия запущена на устройстве</b>\n\n"
                f"Вы успешно вошли в свой аккаунт на сайте.\n\n"
                f"📊 <b>Краткая сводка:</b>\n"
                f"{summary_text}\n\n"
                f"🔔 Важные уведомления и изменения будут приходить сюда в бот.\n\n"
                f"💡 <b>Как дела?</b> Всё идёт по плану? Если есть вопросы - пиши!",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Спустя небольшое время (через 2 секунды) отправляем приветственное окно с краткой сводкой
            import asyncio
            await asyncio.sleep(2)
            
            # Получаем информацию о ключевых изменениях, задачах, рейтинге
            # Получаем последние задачи
            recent_tasks_text = ""
            if active_tasks:
                recent_tasks_text = "\n\n📋 <b>Твои активные задачи:</b>\n"
                for i, task in enumerate(active_tasks[:3], 1):
                    recent_tasks_text += f"{i}. {task.get('title', 'Без названия')[:40]}...\n"
            
            # Формируем приветственное сообщение с краткой сводкой
            welcome_summary = (
                f"👋 <b>Привет, {user_data.get('full_name', user.first_name or 'друг')}!</b>\n\n"
                f"💡 <b>Краткая сводка:</b>\n"
                f"• 📊 Твоя статистика: {stats.get('points', 0)} баллов, уровень {stats.get('level', 1)}\n"
                f"• 📋 Активных задач: {stats.get('active_tasks', 0)}\n"
                f"• ✅ Выполнено: {stats.get('completed_tasks', 0)} задач\n"
                f"{recent_tasks_text}\n"
                f"💬 <b>Как дела?</b> Всё идёт по плану? Если есть вопросы - пиши!\n\n"
                f"🎯 <b>Помни:</b> ты важен для PR-отдела! Твоя работа помогает нам развиваться."
            )
            
            # Получаем ссылку на общий чат
            general_chat_link = None
            try:
                general_chat_response = await call_api("GET", "/telegram-chats/general", headers=headers)
                if "error" not in general_chat_response and general_chat_response.get("exists") and general_chat_response.get("invite_link"):
                    general_chat_link = general_chat_response.get("invite_link")
            except Exception as e:
                logger.warning(f"Could not get general chat link: {e}")
            
            keyboard_summary = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🌐 Открыть сайт",
                        url=site_url
                    ),
                ],
                [
                    InlineKeyboardButton(text="📋 Задачи", callback_data="my_tasks"),
                    InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
                ],
            ])
            
            # Добавляем кнопку на общий чат, если доступна
            if general_chat_link:
                keyboard_summary.inline_keyboard.append([
                    InlineKeyboardButton(
                        text="💬 Общий чат команды",
                        url=general_chat_link
                    ),
                ])
            
            keyboard_summary.inline_keyboard.append([
                InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats"),
            ])
            
            await callback.message.answer(
                welcome_summary,
                reply_markup=keyboard_summary,
                parse_mode="HTML"
            )
        
        # Очищаем состояние
        await state.update_data(qr_token=None, qr_auth_data=None)
        
    except Exception as e:
        logger.error(f"Error confirming QR auth: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("reminder_register_"))
async def callback_reminder_register(callback: CallbackQuery, state: FSMContext):
    """Регистрация из напоминания прямо в боте"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Извлекаем telegram_id из callback_data
        telegram_id_from_callback = callback.data.replace("reminder_register_", "")
        
        # Проверяем, что это тот же пользователь
        if str(user.id) != telegram_id_from_callback:
            await callback.message.answer(
                "❌ Ошибка: несоответствие пользователя. Попробуйте начать заново."
            )
            return
        
        # Проверяем, не зарегистрирован ли уже пользователь
        auth_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name or "",
            "username": user.username or "",
            "auth_date": int(callback.message.date.timestamp()) if callback.message.date else int(callback.message.edit_date.timestamp()) if callback.message.edit_date else 0,
        }
        
        auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
        
        # Проверяем авторизацию
        response = await call_api("POST", "/auth/telegram", data=auth_data)
        
        if "error" in response:
            await callback.message.answer(
                "❌ Ошибка авторизации. Попробуйте позже или обратитесь к администратору."
            )
            return
        
        user_data = response.get("user", {})
        
        # Если пользователь уже активен
        if user_data.get("is_active", False):
            await callback.message.answer(
                "✅ Ты уже зарегистрирован и активен в системе!\n\n"
                "💡 Используй /start для доступа к функциям бота."
            )
            return
        
        # Если заявка на рассмотрении
        access_token = response.get("access_token")
        if access_token:
            headers = {"Authorization": f"Bearer {access_token}"}
            app_response = await call_api("GET", "/moderation/my-application", headers=headers, silent_errors=[403])
            
            if app_response.get("status") == "pending":
                await callback.message.answer(
                    "⏳ Твоя заявка уже находится на рассмотрении!\n\n"
                    "Мы уведомим тебя, когда она будет одобрена.\n"
                    "Пока можешь просматривать задачи и рейтинг через /start."
                )
                return
        
        # Мотивирующее сообщение перед регистрацией
        await callback.message.edit_text(
            "🎯 <b>Отлично! Ты на правильном пути!</b>\n\n"
            "Осталось ещё чуть-чуть - всего пару минут, и ты станешь частью команды PR-отдела BEST Москва!\n\n"
            "💪 <b>Ты молодец, что решил присоединиться к нам!</b>\n\n"
            "📝 <b>Шаг 1:</b> Напиши своё полное ФИО (например: Иванов Иван Иванович)\n\n"
            "Напиши ФИО текстом:",
            parse_mode="HTML"
        )
        
        # Сохраняем состояние регистрации
        await state.update_data(
            registration_step="full_name",
            registration_from_reminder=True,
            registration_auth_data=auth_data
        )
        
    except Exception as e:
        logger.error(f"Error in reminder registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("qr_register_"))
async def callback_qr_register(callback: CallbackQuery, state: FSMContext):
    """Регистрация через QR-код прямо в боте (упрощённая)"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Извлекаем токен из callback_data
        token = callback.data.replace("qr_register_", "")
        
        # Получаем данные из состояния
        data = await state.get_data()
        auth_data = data.get("qr_auth_data")
        
        if not auth_data:
            await callback.message.answer(
                "❌ Данные авторизации не найдены.\n\n"
                "Пожалуйста, отсканируйте QR-код снова."
            )
            return
        
        # Проверяем, не зарегистрирован ли уже пользователь
        # Сначала подтверждаем QR-сессию, чтобы получить информацию о пользователе
        confirm_response = await call_api("POST", "/auth/qr/confirm", data={
            "session_token": token,
            "telegram_id": user.id,
            "first_name": user.first_name or "User",
            "last_name": user.last_name,
            "username": user.username
        })
        
        if "error" in confirm_response:
            await callback.message.answer(
                f"❌ Ошибка подтверждения QR-кода: {confirm_response.get('error', 'Неизвестная ошибка')}\n\n"
                "Попробуйте отсканировать QR-код снова."
            )
            return
        
        # Если пользователь уже существует (is_registration: False), это вход, а не регистрация
        if not confirm_response.get("is_registration", True):
            await callback.message.edit_text(
                "✅ <b>Вы уже зарегистрированы!</b>\n\n"
                "Используйте кнопку «Подтвердить вход» для входа на сайт.",
                parse_mode="HTML"
            )
            return
        
        # Мотивирующее сообщение перед регистрацией
        await callback.message.edit_text(
            "🎯 <b>Отлично! Ты на правильном пути!</b>\n\n"
            "Осталось ещё чуть-чуть - всего пару минут, и ты станешь частью команды PR-отдела BEST Москва!\n\n"
            "💪 <b>Ты молодец, что решил присоединиться к нам!</b>\n\n"
            "📝 <b>Шаг 1:</b> Напиши своё полное ФИО (например: Иванов Иван Иванович)\n\n"
            "Напиши ФИО текстом:",
            parse_mode="HTML"
        )
        
        # Сохраняем состояние регистрации
        await state.update_data(
            registration_step="full_name",
            qr_token=token,
            qr_auth_data=auth_data
        )
        
    except Exception as e:
        logger.error(f"Error in QR registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("reminder_register_accept_"))
async def callback_reminder_register_accept(callback: CallbackQuery, state: FSMContext):
    """Принятие соглашений и завершение регистрации из напоминания"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Получаем данные из состояния
        data = await state.get_data()
        full_name = data.get("full_name")
        auth_data = data.get("registration_auth_data")
        
        if not full_name:
            await callback.message.answer(
                "❌ Ошибка: ФИО не найдено. Пожалуйста, начните регистрацию заново."
            )
            return
        
        if not auth_data:
            await callback.message.answer(
                "❌ Ошибка: данные авторизации не найдены. Пожалуйста, начните регистрацию заново."
            )
            return
        
        # Регистрируем пользователя через API (обычная регистрация, не через QR)
        from datetime import datetime
        
        register_response = await call_api("POST", "/registration/register", data={
            "telegram_auth": auth_data,
            "full_name": full_name,
            "personal_data_consent": {
                "consent": True,
                "date": datetime.utcnow().isoformat()
            },
            "user_agreement": {
                "accepted": True,
                "version": data.get("agreement_version", "1.0")
            }
        })
        
        if "error" in register_response:
            await callback.message.answer(
                f"❌ Ошибка регистрации: {register_response.get('error', 'Неизвестная ошибка')}\n\n"
                "Попробуйте позже или используйте команду /register."
            )
            return
        
        # Успешная регистрация
        await callback.message.edit_text(
            "✅ <b>Регистрация успешна!</b>\n\n"
            "Ваша заявка отправлена на рассмотрение модераторам.\n\n"
            "🔔 Мы уведомим вас, когда заявка будет одобрена.\n\n"
            "Пока вы можете просматривать задачи и рейтинг.",
            parse_mode="HTML"
        )
        
        # Показываем кнопки для просмотра задач и рейтинга + автоматическое перенаправление на сайт
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Перейти на сайт", 
                    url=f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&registered=true"
                ),
            ],
            [
                InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="view_stats"),
            ],
        ])
        
        await callback.message.answer(
            "💡 <b>Что дальше?</b>\n\n"
            "Пока ваша заявка на рассмотрении, вы можете:\n"
            "• 🌐 Изучить сайт и посмотреть доступные функции\n"
            "• 👀 Просматривать доступные задачи\n"
            "• 🏆 Смотреть рейтинг участников\n"
            "• 📊 Изучать статистику системы\n\n"
            "🎯 <b>После одобрения заявки</b> вам станут доступны:\n"
            "• Взятие задач\n"
            "• Бронирование оборудования\n"
            "• Участие в рейтинге",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            registration_step=None,
            full_name=None,
            registration_from_reminder=None,
            registration_auth_data=None,
            agreement_version=None
        )
        
    except Exception as e:
        logger.error(f"Error confirming reminder registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("reminder_register_read_"))
async def callback_reminder_register_read(callback: CallbackQuery, state: FSMContext):
    """Просмотр соглашений перед регистрацией из напоминания"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Получаем соглашение через API
        agreement_response = await call_api("GET", "/registration/agreement")
        agreement_content = agreement_response.get("content", "")
        agreement_title = agreement_response.get("title", "Пользовательское соглашение")
        
        # Показываем краткую версию соглашения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принимаю и продолжаю", 
                    callback_data=f"reminder_register_accept_{user.id}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отменить", 
                    callback_data=f"reminder_register_cancel_{user.id}"
                ),
            ],
        ])
        
        # Показываем первые 1000 символов соглашения
        content_preview = agreement_content[:1000] + "..." if len(agreement_content) > 1000 else agreement_content
        
        await callback.message.edit_text(
            f"📄 <b>{agreement_title}</b>\n\n"
            f"{content_preview}\n\n"
            f"💡 <b>Также вы даёте согласие на обработку персональных данных</b>\n\n"
            f"Нажмите «Принимаю и продолжаю» для завершения регистрации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error reading agreement from reminder: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("reminder_register_cancel_"))
async def callback_reminder_register_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена регистрации из напоминания"""
    try:
        await callback.answer()
        
        await callback.message.edit_text(
            "❌ <b>Регистрация отменена</b>\n\n"
            f"Ты можешь зарегистрироваться позже через команду /register или на сайте:\n"
            f"🔗 {settings.FRONTEND_URL}/register\n\n"
            "💡 Мы можем напомнить тебе о регистрации позже!",
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            registration_step=None,
            full_name=None,
            registration_from_reminder=None,
            registration_auth_data=None,
            agreement_version=None
        )
        
    except Exception as e:
        logger.error(f"Error cancelling reminder registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("qr_register_accept_"))
async def callback_qr_register_accept(callback: CallbackQuery, state: FSMContext):
    """Принятие соглашений и завершение регистрации через QR"""
    try:
        await callback.answer()
        user = callback.from_user
        
        # Извлекаем токен из callback_data
        token = callback.data.replace("qr_register_accept_", "")
        
        # Получаем данные из состояния
        data = await state.get_data()
        full_name = data.get("full_name")
        
        if not full_name:
            await callback.message.answer(
                "❌ Ошибка: ФИО не найдено. Пожалуйста, начните регистрацию заново."
            )
            return
        
        # Регистрируем пользователя через API с ФИО
        register_response = await call_api("POST", "/registration/register-from-bot", data={
            "qr_token": token,
            "full_name": full_name
        })
        
        if "error" in register_response:
            await callback.message.answer(
                f"❌ Ошибка регистрации: {register_response.get('error', 'Неизвестная ошибка')}\n\n"
                "Попробуйте отсканировать QR-код снова."
            )
            return
        
        # Успешная регистрация
        await callback.message.edit_text(
            "✅ <b>Регистрация успешна!</b>\n\n"
            "Ваша заявка отправлена на рассмотрение модераторам.\n\n"
            "🔔 Мы уведомим вас, когда заявка будет одобрена.\n\n"
            "Пока вы можете просматривать задачи и рейтинг.",
            parse_mode="HTML"
        )
        
        # Показываем кнопки для просмотра задач и рейтинга + автоматическое перенаправление на сайт
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Перейти на сайт", 
                    url=f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&registered=true"
                ),
            ],
            [
                InlineKeyboardButton(text="📋 Задачи", callback_data="view_tasks"),
                InlineKeyboardButton(text="🏆 Рейтинг", callback_data="view_leaderboard"),
            ],
            [
                InlineKeyboardButton(text="📊 Статистика", callback_data="view_stats"),
            ],
        ])
        
        await callback.message.answer(
            "💡 <b>Что дальше?</b>\n\n"
            "Пока ваша заявка на рассмотрении, вы можете:\n"
            "• 🌐 Изучить сайт и посмотреть доступные функции\n"
            "• 👀 Просматривать доступные задачи\n"
            "• 🏆 Смотреть рейтинг участников\n"
            "• 📊 Изучать статистику системы\n\n"
            "🎯 <b>После одобрения заявки</b> вам станут доступны:\n"
            "• Взятие задач\n"
            "• Бронирование оборудования\n"
            "• Участие в рейтинге",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            qr_token=None, 
            qr_auth_data=None,
            registration_step=None,
            full_name=None
        )
        
    except Exception as e:
        logger.error(f"Error confirming QR registration: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("qr_register_read_"))
async def callback_qr_register_read(callback: CallbackQuery, state: FSMContext):
    """Просмотр соглашений перед регистрацией"""
    try:
        await callback.answer()
        
        # Получаем соглашение через API
        agreement_response = await call_api("GET", "/registration/agreement")
        agreement_content = agreement_response.get("content", "")
        agreement_title = agreement_response.get("title", "Пользовательское соглашение")
        
        # Показываем краткую версию соглашения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Принимаю и продолжаю", 
                    callback_data=f"qr_register_accept_{callback.data.replace('qr_register_read_', '')}"
                ),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"qr_cancel_{callback.data.replace('qr_register_read_', '')}"),
            ],
        ])
        
        # Показываем первые 1000 символов соглашения
        content_preview = agreement_content[:1000] + "..." if len(agreement_content) > 1000 else agreement_content
        
        await callback.message.edit_text(
            f"📄 <b>{agreement_title}</b>\n\n"
            f"{content_preview}\n\n"
            f"💡 <b>Также вы даёте согласие на обработку персональных данных</b>\n\n"
            f"Нажмите «Принимаю и продолжаю» для завершения регистрации:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error reading agreement: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("qr_cancel_"))
async def callback_qr_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена QR-кода авторизации"""
    try:
        await callback.answer()
        
        # Извлекаем токен из callback_data
        token = callback.data.replace("qr_cancel_", "")
        
        # Отмечаем сессию как отменённую через API (если нужно)
        # Пока просто отменяем локально
        
        await callback.message.edit_text(
            "❌ <b>Вход отменён</b>\n\n"
            "Если вы хотите войти, откройте страницу входа на сайте и отсканируйте QR-код снова.\n\n"
            "💡 <b>Почему это важно?</b>\n"
            "Подтверждение входа помогает защитить ваш аккаунт от несанкционированного доступа.",
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(
            qr_token=None, 
            qr_auth_data=None,
            registration_step=None,
            full_name=None
        )
        
    except Exception as e:
        logger.error(f"Error cancelling QR auth: {e}")


@router.callback_query(F.data == "onboarding_start")
async def callback_onboarding_start(callback: CallbackQuery, state: FSMContext):
    """Начало онбординга - система вопросов для новичков"""
    try:
        await callback.answer()
        user = callback.from_user
        
        await callback.message.edit_text(
            f"💬 <b>Расскажи о себе!</b>\n\n"
            f"Мы хотим узнать тебя получше, чтобы предложить самые интересные задачи.\n\n"
            f"📝 <b>Вопрос 1/3:</b> Какой у тебя опыт в PR, SMM, дизайне или видеопроизводстве?\n\n"
            f"Напиши свой ответ текстом (можно кратко или подробно).",
            parse_mode="HTML"
        )
        
        # Сохраняем состояние онбординга
        await state.update_data(onboarding_step="experience")
        
    except Exception as e:
        logger.error(f"Error in onboarding_start: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "ask_question")
async def callback_ask_question(callback: CallbackQuery, state: FSMContext):
    """Задать вопрос админу/координаторам"""
    try:
        await callback.answer()
        
        await callback.message.edit_text(
            "❓ <b>Задать вопрос</b>\n\n"
            "Ты можешь задать вопрос:\n"
            "• VP4PR (главе PR-отдела) - @bfm5451\n"
            "• Координаторам через поддержку на сайте\n\n"
            "Или напиши свой вопрос здесь, и мы переадресуем его нужному человеку.\n\n"
            "Напиши свой вопрос:",
            parse_mode="HTML"
        )
        
        await state.update_data(asking_question=True)
        
    except Exception as e:
        logger.error(f"Error in ask_question: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.message(F.text)
async def handle_text_message(message: Message, state: FSMContext):
    """Обработка текстовых сообщений (онбординг, вопросы и т.д.)"""
    # Если это группа/супергруппа и сообщение не начинается с команды - игнорируем
    is_group = message.chat.type in ("group", "supergroup")
    if is_group and not message.text.startswith("/"):
        # В группах обрабатываем только команды, обычные сообщения игнорируем
        return
    
    user = message.from_user
    text = message.text
    
    # Проверяем состояние (онбординг, регистрация, вопросы)
    data = await state.get_data()
    onboarding_step = data.get("onboarding_step")
    asking_question = data.get("asking_question")
    registration_step = data.get("registration_step")
    
    if registration_step:
        # Пользователь проходит регистрацию
        if registration_step == "full_name":
            # Сохраняем ФИО и запрашиваем согласия
            full_name = text.strip()
            
            if len(full_name) < 3:
                await message.answer(
                    "❌ ФИО слишком короткое. Пожалуйста, введи полное ФИО (например: Иванов Иван Иванович)."
                )
                return
            
            # Сохраняем ФИО в состоянии
            await state.update_data(full_name=full_name, registration_step="consents")
            
            # Проверяем, откуда регистрация (QR или напоминание)
            qr_token = data.get("qr_token")
            from_reminder = data.get("registration_from_reminder", False)
            
            # Получаем соглашение через API
            agreement_response = await call_api("GET", "/registration/agreement")
            agreement_version = agreement_response.get("version", "1.0")
            
            # Определяем callback_data для кнопок
            if from_reminder:
                # Регистрация из напоминания
                accept_callback = f"reminder_register_accept_{user.id}"
                read_callback = f"reminder_register_read_{user.id}"
                cancel_callback = f"reminder_register_cancel_{user.id}"
            elif qr_token:
                # Регистрация через QR
                accept_callback = f"qr_register_accept_{qr_token}"
                read_callback = f"qr_register_read_{qr_token}"
                cancel_callback = f"qr_cancel_{qr_token}"
            else:
                # Обычная регистрация (через /register)
                accept_callback = "register_accept"
                read_callback = "register_read"
                cancel_callback = "register_cancel"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Принимаю соглашения", 
                        callback_data=accept_callback
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📄 Прочитать соглашения", 
                        callback_data=read_callback
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="❌ Отменить", 
                        callback_data=cancel_callback
                    ),
                ],
            ])
            
            await message.answer(
                f"✅ <b>ФИО сохранено:</b> {full_name}\n\n"
                f"📝 <b>Шаг 2:</b> Примите соглашения\n\n"
                f"Для завершения регистрации необходимо:\n"
                f"• ✅ Принять пользовательское соглашение\n"
                f"• ✅ Дать согласие на обработку персональных данных\n\n"
                f"Нажмите «Принимаю соглашения» для продолжения:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            await state.update_data(agreement_version=agreement_version)
            return
    
    if onboarding_step:
        # Пользователь отвечает на вопросы онбординга
        if onboarding_step == "experience":
            # Сохраняем ответ об опыте
            await call_api("POST", "/onboarding/response", data={
                "telegram_id": str(user.id),
                "experience": text,
                "from_website": data.get("from_website", False),
                "from_qr": data.get("from_qr", False)
            })
            
            await message.answer(
                "✅ Спасибо! Записал.\n\n"
                "📝 <b>Вопрос 2/3:</b> Какие у тебя цели? Что ты хочешь получить от участия в PR-отделе?\n\n"
                "Напиши свой ответ:",
                parse_mode="HTML"
            )
            
            await state.update_data(onboarding_step="goals")
            
        elif onboarding_step == "goals":
            # Сохраняем ответ о целях
            await call_api("POST", "/onboarding/response", data={
                "telegram_id": str(user.id),
                "goals": text
            })
            
            await message.answer(
                "✅ Отлично!\n\n"
                "📝 <b>Вопрос 3/3:</b> Что тебя мотивирует присоединиться к PR-отделу?\n\n"
                "Напиши свой ответ:",
                parse_mode="HTML"
            )
            
            await state.update_data(onboarding_step="motivation")
            
        elif onboarding_step == "motivation":
            # Сохраняем ответ о мотивации и завершаем онбординг
            await call_api("POST", "/onboarding/response", data={
                "telegram_id": str(user.id),
                "motivation": text
            })
            
            await message.answer(
                "🎉 <b>Спасибо за ответы!</b>\n\n"
                "Мы учтём твою информацию при подборе задач.\n\n"
                "💡 <b>Что дальше?</b>\n"
                "• 🌐 Изучи сайт и посмотри доступные задачи\n"
                "• 📝 Зарегистрируйся, когда будешь готов\n"
                "• ❓ Если есть вопросы - пиши нам!\n\n"
                f"🔗 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>",
                parse_mode="HTML"
            )
            
            # Очищаем состояние онбординга
            await state.update_data(onboarding_step=None)
            
        return
    
    elif asking_question:
        # Пользователь задаёт вопрос
        # TODO: Отправить вопрос админу/координаторам
        await message.answer(
            "✅ Спасибо за вопрос! Мы передадим его координаторам.\n\n"
            "Обычно мы отвечаем в течение 24 часов.\n\n"
            "Также ты можешь написать напрямую:\n"
            "• VP4PR - @bfm5451",
            parse_mode="HTML"
        )
        
        # Очищаем состояние
        await state.update_data(asking_question=False)
        
        return
    
    # Если это не онбординг и не вопрос, обрабатываем как неизвестную команду
    # Но только в личном чате, в группах мы уже вернулись выше
    if not is_group:
        await message.answer(
            "❓ Неизвестная команда. Используйте /help для списка доступных команд."
        )


@router.message()
async def handle_unknown(message: Message):
    """Обработка неизвестных сообщений (не текст)"""
    # В группах игнорируем неизвестные сообщения (не команды)
    is_group = message.chat.type in ("group", "supergroup")
    if is_group:
        return
    
    # В личном чате отвечаем
    await message.answer(
        "❓ Неизвестная команда. Используйте /help для списка доступных команд."
    )
