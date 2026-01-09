"""
API endpoints для регистрации с согласием и пользовательским соглашением
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.schemas.auth import TelegramAuthData, PersonalDataConsent, UserAgreementAccept
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import OptionalUser
from app.services.registration_code_service import RegistrationCodeService
from app.utils.telegram_sender import send_telegram_message
from app.config import settings

router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationRequest(BaseModel):
    """Запрос на регистрацию"""
    telegram_auth: TelegramAuthData
    personal_data_consent: PersonalDataConsent
    user_agreement: UserAgreementAccept
    qr_token: Optional[str] = None  # Опциональный токен QR-сессии для упрощённой регистрации


class RegistrationCodeRequest(BaseModel):
    """Запрос на получение кода регистрации"""
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None


class RegistrationCodeVerifyRequest(BaseModel):
    """Запрос на регистрацию с кодом"""
    code: str
    personal_data_consent: PersonalDataConsent
    user_agreement: UserAgreementAccept


@router.post("/register", response_model=dict)
async def register(
    registration: RegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя с согласием и пользовательским соглашением
    
    Доступно всем (публичный endpoint)
    """
    # Проверяем согласие
    if not registration.personal_data_consent.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Согласие на обработку персональных данных обязательно"
        )
    
    if not registration.user_agreement.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо принять пользовательское соглашение"
        )
    
    # Логируем для отладки
    import logging
    logger = logging.getLogger(__name__)
    
    # Если есть qr_token, используем данные из QR-сессии (упрощённая регистрация)
    if registration.qr_token:
        from app.models.qr_session import QRSession
        result = await db.execute(
            select(QRSession).where(QRSession.session_token == registration.qr_token)
        )
        qr_session = result.scalar_one_or_none()
        
        if not qr_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR session not found"
            )
        
        if qr_session.status != "confirmed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR session not confirmed. Please confirm QR code in Telegram bot first."
            )
        
        if not qr_session.telegram_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR session does not have telegram_id"
            )
        
        # Используем telegram_id из QR-сессии
        # Данные пользователя берём из telegram_auth (они должны быть переданы с фронтенда)
        telegram_id = qr_session.telegram_id
        
        # Проверяем, что telegram_id в auth_data совпадает с telegram_id в QR-сессии
        auth_data = registration.telegram_auth.model_dump()
        if auth_data.get("id") != telegram_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram ID mismatch between QR session and auth data"
            )
        
        # Для QR-регистрации не проверяем hash (пользователь уже подтвердил через бота)
        first_name = auth_data.get("first_name", "")
        last_name = auth_data.get("last_name", "")
        username = auth_data.get("username")
        full_name = f"{first_name} {last_name}".strip() or first_name
        
        logger.info(f"Registration via QR token for telegram_id: {telegram_id} (simplified - no hash check)")
    else:
        # Обычная регистрация через Telegram WebApp
        auth_data = registration.telegram_auth.model_dump()
        
        logger.info(f"Registration attempt for telegram_id: {auth_data.get('id')}, hash present: {bool(auth_data.get('hash'))}, auth_date: {auth_data.get('auth_date')}")
        
        # Проверяем hash только для обычной регистрации (не через QR)
        if not verify_telegram_auth(auth_data):
            logger.warning(f"Telegram auth verification failed for telegram_id: {auth_data.get('id')}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram authentication data. Please open this page through Telegram bot."
            )
        
        telegram_id = auth_data.get("id")
        first_name = auth_data.get("first_name", "")
        last_name = auth_data.get("last_name", "")
        username = auth_data.get("username")
        
        full_name = f"{first_name} {last_name}".strip() or first_name
    
    # Общая логика для обоих случаев (QR и обычная регистрация)
    
    # Проверяем, не зарегистрирован ли уже пользователь
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )
    
    # Создаём нового пользователя
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        is_active=False,  # Требует модерации
        personal_data_consent=True,
        consent_date=now,
        user_agreement_accepted=True,
        agreement_version=registration.user_agreement.version or "1.0",
        agreement_accepted_at=now
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Создаём заявку на модерацию
    from app.services.moderation_service import ModerationService
    application = await ModerationService.create_user_application(
        db=db,
        user_id=user.id,
        application_data={
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "source": "qr_registration" if registration.qr_token else "registration",
            "consent_date": now.isoformat(),
            "agreement_version": registration.user_agreement.version or "1.0"
        }
    )
    
    # Уведомляем админов о новой заявке
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_moderation_request(
            db=db,
            user_id=user.id,
            user_name=full_name,
            user_telegram_id=telegram_id
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send moderation request notification: {e}")
    
    # Создаём JWT токен (пользователь может пользоваться системой, но не может брать задачи до модерации)
    access_token = create_access_token(data={"sub": str(user.id), "telegram_id": telegram_id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "telegram_id": user.telegram_id,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "role": user.role.value
        },
        "message": "Регистрация успешна! Ваша заявка отправлена на модерацию. Вы можете просматривать задачи, но не сможете брать их до одобрения."
    }


@router.post("/request-code", response_model=dict)
async def request_registration_code(
    request: RegistrationCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Запросить код регистрации через Telegram бота
    
    Пользователь указывает свой Telegram ID или username,
    система отправляет код в бот
    """
    import logging
    logger = logging.getLogger(__name__)
    
    telegram_id = request.telegram_id
    telegram_username = request.telegram_username
    
    # Если указан только username (для незарегистрированных пользователей username не будет в БД)
    # Нужно обязательно telegram_id для отправки сообщения
    # Telegram Bot API не позволяет отправлять сообщения по username без chat_id
    if not telegram_id and telegram_username:
        # Если указан только username без ID, нужно попросить пользователя указать ID
        # Для незарегистрированных пользователей username не будет в системе
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для запроса кода необходимо указать ваш Telegram ID. "
                   "Вы можете узнать его, начав диалог с ботом @BESTPRSystemBot или используя бота @userinfobot. "
                   "Если у вас есть username, используйте его вместе с ID (бот автоматически определит формат ввода)."
        )
    
    if not telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо указать Telegram ID. Вы можете узнать его, начав диалог с ботом @BESTPRSystemBot или используя бота @userinfobot"
        )
    
    # Очищаем username от @ если есть
    if telegram_username:
        telegram_username = telegram_username.lstrip('@')
    else:
        telegram_username = None
    
    # Проверяем, не зарегистрирован ли уже пользователь
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже зарегистрирован"
        )
    
    # Проверяем, что пользователь начал диалог с ботом (пытаемся отправить тестовое сообщение)
    # Если это не удастся, пользователь не начал диалог с ботом
    try:
        # Пробуем отправить тестовое сообщение (если бот не может отправить - пользователь не начал диалог)
        test_sent = await send_telegram_message(
            telegram_id,
            "🔐 Подготовка кода регистрации...",
            silent_fail=True  # Не логируем ошибку, просто проверяем
        )
        if not test_sent:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Не удалось отправить сообщение в Telegram. Убедитесь, что вы начали диалог с ботом @BESTPRSystemBot. "
                       f"Нажмите /start в боте, чтобы начать диалог."
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to test send message to telegram_id={telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Не удалось отправить сообщение в Telegram. Убедитесь, что вы начали диалог с ботом @BESTPRSystemBot. "
                   f"Нажмите /start в боте, чтобы начать диалог."
        )
    
    # Генерируем код
    code = RegistrationCodeService.create_code(
        telegram_id=telegram_id,
        telegram_username=telegram_username
    )
    
    # Отправляем код в Telegram
    message = (
        f"🔐 <b>Код регистрации в BEST PR System</b>\n\n"
        f"Ваш код подтверждения: <code>{code}</code>\n\n"
        f"⏰ Код действителен в течение {RegistrationCodeService.CODE_EXPIRY_MINUTES} минут.\n\n"
        f"📝 Введите этот код на сайте для завершения регистрации:\n"
        f"🔗 {settings.FRONTEND_URL}/register\n\n"
        f"💡 Если вы не запрашивали этот код, просто проигнорируйте это сообщение."
    )
    
    sent = await send_telegram_message(telegram_id, message)
    
    if not sent:
        logger.error(f"Failed to send registration code to telegram_id={telegram_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось отправить код в Telegram. Убедитесь, что вы начали диалог с ботом @BESTPRSystemBot. Нажмите /start в боте."
        )
    
    logger.info(f"Registration code sent to telegram_id={telegram_id}")
    
    return {
        "message": f"Код отправлен в Telegram бот. Проверьте сообщения от @BESTPRSystemBot",
        "expires_in_minutes": RegistrationCodeService.CODE_EXPIRY_MINUTES
    }


@router.post("/register-with-code", response_model=dict)
async def register_with_code(
    request: RegistrationCodeVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация с кодом подтверждения из Telegram бота
    
    Пользователь вводит код, полученный в боте
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Проверяем согласие
    if not request.personal_data_consent.consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Согласие на обработку персональных данных обязательно"
        )
    
    if not request.user_agreement.accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо принять пользовательское соглашение"
        )
    
    # Проверяем код
    code_data = RegistrationCodeService.verify_code(request.code)
    
    if not code_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный или истёкший код. Запросите новый код."
        )
    
    telegram_id = code_data["telegram_id"]
    telegram_username = code_data.get("telegram_username")
    
    # Проверяем, не зарегистрирован ли уже пользователь
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь уже зарегистрирован"
        )
    
    # Получаем данные пользователя из Telegram (минимальные данные)
    # Для полной регистрации нужно будет получить данные через Telegram Bot API
    # Пока используем только telegram_id и username
    first_name = "Пользователь"  # Будет обновлено при первом входе через /start
    full_name = first_name
    
    # Создаём нового пользователя
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=telegram_username,
        full_name=full_name,
        is_active=False,  # Требует модерации
        personal_data_consent=True,
        consent_date=now,
        user_agreement_accepted=True,
        agreement_version=request.user_agreement.version or "1.0",
        agreement_accepted_at=now
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Создаём заявку на модерацию
    from app.services.moderation_service import ModerationService
    application = await ModerationService.create_user_application(
        db=db,
        user_id=user.id,
        application_data={
            "telegram_id": telegram_id,
            "username": telegram_username,
            "full_name": full_name,
            "source": "registration_with_code",
            "consent_date": now.isoformat(),
            "agreement_version": request.user_agreement.version or "1.0"
        }
    )
    
    # Уведомляем админов о новой заявке
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_moderation_request(
            db=db,
            user_id=user.id,
            user_name=full_name,
            user_telegram_id=telegram_id
        )
    except Exception as e:
        logger.error(f"Failed to send moderation request notification: {e}")
    
    # Создаём JWT токен
    access_token = create_access_token(data={"sub": str(user.id), "telegram_id": telegram_id})
    
    logger.info(f"User registered with code: telegram_id={telegram_id}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "telegram_id": user.telegram_id,
            "username": user.username,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "role": user.role.value
        },
        "message": "Регистрация успешна! Ваша заявка отправлена на модерацию. Вы можете просматривать задачи, но не сможете брать их до одобрения."
    }


class RegisterFromBotRequest(BaseModel):
    """Запрос на регистрацию из бота через QR-код"""
    qr_token: str
    full_name: Optional[str] = None  # ФИО пользователя


@router.post("/register-from-bot", response_model=dict)
async def register_from_bot(
    request: RegisterFromBotRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация через QR-код прямо из бота
    
    Пользователь нажал "Зарегистрироваться" в боте после сканирования QR-кода.
    Автоматически принимаются согласие и пользовательское соглашение.
    """
    from app.models.qr_session import QRSession
    from datetime import datetime, timezone
    
    # Находим QR-сессию
    result = await db.execute(
        select(QRSession).where(QRSession.session_token == request.qr_token)
    )
    qr_session = result.scalar_one_or_none()
    
    if not qr_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR session not found"
        )
    
    if qr_session.status != "confirmed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR session not confirmed. Please confirm QR code in Telegram bot first."
        )
    
    if not qr_session.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR session does not have telegram_id"
        )
    
    telegram_id = qr_session.telegram_id
    
    # Проверяем, не зарегистрирован ли уже пользователь
    user_result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = user_result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already registered"
        )
    
    # Получаем ФИО из запроса или используем минимальные данные
    if request.full_name:
        full_name = request.full_name.strip()
    else:
        full_name = "Пользователь"
    
    username = None
    
    # Создаём нового пользователя
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        is_active=False,  # Требует модерации
        personal_data_consent=True,
        consent_date=now,
        user_agreement_accepted=True,
        agreement_version="1.0",
        agreement_accepted_at=now
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Обновляем QR-сессию с user_id для автоматического входа после регистрации
    qr_session.user_id = user.id
    await db.commit()
    
    # Создаём заявку на модерацию
    from app.services.moderation_service import ModerationService
    application = await ModerationService.create_user_application(
        db=db,
        user_id=user.id,
        application_data={
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "source": "qr_bot_registration",
            "consent_date": now.isoformat(),
            "agreement_version": "1.0"
        }
    )
    
    # Отмечаем пользователя как зарегистрированного в OnboardingReminder
    from app.models.onboarding import OnboardingReminder
    reminder_result = await db.execute(
        select(OnboardingReminder).where(
            OnboardingReminder.telegram_id == str(telegram_id)
        )
    )
    reminder = reminder_result.scalar_one_or_none()
    if reminder:
        reminder.registered = True
        await db.commit()
    
    # Уведомляем админов о новой заявке
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_moderation_request(
            db=db,
            user_id=user.id,
            user_name=full_name,
            user_telegram_id=telegram_id
        )
    except Exception as e:
        logger.error(f"Failed to send moderation request notification: {e}")
    
    # Создаём JWT токен для автоматического входа (пользователь может пользоваться системой, но не может брать задачи до модерации)
    from app.utils.auth import create_access_token
    access_token = create_access_token(data={"sub": str(user.id), "telegram_id": telegram_id})
    
    logger.info(f"User registered from bot via QR: telegram_id={telegram_id}")
    
    return {
        "success": True,
        "message": "Регистрация успешна! Ваша заявка отправлена на модерацию.",
        "user_id": str(user.id),
        "telegram_id": telegram_id,
        "access_token": access_token  # Возвращаем токен для автоматического входа
    }


