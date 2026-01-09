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
                f"📝 <b>Как зарегистрироваться?</b>\n"
                f"1. Перейди на сайт по ссылке ниже\n"
                f"2. Отсканируй QR-код для входа\n"
                f"3. Заполни форму регистрации\n"
                f"4. Дождись одобрения заявки координатором\n\n"
                f"💡 После регистрации ты сможешь брать задачи, бронировать оборудование и участвовать в рейтинге!"
            )
            
            keyboard.inline_keyboard = [
                [
                    InlineKeyboardButton(
                        text="🌐 Перейти на сайт для регистрации", 
                        url=f"{settings.FRONTEND_URL}/login?from=bot&telegram_id={user.id}&username={user.username or ''}&first_name={user.first_name or ''}&auto_register=true"
                    ),
                ],
                [
                    InlineKeyboardButton(text="📋 Посмотреть задачи", callback_data="view_tasks"),
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
        
        if "error" in response:
            await callback.answer("❌ Ошибка при загрузке задач. Попробуйте позже.", show_alert=True)
            return
        
        tasks = response.get("items", [])
        
        if not tasks or len(tasks) == 0:
            # Если задач нет, показываем информативное сообщение
            await callback.message.answer(
                "📋 <b>Доступные задачи</b>\n\n"
                "🔍 Пока нет открытых задач.\n\n"
                "💡 <b>Что делать?</b>\n"
                "• Зарегистрируйся, чтобы получать уведомления о новых задачах\n"
                "• Следи за обновлениями на сайте\n\n"
                f"🌐 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>",
                parse_mode="HTML"
            )
            return
        
        text = "📋 <b>Доступные задачи:</b>\n\n"
        
        for i, task in enumerate(tasks[:5], 1):
            task_type = task.get('type', 'unknown')
            type_emoji = {
                'smm': '📱',
                'design': '🎨',
                'channel': '🎬',
                'prfr': '🤝'
            }.get(task_type, '📋')
            
            priority = task.get('priority', 'medium')
            priority_emoji = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🟢'
            }.get(priority, '⚪')
            
            due_date = task.get('due_date_relative', 'не указан')
            
            text += (
                f"{i}. {type_emoji} <b>{task.get('title', 'Без названия')}</b>\n"
                f"   {priority_emoji} Приоритет: {priority}\n"
                f"   📅 Дедлайн: {due_date}\n\n"
            )
        
        if response.get("total", 0) > 5:
            text += f"📊 <i>Показано 5 из {response.get('total', 0)} задач</i>\n\n"
        
        text += (
            "💡 <b>Для взятия задачи и оборудования BEST Channel</b> зарегистрируйся:\n"
            f"🔗 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>"
        )
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_view_tasks: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "view_leaderboard")
async def callback_view_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Просмотр рейтинга (публичный) - ТОП участников"""
    try:
        await callback.answer()  # Сначала отвечаем на callback
        response = await call_api("GET", "/public/leaderboard?limit=10")
        
        if "error" in response:
            await callback.answer("❌ Ошибка при загрузке рейтинга. Попробуйте позже.", show_alert=True)
            return
        
        # API возвращает список напрямую, не dict с items
        leaderboard = response if isinstance(response, list) else []
        
        if not leaderboard or len(leaderboard) == 0:
            await callback.message.answer(
                "🏆 <b>ТОП участников</b>\n\n"
                "📊 Рейтинг пока пуст.\n\n"
                "💡 <b>Стань первым!</b>\n"
                "Зарегистрируйся и начни выполнять задачи, чтобы попасть в рейтинг.\n\n"
                f"🌐 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>",
                parse_mode="HTML"
            )
            return
        
        text = "🏆 <b>ТОП-10 участников:</b>\n\n"
        medals = ["🥇", "🥈", "🥉"]
        
        for i, user in enumerate(leaderboard[:10], 1):
            if i <= 3:
                medal = medals[i-1]
            else:
                medal = f"{i}."
            
            name = user.get('name') or user.get('full_name', 'Unknown')
            points = user.get('points', 0)
            level = user.get('level', 1)
            completed = user.get('completed_tasks', 0)
            
            text += (
                f"{medal} <b>{name}</b>\n"
                f"   ⭐ {points} баллов | "
                f"Уровень {level} | "
                f"✅ {completed} задач\n\n"
            )
        
        text += (
            "💡 <b>Хочешь попасть в рейтинг?</b>\n"
            "Зарегистрируйся и начни выполнять задачи!\n\n"
            f"🌐 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>"
        )
        
        await callback.message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_view_leaderboard: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "view_stats")
async def callback_view_stats(callback: CallbackQuery, state: FSMContext):
    """Просмотр статистики системы (публичный)"""
    try:
        await callback.answer()  # Сначала отвечаем на callback
        response = await call_api("GET", "/public/stats")
        
        if "error" in response:
            await callback.answer("❌ Ошибка при загрузке статистики. Попробуйте позже.", show_alert=True)
            return
        
        stats = response
        text = (
            f"📊 <b>Статистика системы:</b>\n\n"
            f"👥 Участников: {stats.get('participants_count', stats.get('total_users', 0))}\n"
            f"📋 Всего задач: {stats.get('total_tasks', 0)}\n"
            f"✅ Выполнено: {stats.get('completed_tasks', 0)}\n"
            f"⚙️ В работе: {stats.get('active_tasks', 0)}\n"
            f"⭐ Всего баллов: {stats.get('total_points', 0)}\n"
            f"📈 Средний рейтинг: {stats.get('average_points', 0)} баллов\n\n"
            f"💡 <b>Присоединяйся к команде!</b>\n"
            f"🌐 <a href=\"{settings.FRONTEND_URL}\">Перейти на сайт</a>"
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
    """Меню работы с оборудованием - улучшенный UI"""
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
        
        # Удаляем предыдущее сообщение с меню (если есть), чтобы не было нагромождения
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Получаем мои заявки для отображения в меню
        requests_response = await call_api("GET", "/equipment/requests", headers=headers)
        requests = requests_response if isinstance(requests_response, list) else []
        pending_count = len([r for r in requests if r.get("status") == "pending"])
        
        # Создаём меню с кнопками
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Подать заявку",
                    callback_data="equipment_new_request"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=f"📋 Мои заявки{f' ({len(requests)})' if requests else ''}",
                    callback_data="equipment_my_requests"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📦 Доступное оборудование",
                    callback_data="equipment_available_list"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="main_menu"
                ),
            ],
        ])
        
        text = (
            f"📦 <b>Оборудование BEST Channel</b>\n\n"
            f"💡 <b>Что можно сделать:</b>\n"
            f"• 📝 Подать заявку на оборудование\n"
            f"• 📋 Посмотреть свои заявки"
        )
        
        if pending_count > 0:
            text += f"\n   ⏳ На рассмотрении: {pending_count}"
        
        text += (
            f"\n• 📦 Посмотреть доступное оборудование\n\n"
            f"💬 <b>Совет:</b> При взятии задачи типа Channel с возможностью получения оборудования, система автоматически предложит его."
        )
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
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
    """Команда /equipment - работа с оборудованием (улучшенный UI)"""
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
    pending_count = len([r for r in requests if r.get("status") == "pending"])
    
    # Создаём меню с кнопками
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Подать заявку",
                callback_data="equipment_new_request"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"📋 Мои заявки{f' ({len(requests)})' if requests else ''}",
                callback_data="equipment_my_requests"
            ),
        ],
        [
            InlineKeyboardButton(
                text="📦 Доступное оборудование",
                callback_data="equipment_available_list"
            ),
        ],
    ])
    
    text = (
        f"📦 <b>Оборудование BEST Channel</b>\n\n"
        f"💡 <b>Что можно сделать:</b>\n"
        f"• 📝 Подать заявку на оборудование\n"
        f"• 📋 Посмотреть свои заявки"
    )
    
    if pending_count > 0:
        text += f"\n   ⏳ На рассмотрении: {pending_count}"
    
    text += (
        f"\n• 📦 Посмотреть доступное оборудование\n\n"
        f"💬 <b>Совет:</b> При взятии задачи типа Channel с возможностью получения оборудования, система автоматически предложит его."
    )
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")


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
        from datetime import datetime, timezone
        
        # Обновляем auth_data с полным именем пользователя
        # Разбиваем full_name на first_name и last_name для совместимости
        name_parts = full_name.split(maxsplit=1)
        if len(name_parts) >= 2:
            auth_data["first_name"] = name_parts[0]
            auth_data["last_name"] = name_parts[1]
        else:
            auth_data["first_name"] = full_name
            auth_data["last_name"] = ""
        
        # Перегенерируем hash с обновлёнными данными
        auth_data["hash"] = generate_telegram_hash(auth_data, settings.TELEGRAM_BOT_TOKEN)
        
        # Получаем версию соглашения
        agreement_response = await call_api("GET", "/registration/agreement")
        agreement_version = agreement_response.get("version", "1.0")
        
        register_response = await call_api("POST", "/registration/register", data={
            "telegram_auth": auth_data,
            "personal_data_consent": {
                "consent": True,
                "consent_date": datetime.now(timezone.utc).isoformat()
            },
            "user_agreement": {
                "accepted": True,
                "version": agreement_version
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
            # Это регистрация - НЕ говорим что сессия запущена, предлагаем зарегистрироваться
            # Сохраняем qr_token для последующей регистрации
            await state.update_data(qr_token=token)
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📝 Зарегистрироваться в боте", 
                        callback_data=f"qr_register_{token}"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🌐 Зарегистрироваться на сайте", 
                        url=f"{settings.FRONTEND_URL}/register?from=bot&telegram_id={user.id}&qr_token={token}"
                    ),
                ],
            ])
            
            await callback.message.edit_text(
                "✅ <b>QR-код подтверждён!</b>\n\n"
                "🔐 <b>Вы ещё не зарегистрированы в системе.</b>\n\n"
                "💡 <b>Для продолжения необходимо зарегистрироваться:</b>\n"
                "• 📝 Нажмите «Зарегистрироваться в боте» для быстрой регистрации\n"
                "• 🌐 Или перейдите на сайт для регистрации через веб-интерфейс\n\n"
                "🎯 <b>После регистрации</b> вы сможете:\n"
                "• Брать задачи по SMM, дизайну и видеопроизводству\n"
                "• Бронировать оборудование BEST Channel\n"
                "• Участвовать в рейтинге и зарабатывать баллы",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return  # ВАЖНО: не продолжаем дальше, не отправляем сообщение о "сессии запущена"
        else:
            # Это вход - пользователь уже зарегистрирован
            # Получаем access_token из ответа подтверждения
            access_token = response.get("access_token")
            
            # Сохраняем токен для последующих запросов
            await state.update_data(access_token=access_token)
            
            # Удаляем сообщение с подтверждением входа
            try:
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Failed to delete confirmation message: {e}")
            
            # Получаем данные пользователя для краткой сводки
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await call_api("GET", "/auth/me", headers=headers)
            user_data = user_response.get("user", {}) if "error" not in user_response else {}
            
            # Формируем URL для возврата на сайт (без access_token в URL - фронтенд получит через polling)
            site_url = f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&logged_in=true"
            
            # Получаем статистику для сводки
            stats_response = await call_api("GET", "/gamification/stats", headers=headers)
            stats = stats_response if "error" not in stats_response else {}
            
            # Получаем активные задачи
            tasks_response = await call_api("GET", "/tasks?limit=3", headers=headers)
            active_tasks = tasks_response.get("items", [])[:3] if "error" not in tasks_response else []
            
            # Формируем краткую сводку
            recent_tasks_text = ""
            if active_tasks:
                recent_tasks_text = "\n📋 <b>Твои активные задачи:</b>\n"
                for i, task in enumerate(active_tasks[:3], 1):
                    recent_tasks_text += f"{i}. {task.get('title', 'Без названия')[:40]}...\n"
            
            # Формируем приветственное сообщение с краткой сводкой (одно сообщение вместо двух)
            welcome_summary = (
                f"👋 <b>Привет, {user_data.get('full_name', user.first_name or 'друг')}!</b>\n\n"
                f"✅ Сессия успешно запущена на устройстве.\n\n"
                f"💡 <b>Краткая сводка:</b>\n"
            )
            
            if stats.get("active_tasks", 0) > 0:
                welcome_summary += f"• 📋 Активных задач: {stats.get('active_tasks', 0)}\n"
            if stats.get("points", 0) > 0:
                welcome_summary += f"• ⭐ Баллов: {stats.get('points', 0)}\n"
            if stats.get("level", 1) > 1:
                welcome_summary += f"• 🎯 Уровень: {stats.get('level', 1)}\n"
            if stats.get("completed_tasks", 0) > 0:
                welcome_summary += f"• ✅ Выполнено: {stats.get('completed_tasks', 0)} задач\n"
            
            welcome_summary += f"{recent_tasks_text}\n"
            welcome_summary += (
                f"🔔 Важные уведомления и изменения будут приходить сюда в бот.\n\n"
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
            
            # Отправляем одно приветственное сообщение вместо двух
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
        access_token = register_response.get("access_token")
        if access_token:
            # Сохраняем токен для последующих запросов
            await state.update_data(access_token=access_token)
        
        await callback.message.edit_text(
            "✅ <b>Регистрация успешна!</b>\n\n"
            "Ваша заявка отправлена на рассмотрение модераторам.\n\n"
            "🔔 Мы уведомим вас, когда заявка будет одобрена.\n\n"
            "💡 <b>Пока ваша заявка на рассмотрении:</b>\n"
            "• Вы можете просматривать задачи и рейтинг\n"
            "• Изучать сайт и доступные функции\n\n"
            "🎯 <b>После одобрения заявки</b> вам станут доступны:\n"
            "• Взятие задач\n"
            "• Бронирование оборудования\n"
            "• Участие в рейтинге",
            parse_mode="HTML"
        )
        
        # Показываем кнопки для просмотра задач и рейтинга + автоматическое перенаправление на сайт
        # Если есть access_token, пользователь может войти на сайт автоматически
        site_url = f"{settings.FRONTEND_URL}?from=bot&telegram_id={user.id}&registered=true"
        if access_token:
            # Добавляем токен в URL для автоматического входа (временное решение)
            # В идеале фронтенд должен получить токен через polling статуса QR-сессии
            site_url += f"&token={access_token}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🌐 Перейти на сайт", 
                    url=site_url
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
            "Нажмите «Перейти на сайт» для автоматического входа и изучения системы.",
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


# ========== FSM для создания задач ==========
from bot.states import TaskCreationStates, EquipmentRequestStates
from app.models.task import TaskType, TaskPriority
from datetime import datetime, timedelta, timezone
from aiogram import F
from aiogram.types import ContentType


@router.message(Command("create_task"))
async def cmd_create_task(message: Message, state: FSMContext):
    """Команда /create_task - создание новой задачи (только для координаторов)"""
    user = message.from_user
    
    # Проверяем авторизацию
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await message.answer(
            "❌ Вы не авторизованы. Используйте /start для авторизации."
        )
        return
    
    # Проверяем права доступа (только координаторы и VP4PR)
    headers = {"Authorization": f"Bearer {access_token}"}
    user_response = await call_api("GET", "/auth/me", headers=headers)
    
    if "error" in user_response:
        await message.answer(
            "❌ Ошибка проверки прав доступа. Попробуйте позже."
        )
        return
    
    user_data = user_response.get("user", {})
    user_role = user_data.get("role")
    
    from app.models.user import UserRole
    allowed_roles = [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]
    
    if user_role not in [r.value for r in allowed_roles]:
        await message.answer(
            "❌ У вас нет прав для создания задач.\n\n"
            "Создавать задачи могут только координаторы и VP4PR."
        )
        return
    
    # Начинаем процесс создания задачи
    await message.answer(
        "📝 <b>Создание новой задачи</b>\n\n"
        "Давай создадим задачу пошагово! Это займёт всего пару минут.\n\n"
        "📋 <b>Шаг 1 из 7:</b> Введи название задачи\n\n"
        "Напиши название задачи текстом:",
        parse_mode="HTML"
    )
    
    # Устанавливаем состояние
    await state.set_state(TaskCreationStates.waiting_for_title)
    await state.update_data(
        task_creation_step=1,
        task_files=[]  # Список для хранения файлов
    )


@router.message(TaskCreationStates.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    """Обработка названия задачи"""
    title = message.text.strip()
    
    if len(title) < 3:
        await message.answer(
            "❌ Название слишком короткое. Пожалуйста, введи название задачи (минимум 3 символа):"
        )
        return
    
    if len(title) > 200:
        await message.answer(
            "❌ Название слишком длинное. Пожалуйста, введи название задачи (максимум 200 символов):"
        )
        return
    
    # Сохраняем название
    await state.update_data(task_title=title, task_creation_step=2)
    
    # Переходим к выбору типа задачи
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📢 SMM", callback_data="task_type_smm"),
            InlineKeyboardButton(text="🎨 Design", callback_data="task_type_design"),
        ],
        [
            InlineKeyboardButton(text="📹 Channel", callback_data="task_type_channel"),
            InlineKeyboardButton(text="📣 PR-FR", callback_data="task_type_prfr"),
        ],
    ])
    
    await message.answer(
        f"✅ Название сохранено: <b>{title}</b>\n\n"
        f"📋 <b>Шаг 2 из 7:</b> Выбери тип задачи\n\n"
        f"Нажми на кнопку с нужным типом:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_type)


@router.callback_query(F.data.startswith("task_type_"))
async def process_task_type(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора типа задачи"""
    await callback.answer()
    
    task_type_str = callback.data.replace("task_type_", "")
    
    # Маппинг типов
    type_map = {
        "smm": TaskType.SMM,
        "design": TaskType.DESIGN,
        "channel": TaskType.CHANNEL,
        "prfr": TaskType.PRFR,
    }
    
    task_type = type_map.get(task_type_str)
    if not task_type:
        await callback.message.answer("❌ Неверный тип задачи. Попробуйте ещё раз.")
        return
    
    # Сохраняем тип
    await state.update_data(task_type=task_type.value, task_creation_step=3)
    
    type_names = {
        "smm": "SMM",
        "design": "Design",
        "channel": "Channel",
        "prfr": "PR-FR",
    }
    
    await callback.message.edit_text(
        f"✅ Тип задачи: <b>{type_names[task_type_str]}</b>\n\n"
        f"📋 <b>Шаг 3 из 7:</b> Введи описание задачи\n\n"
        f"Опиши задачу подробно (что нужно сделать, какие требования, формат результата и т.д.):\n\n"
        f"💡 <i>Можно написать подробно, это поможет исполнителям лучше понять задачу.</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_description)


@router.message(TaskCreationStates.waiting_for_description)
async def process_task_description(message: Message, state: FSMContext):
    """Обработка описания задачи"""
    description = message.text.strip()
    
    if len(description) < 10:
        await message.answer(
            "❌ Описание слишком короткое. Пожалуйста, опиши задачу подробнее (минимум 10 символов):"
        )
        return
    
    # Сохраняем описание
    await state.update_data(task_description=description, task_creation_step=4)
    
    # Переходим к выбору приоритета
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Высокий", callback_data="task_priority_high"),
            InlineKeyboardButton(text="🟠 Средний", callback_data="task_priority_medium"),
        ],
        [
            InlineKeyboardButton(text="🟡 Низкий", callback_data="task_priority_low"),
            InlineKeyboardButton(text="⚡ Критический", callback_data="task_priority_critical"),
        ],
    ])
    
    await message.answer(
        f"✅ Описание сохранено\n\n"
        f"📋 <b>Шаг 4 из 7:</b> Выбери приоритет задачи\n\n"
        f"Нажми на кнопку с нужным приоритетом:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_priority)


@router.callback_query(F.data.startswith("task_priority_"))
async def process_task_priority(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора приоритета задачи"""
    await callback.answer()
    
    priority_str = callback.data.replace("task_priority_", "")
    
    # Маппинг приоритетов
    priority_map = {
        "low": TaskPriority.LOW,
        "medium": TaskPriority.MEDIUM,
        "high": TaskPriority.HIGH,
        "critical": TaskPriority.CRITICAL,
    }
    
    task_priority = priority_map.get(priority_str)
    if not task_priority:
        await callback.message.answer("❌ Неверный приоритет. Попробуйте ещё раз.")
        return
    
    # Сохраняем приоритет
    await state.update_data(task_priority=task_priority.value, task_creation_step=5)
    
    priority_names = {
        "low": "Низкий",
        "medium": "Средний",
        "high": "Высокий",
        "critical": "Критический",
    }
    
    await callback.message.edit_text(
        f"✅ Приоритет: <b>{priority_names[priority_str]}</b>\n\n"
        f"📋 <b>Шаг 5 из 7:</b> Введи дедлайн задачи\n\n"
        f"Напиши дату и время дедлайна в формате:\n"
        f"• <code>ДД.ММ.ГГГГ ЧЧ:ММ</code> (например: 25.12.2024 18:00)\n"
        f"• или просто дату: <code>ДД.ММ.ГГГГ</code> (например: 25.12.2024)\n\n"
        f"💡 <i>Если дедлайна нет, напиши \"нет\" или \"-\"</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_due_date)


@router.message(TaskCreationStates.waiting_for_due_date)
async def process_task_due_date(message: Message, state: FSMContext):
    """Обработка дедлайна задачи"""
    due_date_text = message.text.strip().lower()
    
    due_date = None
    
    # Если дедлайна нет
    if due_date_text in ["нет", "-", "без дедлайна", "no", "none"]:
        due_date = None
    else:
        # Парсим дату
        try:
            # Пробуем разные форматы
            formats = [
                "%d.%m.%Y %H:%M",  # ДД.ММ.ГГГГ ЧЧ:ММ
                "%d.%m.%Y",        # ДД.ММ.ГГГГ
                "%Y-%m-%d %H:%M",  # ГГГГ-ММ-ДД ЧЧ:ММ
                "%Y-%m-%d",        # ГГГГ-ММ-ДД
            ]
            
            parsed = False
            for fmt in formats:
                try:
                    due_date = datetime.strptime(due_date_text, fmt)
                    # Если не указано время, ставим 18:00 по умолчанию
                    if "%H:%M" not in fmt:
                        due_date = due_date.replace(hour=18, minute=0)
                    parsed = True
                    break
                except ValueError:
                    continue
            
            if not parsed:
                raise ValueError("Не удалось распарсить дату")
            
            # Делаем дату timezone-aware (UTC)
            if due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            
            # Проверяем, что дата в будущем
            if due_date < datetime.now(timezone.utc):
                await message.answer(
                    "❌ Дедлайн не может быть в прошлом. Пожалуйста, введи дату в будущем:"
                )
                return
            
        except Exception as e:
            await message.answer(
                "❌ Неверный формат даты. Пожалуйста, введи дату в формате ДД.ММ.ГГГГ или ДД.ММ.ГГГГ ЧЧ:ММ:\n\n"
                "Пример: 25.12.2024 или 25.12.2024 18:00"
            )
            return
    
    # Сохраняем дедлайн
    await state.update_data(
        task_due_date=due_date.isoformat() if due_date else None,
        task_creation_step=6
    )
    
    # Проверяем тип задачи - для всех типов нужны этапы
    data = await state.get_data()
    task_type = data.get("task_type")
    
    # Определяем этапы по умолчанию для каждого типа задачи
    stage_templates = {
        TaskType.SMM.value: [
            ("Исследование/Анализ", "green"),
            ("Написание текста", "yellow"),
            ("Редактура", "orange"),
            ("Публикация", "red"),
        ],
        TaskType.DESIGN.value: [
            ("Исследование", "green"),
            ("Концепция", "yellow"),
            ("Дизайн", "orange"),
            ("Редактура", "red"),
            ("Финальная версия", "red"),
        ],
        TaskType.CHANNEL.value: [
            ("Сценарий", "green"),
            ("Съёмка", "yellow"),
            ("Монтаж", "orange"),
            ("Публикация", "red"),
        ],
        TaskType.PRFR.value: [
            ("Исследование", "green"),
            ("Подготовка контента", "yellow"),
            ("Редактура", "orange"),
            ("Публикация", "red"),
        ],
    }
    
    stages_info = stage_templates.get(task_type, [])
    stages_text = "\n".join([f"• {stage[0]}" for stage in stages_info])
    
    type_names = {
        TaskType.SMM.value: "SMM",
        TaskType.DESIGN.value: "Design",
        TaskType.CHANNEL.value: "Channel",
        TaskType.PRFR.value: "PR-FR",
    }
    
    await message.answer(
        f"✅ Дедлайн сохранен\n\n"
        f"📋 <b>Шаг 6 из 7:</b> Этапы задачи (для {type_names.get(task_type, task_type)} задач)\n\n"
        f"Этапы создадутся автоматически по стандартному шаблону:\n"
        f"{stages_text}\n\n"
        f"💡 Если нужны дополнительные этапы, их можно добавить позже на сайте.\n\n"
        f"Продолжить с этапами по умолчанию?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, продолжить", callback_data="task_stages_default"),
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="task_stages_skip"),
            ],
        ]),
        parse_mode="HTML"
    )
    await state.set_state(TaskCreationStates.waiting_for_stages)


@router.callback_query(F.data == "task_stages_default")
async def process_task_stages_default(callback: CallbackQuery, state: FSMContext):
    """Создание этапов по умолчанию для всех типов задач"""
    await callback.answer()
    
    # Сохраняем, что этапы будут созданы по умолчанию
    await state.update_data(task_stages_default=True, task_creation_step=6)
    
    await callback.message.edit_text(
        f"✅ Этапы будут созданы автоматически\n\n"
        f"📋 <b>Шаг 6 из 7:</b> Добавь материалы (файлы) для задачи\n\n"
        f"Можешь прикрепить файлы (фото, документы, видео), которые помогут исполнителям:\n"
        f"• Прикрепи файлы одним сообщением\n"
        f"• Или нажми «Пропустить», если файлов нет\n\n"
        f"💡 <i>Можно добавить несколько файлов сразу.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="task_files_skip"),
            ],
        ]),
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_files)


@router.callback_query(F.data == "task_stages_skip")
async def process_task_stages_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск этапов"""
    await callback.answer()
    
    # Сохраняем, что этапы пропущены
    await state.update_data(task_stages_default=False, task_creation_step=6)
    
    await callback.message.edit_text(
        f"✅ Этапы пропущены (можно добавить позже)\n\n"
        f"📋 <b>Шаг 6 из 7:</b> Добавь материалы (файлы) для задачи\n\n"
        f"Можешь прикрепить файлы (фото, документы, видео), которые помогут исполнителям:\n"
        f"• Прикрепи файлы одним сообщением\n"
        f"• Или нажми «Пропустить», если файлов нет\n\n"
        f"💡 <i>Можно добавить несколько файлов сразу.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="task_files_skip"),
            ],
        ]),
        parse_mode="HTML"
    )
    
    await state.set_state(TaskCreationStates.waiting_for_files)