@router.get("/agreement", response_model=dict)
async def get_user_agreement():
    """
    Получить текст пользовательского соглашения
    
    Доступно всем (публичный endpoint)
    """
    # TODO: Загрузить из файла или базы данных
    # Пока возвращаем заглушку
    return {
        "version": "1.0",
        "title": "Пользовательское соглашение BEST PR System",
        "content": """
        ПОЛЬЗОВАТЕЛЬСКОЕ СОГЛАШЕНИЕ
        BEST Москва при МГТУ им. Н.Э. Баумана
        Система управления PR-отделом
        
        1. ОБЩИЕ ПОЛОЖЕНИЯ
        
        1.1. Настоящее Пользовательское соглашение определяет условия использования системы управления PR-отделом BEST Москва.
        
        1.2. Используя систему, Пользователь соглашается с условиями настоящего Соглашения.
        
        2. ПРАВА И ОБЯЗАННОСТИ ПОЛЬЗОВАТЕЛЯ
        
        2.1. Пользователь обязуется:
        - Соблюдать дедлайны задач
        - Предоставлять качественные результаты работы
        - Следовать инструкциям координаторов
        - Не передавать доступ к системе третьим лицам
        
        2.2. Пользователь имеет право:
        - Просматривать доступные задачи
        - Брать задачи (после одобрения модерации)
        - Предлагать концепты и идеи
        - Получать обратную связь от координаторов
        
        3. ОТВЕТСТВЕННОСТЬ
        
        3.1. Пользователь несёт ответственность за качество выполнения задач.
        
        3.2. В случае нарушения дедлайнов или некачественного выполнения могут применяться санкции.
        
        4. ОБРАБОТКА ПЕРСОНАЛЬНЫХ ДАННЫХ
        
        4.1. Персональные данные используются для управления задачами и связи с пользователем.
        
        4.2. Данные не передаются третьим лицам без согласия пользователя.
        
        5. ЗАКЛЮЧИТЕЛЬНЫЕ ПОЛОЖЕНИЯ
        
        5.1. Соглашение вступает в силу с момента регистрации.
        
        5.2. По всем вопросам обращайтесь в поддержку.
        """,
        "updated_at": "2026-01-07"
    }