@router.message(TaskCreationStates.waiting_for_files, F.content_type.in_([ContentType.PHOTO, ContentType.DOCUMENT, ContentType.VIDEO]))
async def process_task_files(message: Message, state: FSMContext):
    """Обработка файлов задачи"""
    data = await state.get_data()
    task_files = data.get("task_files", [])
    
    # Обрабатываем файлы
    file_id = None
    file_type = None
    file_name = None
    
    if message.photo:
        # Фото
        file_id = message.photo[-1].file_id  # Берём самое большое фото
        file_type = "photo"
        file_name = f"photo_{message.photo[-1].file_unique_id}.jpg"
    elif message.document:
        # Документ
        file_id = message.document.file_id
        file_type = "document"
        file_name = message.document.file_name or f"document_{message.document.file_unique_id}"
    elif message.video:
        # Видео
        file_id = message.video.file_id
        file_type = "video"
        file_name = message.video.file_name or f"video_{message.video.file_unique_id}.mp4"
    
    if file_id:
        task_files.append({
            "file_id": file_id,
            "type": file_type,
            "name": file_name
        })
        await state.update_data(task_files=task_files)
        
        await message.answer(
            f"✅ Файл добавлен ({len(task_files)})\n\n"
            f"💡 Можешь добавить ещё файлы или нажми «Продолжить», чтобы перейти к подтверждению.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Продолжить", callback_data="task_files_done"),
                    InlineKeyboardButton(text="➕ Добавить ещё", callback_data="task_files_more"),
                ],
            ])
        )


@router.callback_query(F.data == "task_files_skip")
async def process_task_files_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск добавления файлов"""
    await callback.answer()
    
    await state.update_data(task_files=[], task_creation_step=7)
    
    # Переходим к подтверждению
    await show_task_confirmation(callback.message, state)


@router.callback_query(F.data == "task_files_done")
async def process_task_files_done(callback: CallbackQuery, state: FSMContext):
    """Завершение добавления файлов"""
    await callback.answer()
    
    await state.update_data(task_creation_step=7)
    
    # Переходим к подтверждению
    await show_task_confirmation(callback.message, state)


@router.callback_query(F.data == "task_files_more")
async def process_task_files_more(callback: CallbackQuery, state: FSMContext):
    """Продолжение добавления файлов"""
    await callback.answer()
    
    data = await state.get_data()
    files_count = len(data.get("task_files", []))
    
    await callback.message.edit_text(
        f"✅ Добавлено файлов: {files_count}\n\n"
        f"📋 <b>Шаг 6 из 7:</b> Добавь материалы (файлы) для задачи\n\n"
        f"Можешь прикрепить ещё файлы или нажми «Продолжить», чтобы перейти к подтверждению.\n\n"
        f"💡 <i>Можно добавить несколько файлов сразу.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Продолжить", callback_data="task_files_done"),
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="task_files_skip"),
            ],
        ]),
        parse_mode="HTML"
    )


async def show_task_confirmation(message_or_callback, state: FSMContext):
    """Показать подтверждение создания задачи"""
    data = await state.get_data()
    
    task_title = data.get("task_title")
    task_type = data.get("task_type")
    task_description = data.get("task_description", "")
    task_priority = data.get("task_priority")
    task_due_date = data.get("task_due_date")
    task_files = data.get("task_files", [])
    task_stages_default = data.get("task_stages_default", False)
    
    # Формируем текст подтверждения
    type_names = {
        "smm": "SMM",
        "design": "Design",
        "channel": "Channel",
        "prfr": "PR-FR",
    }
    priority_names = {
        "low": "Низкий",
        "medium": "Средний",
        "high": "Высокий",
        "critical": "Критический",
    }
    
    confirmation_text = (
        f"📝 <b>Подтверждение создания задачи</b>\n\n"
        f"📋 <b>Название:</b> {task_title}\n"
        f"📌 <b>Тип:</b> {type_names.get(task_type, task_type)}\n"
        f"🎯 <b>Приоритет:</b> {priority_names.get(task_priority, task_priority)}\n"
    )
    
    if task_due_date:
        due_date_obj = datetime.fromisoformat(task_due_date)
        confirmation_text += f"📅 <b>Дедлайн:</b> {due_date_obj.strftime('%d.%m.%Y %H:%M')}\n"
    else:
        confirmation_text += f"📅 <b>Дедлайн:</b> Не установлен\n"
    
    if task_stages_default:
        confirmation_text += f"📑 <b>Этапы:</b> Будют созданы автоматически\n"
    
    confirmation_text += f"\n📄 <b>Описание:</b>\n{task_description[:200]}{'...' if len(task_description) > 200 else ''}\n"
    
    if task_files:
        confirmation_text += f"\n📎 <b>Файлы:</b> {len(task_files)} файл(ов)\n"
    
    confirmation_text += (
        f"\n\n💡 Проверь данные и подтверди создание задачи:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Создать задачу", callback_data="task_confirm_create"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="task_confirm_edit"),
        ],
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data="task_confirm_cancel"),
        ],
    ])
    
    if hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.set_state(TaskCreationStates.confirming)


@router.callback_query(F.data == "task_confirm_create", TaskCreationStates.confirming)
async def process_task_confirm_create(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и создание задачи"""
    await callback.answer()
    
    user = callback.from_user
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.message.edit_text("❌ Ошибка: не найден токен авторизации.")
        await state.clear()
        return
    
    # Получаем данные задачи
    task_title = data.get("task_title")
    task_type = data.get("task_type")
    task_description = data.get("task_description", "")
    task_priority = data.get("task_priority")
    task_due_date = data.get("task_due_date")
    task_files = data.get("task_files", [])
    task_stages_default = data.get("task_stages_default", False)
    
    # Подготавливаем данные для API
    task_data = {
        "title": task_title,
        "description": task_description,
        "type": task_type,
        "priority": task_priority,
        "due_date": task_due_date,
    }
    
    # Если нужны этапы по умолчанию (для всех типов задач)
    if task_stages_default:
        if task_due_date:
            due_date_obj = datetime.fromisoformat(task_due_date)
            if due_date_obj.tzinfo is None:
                due_date_obj = due_date_obj.replace(tzinfo=timezone.utc)
        else:
            due_date_obj = datetime.now(timezone.utc) + timedelta(days=7)
        
        # Определяем этапы по умолчанию для каждого типа задачи
        stage_templates = {
            TaskType.SMM.value: [
                ("Исследование/Анализ", "green", 3),  # за 3 дня до дедлайна
                ("Написание текста", "yellow", 2),    # за 2 дня
                ("Редактура", "orange", 1),           # за 1 день
                ("Публикация", "red", 0),             # в день дедлайна
            ],
            TaskType.DESIGN.value: [
                ("Исследование", "green", 4),         # за 4 дня
                ("Концепция", "yellow", 3),           # за 3 дня
                ("Дизайн", "orange", 2),              # за 2 дня
                ("Редактура", "red", 1),              # за 1 день
                ("Финальная версия", "red", 0),       # в день дедлайна
            ],
            TaskType.CHANNEL.value: [
                ("Сценарий", "green", 3),             # за 3 дня
                ("Съёмка", "yellow", 1),              # за 1 день
                ("Монтаж", "orange", 0.25),           # за 6 часов
                ("Публикация", "red", 0),             # в день дедлайна
            ],
            TaskType.PRFR.value: [
                ("Исследование", "green", 3),         # за 3 дня
                ("Подготовка контента", "yellow", 2), # за 2 дня
                ("Редактура", "orange", 1),           # за 1 день
                ("Публикация", "red", 0),             # в день дедлайна
            ],
        }
        
        stages_template = stage_templates.get(task_type, [])
        
        # Создаём этапы по умолчанию (дедлайны рассчитываем от общего дедлайна задачи)
        stages = []
        for i, (stage_name, status_color, days_before) in enumerate(stages_template, 1):
            # Рассчитываем дедлайн этапа
            if days_before >= 1:
                stage_due_date = due_date_obj - timedelta(days=int(days_before))
            else:
                # Для дробных значений (например, 0.25 дня = 6 часов)
                stage_due_date = due_date_obj - timedelta(hours=int(days_before * 24))
            
            stages.append({
                "stage_name": stage_name,
                "stage_order": i,
                "due_date": stage_due_date.isoformat(),
                "status_color": status_color
            })
        
        task_data["stages"] = stages
    
    # Создаём задачу через API
    headers = {"Authorization": f"Bearer {access_token}"}
    create_response = await call_api("POST", "/tasks", data=task_data, headers=headers)
    
    if "error" in create_response:
        await callback.message.edit_text(
            f"❌ Ошибка создания задачи: {create_response.get('error', 'Неизвестная ошибка')}\n\n"
            f"Попробуйте позже или создайте задачу на сайте.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    task_id = create_response.get("id")
    task_title_created = create_response.get("title")
    
    # Если есть файлы, загружаем их в Google Drive
    if task_files and task_id:
        try:
            # Получаем папку задачи в Google Drive
            drive_folders_response = await call_api("POST", f"/drive/tasks/{task_id}/folders", 
                                                    data={"task_name": task_title_created}, 
                                                    headers=headers)
            
            if "error" not in drive_folders_response:
                materials_folder_id = drive_folders_response.get("folders", {}).get("materials_folder_id")
                
                # Загружаем файлы (это будет сделано асинхронно через executor, так как это долгая операция)
                # Пока просто логируем
                logger.info(f"Task {task_id} created, {len(task_files)} files to upload to Drive")
        except Exception as e:
            logger.warning(f"Failed to create Drive folders or upload files for task {task_id}: {e}")
    
    # Успешное создание задачи
    await callback.message.edit_text(
        f"✅ <b>Задача успешно создана!</b>\n\n"
        f"📋 <b>Название:</b> {task_title_created}\n"
        f"🆔 <b>ID:</b> <code>{task_id}</code>\n\n"
        f"💡 Задача создана в статусе <b>Черновик</b>. Опубликуй её, когда будешь готов.\n\n"
        f"🌐 <a href=\"{settings.FRONTEND_URL}/tasks/{task_id}\">Открыть задачу на сайте</a>",
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data == "task_confirm_edit", TaskCreationStates.confirming)
async def process_task_confirm_edit(callback: CallbackQuery, state: FSMContext):
    """Редактирование данных задачи перед созданием"""
    await callback.answer()
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование задачи</b>\n\n"
        "В данный момент редактирование в процессе создания задачи не реализовано.\n\n"
        "💡 <b>Решение:</b>\n"
        "• Отмени создание задачи и начни заново командой /create_task\n"
        "• Или создай задачу как есть, а затем отредактируй её на сайте\n\n"
        "Продолжить с текущими данными?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, создать", callback_data="task_confirm_create"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="task_confirm_cancel"),
            ],
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "task_confirm_cancel", TaskCreationStates.confirming)
async def process_task_confirm_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена создания задачи"""
    await callback.answer()
    
    await callback.message.edit_text(
        "❌ <b>Создание задачи отменено</b>\n\n"
        "Ты можешь создать задачу позже командой /create_task или на сайте.",
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()


# ========== Обработчики для меню оборудования ==========

@router.callback_query(F.data == "equipment_my_requests")
async def callback_equipment_my_requests(callback: CallbackQuery, state: FSMContext):
    """Показать мои заявки на оборудование"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        requests_response = await call_api("GET", "/equipment/requests", headers=headers)
        
        if "error" in requests_response:
            await callback.message.answer("❌ Ошибка при загрузке заявок.")
            return
        
        requests = requests_response if isinstance(requests_response, list) else []
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        if not requests:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Подать заявку", callback_data="equipment_new_request"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="equipment"),
                ],
            ])
            
            await callback.message.answer(
                f"📦 <b>Мои заявки на оборудование</b>\n\n"
                f"У тебя пока нет заявок.\n\n"
                f"💡 <b>Совет:</b> При взятии задачи типа Channel с возможностью получения оборудования, система автоматически предложит его.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            status_emoji = {
                "pending": "⏳",
                "approved": "✅",
                "rejected": "❌",
                "active": "📦",
                "completed": "✔️",
                "cancelled": "🚫"
            }
            
            status_names = {
                "pending": "На рассмотрении",
                "approved": "Одобрена",
                "rejected": "Отклонена",
                "active": "Активна",
                "completed": "Завершена",
                "cancelled": "Отменена"
            }
            
            text = f"📦 <b>Мои заявки на оборудование ({len(requests)})</b>\n\n"
            
            for i, req in enumerate(requests[:10], 1):  # Показываем первые 10
                emoji = status_emoji.get(req.get("status"), "❓")
                status_name = status_names.get(req.get("status"), req.get("status"))
                text += (
                    f"{i}. {emoji} <b>{req.get('equipment_name', 'Unknown')}</b>\n"
                    f"   Статус: {status_name}\n"
                    f"   Даты: {req.get('start_date')} - {req.get('end_date')}\n\n"
                )
            
            if len(requests) > 10:
                text += f"... и ещё {len(requests) - 10} заявок\n\n"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📝 Подать новую заявку", callback_data="equipment_new_request"),
                ],
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="equipment"),
                ],
            ])
            
            await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_equipment_my_requests: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "equipment_available_list")
async def callback_equipment_available_list(callback: CallbackQuery, state: FSMContext):
    """Показать доступное оборудование"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        equipment_response = await call_api("GET", "/equipment", headers=headers)
        
        if "error" in equipment_response:
            await callback.message.answer("❌ Ошибка при загрузке оборудования. Попробуйте позже.")
            return
        
        equipment_list = equipment_response.get("items", [])
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        if not equipment_list:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🔙 Назад", callback_data="equipment"),
                ],
            ])
            
            await callback.message.answer(
                f"📦 <b>Доступное оборудование</b>\n\n"
                f"Оборудование пока не добавлено.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        
        status_emoji = {
            "available": "✅",
            "rented": "🔴",
            "maintenance": "🔧",
            "broken": "❌",
        }
        
        status_names = {
            "available": "Доступно",
            "rented": "В аренде",
            "maintenance": "На обслуживании",
            "broken": "Сломано",
        }
        
        text = f"📦 <b>Доступное оборудование ({len(equipment_list)})</b>\n\n"
        
        # Группируем по категориям
        by_category = {}
        for eq in equipment_list:
            category = eq.get('category', 'other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(eq)
        
        category_names = {
            "camera": "📷 Камеры",
            "lens": "🔍 Объективы",
            "lighting": "💡 Освещение",
            "audio": "🎤 Аудио",
            "tripod": "📐 Штативы",
            "accessories": "🔧 Аксессуары",
            "storage": "💾 Накопители",
            "other": "📦 Другое",
        }
        
        for category, items in sorted(by_category.items()):
            category_name = category_names.get(category, f"📦 {category}")
            text += f"{category_name}:\n"
            for eq in items[:5]:  # Показываем первые 5 в каждой категории
                emoji = status_emoji.get(eq.get("status"), "❓")
                status_name = status_names.get(eq.get("status"), eq.get("status"))
                eq_name = eq.get('name', 'Unknown')
                eq_quantity = eq.get('quantity', 1)
                
                # Показываем количество, если больше 1
                if eq_quantity > 1:
                    text += f"  {emoji} {eq_name} ({status_name}, {eq_quantity} шт.)\n"
                else:
                    text += f"  {emoji} {eq_name} ({status_name})\n"
            if len(items) > 5:
                text += f"  ... и ещё {len(items) - 5}\n"
            text += "\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Подать заявку", callback_data="equipment_new_request"),
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="equipment"),
            ],
        ])
        
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in callback_equipment_available_list: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data == "equipment_new_request")
async def callback_equipment_new_request(callback: CallbackQuery, state: FSMContext):
    """Начать процесс подачи заявки на оборудование"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Начинаем FSM для подачи заявки
        await callback.message.answer(
            "📝 <b>Подача заявки на оборудование</b>\n\n"
            "Давай заполним заявку пошагово!\n\n"
            "📋 <b>Шаг 1 из 6:</b> Введи название съёмки\n\n"
            "Напиши название съёмки или проекта, для которого нужно оборудование:",
            parse_mode="HTML"
        )
        
        await state.set_state(EquipmentRequestStates.waiting_for_shooting_name)
        await state.update_data(equipment_request_step=1)
        
    except Exception as e:
        logger.error(f"Error in callback_equipment_new_request: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.message(EquipmentRequestStates.waiting_for_shooting_name)
async def process_equipment_shooting_name(message: Message, state: FSMContext):
    """Обработка названия съёмки"""
    shooting_name = message.text.strip()
    
    if len(shooting_name) < 3:
        await message.answer("❌ Название слишком короткое. Введи название съёмки (минимум 3 символа):")
        return
    
    # Сохраняем название
    await state.update_data(
        equipment_shooting_name=shooting_name,
        equipment_request_step=2
    )
    
    # Переходим к дате съёмки
    await message.answer(
        f"✅ Название сохранено: <b>{shooting_name}</b>\n\n"
        f"📋 <b>Шаг 2 из 6:</b> Введи дату съёмки\n\n"
        f"Напиши дату съёмки в формате <code>ДД.ММ.ГГГГ</code> (например: 25.12.2024):\n\n"
        f"💡 <i>Заявку нужно подавать минимум за 2 дня до съёмки.</i>",
        parse_mode="HTML"
    )
    
    await state.set_state(EquipmentRequestStates.waiting_for_shooting_date)


@router.message(EquipmentRequestStates.waiting_for_shooting_date)
async def process_equipment_shooting_date(message: Message, state: FSMContext):
    """Обработка даты съёмки"""
    from datetime import datetime, timedelta, timezone as tz
    
    shooting_date_text = message.text.strip()
    
    try:
        # Парсим дату
        shooting_date = datetime.strptime(shooting_date_text, "%d.%m.%Y").date()
        
        # Проверяем, что дата не в прошлом
        if shooting_date < datetime.now(tz.utc).date():
            await message.answer("❌ Дата съёмки не может быть в прошлом. Введи дату в будущем:")
            return
        
        # Проверяем, что заявка подаётся минимум за 2 дня
        min_date = datetime.now(tz.utc).date() + timedelta(days=2)
        if shooting_date < min_date:
            await message.answer(
                f"❌ Заявку нужно подавать минимум за 2 дня до съёмки.\n\n"
                f"Минимальная дата: {min_date.strftime('%d.%m.%Y')}\n\n"
                f"Введи дату съёмки:"
            )
            return
        
        # Сохраняем дату
        await state.update_data(
            equipment_shooting_date=shooting_date.isoformat(),
            equipment_request_step=3
        )
        
        # Переходим к дате получения оборудования
        await message.answer(
            f"✅ Дата съёмки сохранена: <b>{shooting_date.strftime('%d.%m.%Y')}</b>\n\n"
            f"📋 <b>Шаг 3 из 6:</b> Введи дату получения оборудования\n\n"
            f"Напиши дату, когда нужно получить оборудование в формате <code>ДД.ММ.ГГГГ</code>:\n\n"
            f"💡 <i>Обычно оборудование получают за день до съёмки или в день съёмки.</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(EquipmentRequestStates.waiting_for_rental_start)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введи дату в формате ДД.ММ.ГГГГ (например: 25.12.2024):"
        )


@router.message(EquipmentRequestStates.waiting_for_rental_start)
async def process_equipment_rental_start(message: Message, state: FSMContext):
    """Обработка даты получения оборудования"""
    from datetime import datetime, timezone as tz
    
    rental_start_text = message.text.strip()
    
    try:
        rental_start = datetime.strptime(rental_start_text, "%d.%m.%Y").date()
        
        # Получаем дату съёмки из состояния
        data = await state.get_data()
        shooting_date_str = data.get("equipment_shooting_date")
        if shooting_date_str:
            shooting_date = datetime.fromisoformat(shooting_date_str).date()
            
            # Проверяем, что дата получения не позже даты съёмки
            if rental_start > shooting_date:
                await message.answer(
                    f"❌ Дата получения оборудования не может быть позже даты съёмки ({shooting_date.strftime('%d.%m.%Y')}).\n\n"
                    f"Введи дату получения оборудования:"
                )
                return
        
        # Сохраняем дату
        await state.update_data(
            equipment_rental_start=rental_start.isoformat(),
            equipment_request_step=4
        )
        
        # Переходим к дате возврата
        await message.answer(
            f"✅ Дата получения сохранена: <b>{rental_start.strftime('%d.%m.%Y')}</b>\n\n"
            f"📋 <b>Шаг 4 из 6:</b> Введи дату возврата оборудования\n\n"
            f"Напиши дату, когда нужно вернуть оборудование в формате <code>ДД.ММ.ГГГГ</code>:\n\n"
            f"💡 <i>Обычно оборудование возвращают в день съёмки или на следующий день.</i>",
            parse_mode="HTML"
        )
        
        await state.set_state(EquipmentRequestStates.waiting_for_rental_end)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введи дату в формате ДД.ММ.ГГГГ (например: 25.12.2024):"
        )


@router.message(EquipmentRequestStates.waiting_for_rental_end)
async def process_equipment_rental_end(message: Message, state: FSMContext):
    """Обработка даты возврата оборудования"""
    from datetime import datetime, timezone as tz
    
    rental_end_text = message.text.strip()
    
    try:
        rental_end = datetime.strptime(rental_end_text, "%d.%m.%Y").date()
        
        # Получаем дату получения из состояния
        data = await state.get_data()
        rental_start_str = data.get("equipment_rental_start")
        if rental_start_str:
            rental_start = datetime.fromisoformat(rental_start_str).date()
            
            # Проверяем, что дата возврата не раньше даты получения
            if rental_end < rental_start:
                await message.answer(
                    f"❌ Дата возврата не может быть раньше даты получения ({rental_start.strftime('%d.%m.%Y')}).\n\n"
                    f"Введи дату возврата оборудования:"
                )
                return
        
        # Сохраняем дату
        await state.update_data(
            equipment_rental_end=rental_end.isoformat(),
            equipment_request_step=5
        )
        
        # Получаем доступное оборудование на эти даты
        data = await state.get_data()
        access_token = data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        try:
            available_response = await call_api(
                "GET",
                f"/equipment/available?start_date={rental_start.isoformat()}&end_date={rental_end.isoformat()}",
                headers=headers
            )
            available_equipment = available_response if isinstance(available_response, list) else []
        except Exception as e:
            logger.warning(f"Failed to get available equipment: {e}")
            available_equipment = []
        
        if not available_equipment:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="➡️ Продолжить без оборудования", callback_data="equipment_selection_skip"),
                ],
                [
                    InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
                ],
            ])
            
            await message.answer(
                f"✅ Дата возврата сохранена: <b>{rental_end.strftime('%d.%m.%Y')}</b>\n\n"
                f"⚠️ <b>На указанные даты нет доступного оборудования.</b>\n\n"
                f"Можешь продолжить без выбора оборудования или отменить заявку.",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            await state.set_state(EquipmentRequestStates.waiting_for_equipment_selection)
            return
        
        # Формируем кнопки для выбора оборудования с информацией о количестве
        keyboard_buttons = []
        equipment_list_items = []
        
        for eq in available_equipment[:10]:  # Показываем первые 10
            eq_name = eq.get('name', 'Unknown')
            eq_quantity = eq.get('quantity', 1)
            eq_category = eq.get('category', 'other')
            
            # Подсчитываем, сколько экземпляров уже забронировано на эти даты
            # (это уже учтено в get_available_equipment, но показываем для информации)
            available_count = eq_quantity  # В будущем можно добавить точный подсчёт
            
            # Формируем текст кнопки с количеством
            if eq_quantity > 1:
                button_text = f"📦 {eq_name} ({available_count}/{eq_quantity} шт.)"
            else:
                button_text = f"📦 {eq_name}"
            
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"equipment_select_{eq.get('id')}"
                ),
            ])
            
            # Формируем текст для списка
            category_emoji = {
                'camera': '📷',
                'lens': '🔍',
                'lighting': '💡',
                'audio': '🎤',
                'tripod': '📐',
                'accessories': '🔧',
                'storage': '💾',
                'other': '📦'
            }.get(eq_category, '📦')
            
            if eq_quantity > 1:
                equipment_list_items.append(f"{category_emoji} {eq_name} ({available_count}/{eq_quantity} шт.)")
            else:
                equipment_list_items.append(f"{category_emoji} {eq_name}")
        
        keyboard_buttons.append([
            InlineKeyboardButton(text="➡️ Продолжить без оборудования", callback_data="equipment_selection_skip"),
        ])
        keyboard_buttons.append([
            InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        equipment_list_text = "\n".join(equipment_list_items)
        
        await message.answer(
            f"✅ Дата возврата сохранена: <b>{rental_end.strftime('%d.%m.%Y')}</b>\n\n"
            f"📋 <b>Шаг 5 из 6:</b> Выбери оборудование\n\n"
            f"Доступное оборудование на даты {rental_start.strftime('%d.%m.%Y')} - {rental_end.strftime('%d.%m.%Y')}:\n"
            f"{equipment_list_text}\n\n"
            f"Нажми на кнопку с нужным оборудованием:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(EquipmentRequestStates.waiting_for_equipment_selection)
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты. Введи дату в формате ДД.ММ.ГГГГ (например: 25.12.2024):"
        )


@router.callback_query(F.data.startswith("equipment_select_"))
async def process_equipment_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора оборудования"""
    await callback.answer()
    
    equipment_id = callback.data.replace("equipment_select_", "")
    
    # Сохраняем выбранное оборудование
    await state.update_data(
        equipment_selected_id=equipment_id,
        equipment_request_step=6
    )
    
    # Получаем информацию об оборудовании
    data = await state.get_data()
    access_token = data.get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        equipment_response = await call_api("GET", f"/equipment/{equipment_id}", headers=headers)
        equipment_name = equipment_response.get("name", "Unknown") if "error" not in equipment_response else "Unknown"
    except Exception:
        equipment_name = "Unknown"
    
    await callback.message.edit_text(
        f"✅ Оборудование выбрано: <b>{equipment_name}</b>\n\n"
        f"📋 <b>Шаг 6 из 6:</b> Комментарий (опционально)\n\n"
        f"Можешь добавить комментарий к заявке или нажми «Пропустить»:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="equipment_comment_skip"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
            ],
        ]),
        parse_mode="HTML"
    )
    
    await state.set_state(EquipmentRequestStates.waiting_for_comment)


@router.callback_query(F.data == "equipment_selection_skip")
async def process_equipment_selection_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск выбора оборудования"""
    await callback.answer()
    
    await state.update_data(
        equipment_selected_id=None,
        equipment_request_step=6
    )
    
    await callback.message.edit_text(
        f"✅ Выбор оборудования пропущен\n\n"
        f"📋 <b>Шаг 6 из 6:</b> Комментарий (опционально)\n\n"
        f"Можешь добавить комментарий к заявке или нажми «Пропустить»:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="➡️ Пропустить", callback_data="equipment_comment_skip"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
            ],
        ]),
        parse_mode="HTML"
    )
    
    await state.set_state(EquipmentRequestStates.waiting_for_comment)


@router.message(EquipmentRequestStates.waiting_for_comment)
async def process_equipment_comment(message: Message, state: FSMContext):
    """Обработка комментария к заявке"""
    comment = message.text.strip()
    
    await state.update_data(
        equipment_comment=comment,
        equipment_request_step=7
    )
    
    # Переходим к подтверждению
    await show_equipment_request_confirmation(message, state)


@router.callback_query(F.data == "equipment_comment_skip")
async def process_equipment_comment_skip(callback: CallbackQuery, state: FSMContext):
    """Пропуск комментария"""
    await callback.answer()
    
    await state.update_data(
        equipment_comment=None,
        equipment_request_step=7
    )
    
    # Переходим к подтверждению
    await show_equipment_request_confirmation(callback.message, state)


async def show_equipment_request_confirmation(message_or_callback, state: FSMContext):
    """Показать подтверждение заявки на оборудование"""
    from datetime import datetime
    from uuid import UUID
    
    data = await state.get_data()
    
    shooting_name = data.get("equipment_shooting_name")
    shooting_date_str = data.get("equipment_shooting_date")
    rental_start_str = data.get("equipment_rental_start")
    rental_end_str = data.get("equipment_rental_end")
    equipment_id = data.get("equipment_selected_id")
    comment = data.get("equipment_comment")
    
    # Форматируем даты
    shooting_date = datetime.fromisoformat(shooting_date_str).date() if shooting_date_str else None
    rental_start = datetime.fromisoformat(rental_start_str).date() if rental_start_str else None
    rental_end = datetime.fromisoformat(rental_end_str).date() if rental_end_str else None
    
    # Получаем название оборудования
    equipment_name = "Не выбрано"
    if equipment_id:
        access_token = data.get("access_token")
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            equipment_response = await call_api("GET", f"/equipment/{equipment_id}", headers=headers)
            equipment_name = equipment_response.get("name", "Unknown") if "error" not in equipment_response else "Unknown"
        except Exception:
            pass
    
    confirmation_text = (
        f"📝 <b>Подтверждение заявки на оборудование</b>\n\n"
        f"📋 <b>Название съёмки:</b> {shooting_name}\n"
        f"📅 <b>Дата съёмки:</b> {shooting_date.strftime('%d.%m.%Y') if shooting_date else 'Не указана'}\n"
        f"📦 <b>Оборудование:</b> {equipment_name}\n"
        f"📥 <b>Получение:</b> {rental_start.strftime('%d.%m.%Y') if rental_start else 'Не указана'}\n"
        f"📤 <b>Возврат:</b> {rental_end.strftime('%d.%m.%Y') if rental_end else 'Не указана'}\n"
    )
    
    if comment:
        confirmation_text += f"\n💬 <b>Комментарий:</b>\n{comment}\n"
    
    confirmation_text += "\n\n💡 Проверь данные и подтверди заявку:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить заявку", callback_data="equipment_request_confirm"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
        ],
    ])
    
    if hasattr(message_or_callback, 'edit_text'):
        await message_or_callback.edit_text(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.answer(confirmation_text, reply_markup=keyboard, parse_mode="HTML")
    
    await state.set_state(EquipmentRequestStates.confirming)


@router.callback_query(F.data == "equipment_request_confirm", EquipmentRequestStates.confirming)
async def process_equipment_request_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и создание заявки на оборудование"""
    await callback.answer()
    
    from datetime import datetime
    from uuid import UUID
    
    data = await state.get_data()
    access_token = data.get("access_token")
    
    if not access_token:
        await callback.message.edit_text("❌ Ошибка: не найден токен авторизации.")
        await state.clear()
        return
    
    # Получаем данные заявки
    shooting_name = data.get("equipment_shooting_name")
    rental_start_str = data.get("equipment_rental_start")
    rental_end_str = data.get("equipment_rental_end")
    equipment_id = data.get("equipment_selected_id")
    comment = data.get("equipment_comment")
    task_id = data.get("equipment_task_id")  # Если заявка связана с задачей
    
    if not equipment_id:
        await callback.message.edit_text(
            "❌ Ошибка: не выбрано оборудование.\n\n"
            "Пожалуйста, начни заявку заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Подготавливаем данные для API
    request_data = {
        "equipment_id": equipment_id,
        "start_date": rental_start_str,
        "end_date": rental_end_str,
    }
    
    if task_id:
        request_data["task_id"] = task_id
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Создаём заявку через API
    create_response = await call_api("POST", "/equipment/requests", data=request_data, headers=headers)
    
    if "error" in create_response:
        await callback.message.edit_text(
            f"❌ Ошибка создания заявки: {create_response.get('error', 'Неизвестная ошибка')}\n\n"
            f"Попробуйте позже или создайте заявку на сайте.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    request_id = create_response.get("id")
    equipment_name = create_response.get("equipment_name", "Unknown")
    
    # Успешное создание заявки
    await callback.message.edit_text(
        f"✅ <b>Заявка успешно создана!</b>\n\n"
        f"📦 <b>Оборудование:</b> {equipment_name}\n"
        f"📅 <b>Даты:</b> {rental_start_str} - {rental_end_str}\n"
        f"🆔 <b>ID заявки:</b> <code>{request_id}</code>\n\n"
        f"⏳ Заявка отправлена на рассмотрение координаторам.\n\n"
        f"🔔 Мы уведомим тебя, когда заявка будет одобрена или отклонена.\n\n"
        f"🌐 <a href=\"{settings.FRONTEND_URL}/equipment\">Посмотреть заявку на сайте</a>",
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data == "equipment_request_cancel")
async def process_equipment_request_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена подачи заявки на оборудование"""
    await callback.answer()
    
    await callback.message.edit_text(
        "❌ <b>Подача заявки отменена</b>\n\n"
        "Ты можешь подать заявку позже через меню оборудования или на сайте.",
        parse_mode="HTML"
    )
    
    # Очищаем состояние
    await state.clear()


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню (эмулирует /start)"""
    try:
        await callback.answer()
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Эмулируем команду /start - просто вызываем cmd_start
        await cmd_start(callback.message, state)
    except Exception as e:
        logger.error(f"Error in callback_main_menu: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


@router.callback_query(F.data.startswith("equipment_quick_request_"))
async def callback_equipment_quick_request(callback: CallbackQuery, state: FSMContext):
    """Быстрая подача заявки на оборудование для задачи"""
    try:
        await callback.answer()
        data = await state.get_data()
        access_token = data.get("access_token")
        
        if not access_token:
            await callback.message.answer("⚠️ Сначала выполните /start для авторизации.")
            return
        
        # Извлекаем task_id из callback_data
        task_id_str = callback.data.replace("equipment_quick_request_", "")
        
        # Получаем информацию о задаче
        headers = {"Authorization": f"Bearer {access_token}"}
        task_response = await call_api("GET", f"/tasks/{task_id_str}", headers=headers)
        
        if "error" in task_response:
            await callback.message.answer("❌ Ошибка при загрузке задачи.")
            return
        
        task = task_response
        task_title = task.get("title", "Unknown")
        
        # Находим этап "Съёмка" для предзаполнения дат
        stages = task.get("stages", [])
        shooting_stage = None
        for stage in stages:
            if stage.get("stage_name", "").lower() in ["съёмка", "shooting", "съемка"]:
                shooting_stage = stage
                break
        
        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception:
            pass
        
        # Предзаполняем данные из задачи
        if shooting_stage and shooting_stage.get("due_date"):
            from datetime import datetime
            shooting_date = datetime.fromisoformat(shooting_stage["due_date"]).date()
            rental_start = shooting_date  # Получение в день съёмки
            rental_end = shooting_date  # Возврат в день съёмки
            
            await state.update_data(
                equipment_shooting_name=task_title,
                equipment_shooting_date=shooting_date.isoformat(),
                equipment_rental_start=rental_start.isoformat(),
                equipment_rental_end=rental_end.isoformat(),
                equipment_task_id=task_id_str,
                equipment_request_step=5  # Пропускаем шаги 1-4, сразу к выбору оборудования
            )
            
            # Получаем доступное оборудование
            try:
                available_response = await call_api(
                    "GET",
                    f"/equipment/available?start_date={rental_start.isoformat()}&end_date={rental_end.isoformat()}",
                    headers=headers
                )
                available_equipment = available_response if isinstance(available_response, list) else []
            except Exception:
                available_equipment = []
            
            if available_equipment:
                # Формируем кнопки для выбора оборудования с информацией о количестве
                keyboard_buttons = []
                equipment_list_items = []
                
                for eq in available_equipment[:10]:
                    eq_name = eq.get('name', 'Unknown')
                    eq_quantity = eq.get('quantity', 1)
                    eq_category = eq.get('category', 'other')
                    
                    # Формируем текст кнопки с количеством
                    if eq_quantity > 1:
                        button_text = f"📦 {eq_name} ({eq_quantity} шт.)"
                    else:
                        button_text = f"📦 {eq_name}"
                    
                    keyboard_buttons.append([
                        InlineKeyboardButton(
                            text=button_text,
                            callback_data=f"equipment_select_{eq.get('id')}"
                        ),
                    ])
                    
                    # Формируем текст для списка
                    category_emoji = {
                        'camera': '📷',
                        'lens': '🔍',
                        'lighting': '💡',
                        'audio': '🎤',
                        'tripod': '📐',
                        'accessories': '🔧',
                        'storage': '💾',
                        'other': '📦'
                    }.get(eq_category, '📦')
                    
                    if eq_quantity > 1:
                        equipment_list_items.append(f"{category_emoji} {eq_name} ({eq_quantity} шт.)")
                    else:
                        equipment_list_items.append(f"{category_emoji} {eq_name}")
                
                keyboard_buttons.append([
                    InlineKeyboardButton(text="➡️ Продолжить без оборудования", callback_data="equipment_selection_skip"),
                ])
                keyboard_buttons.append([
                    InlineKeyboardButton(text="❌ Отменить", callback_data="equipment_request_cancel"),
                ])
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
                
                equipment_list_text = "\n".join(equipment_list_items)
                
                await callback.message.answer(
                    f"📝 <b>Быстрая подача заявки на оборудование</b>\n\n"
                    f"📋 <b>Задача:</b> {task_title}\n"
                    f"📅 <b>Дата съёмки:</b> {shooting_date.strftime('%d.%m.%Y')}\n\n"
                    f"Доступное оборудование на дату съёмки:\n"
                    f"{equipment_list_text}\n\n"
                    f"Выбери оборудование:",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                
                await state.set_state(EquipmentRequestStates.waiting_for_equipment_selection)
            else:
                # Нет доступного оборудования
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📝 Подать заявку вручную", callback_data="equipment_new_request"),
                    ],
                    [
                        InlineKeyboardButton(text="🔙 Назад", callback_data="equipment"),
                    ],
                ])
                
                await callback.message.answer(
                    f"📝 <b>Быстрая подача заявки на оборудование</b>\n\n"
                    f"📋 <b>Задача:</b> {task_title}\n"
                    f"📅 <b>Дата съёмки:</b> {shooting_date.strftime('%d.%m.%Y')}\n\n"
                    f"⚠️ <b>На указанную дату нет доступного оборудования.</b>\n\n"
                    f"Можешь подать заявку вручную или выбрать другую дату.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        else:
            # Нет этапа "Съёмка" или даты, начинаем обычный процесс
            await callback.message.answer(
                f"📝 <b>Подача заявки на оборудование для задачи</b>\n\n"
                f"📋 <b>Задача:</b> {task_title}\n\n"
                f"Давай заполним заявку пошагово!\n\n"
                f"📋 <b>Шаг 1 из 6:</b> Введи название съёмки\n\n"
                f"Напиши название съёмки или проекта:",
                parse_mode="HTML"
            )
            
            await state.update_data(equipment_task_id=task_id_str)
            await state.set_state(EquipmentRequestStates.waiting_for_shooting_name)
            await state.update_data(equipment_request_step=1)
        
    except Exception as e:
        logger.error(f"Error in callback_equipment_quick_request: {e}")
        await callback.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=True)


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
