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
from app.models.user import User, UserRole
from app.schemas.auth import TelegramAuthData, PersonalDataConsent, UserAgreementAccept
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import OptionalUser
from app.services.registration_code_service import RegistrationCodeService
from app.utils.telegram_sender import send_telegram_message
from app.config import settings

router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationRequest(BaseModel):
    """Запрос на регистрацию"""
    telegram_auth: Optional[TelegramAuthData] = None  # Опционально для QR-регистрации
    personal_data_consent: PersonalDataConsent
    user_agreement: UserAgreementAccept
    qr_token: Optional[str] = None  # Опциональный токен QR-сессии для упрощённой регистрации
    full_name: str  # ОБЯЗАТЕЛЬНОЕ ФИО пользователя (должно быть указано вручную, не из Telegram)


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
    # Логируем для отладки
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔵 Registration attempt - qr_token: {registration.qr_token is not None}, telegram_auth: {registration.telegram_auth is not None}")
    logger.info(f"🔵 Registration data: personal_data_consent={registration.personal_data_consent.consent}, user_agreement={registration.user_agreement.accepted}")
    
    # Проверяем согласие
    if not registration.personal_data_consent.consent:
        logger.warning("Registration failed: personal_data_consent is False")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Согласие на обработку персональных данных обязательно"
        )
    
    if not registration.user_agreement.accepted:
        logger.warning("Registration failed: user_agreement not accepted")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо принять пользовательское соглашение"
        )
    
    # Если есть qr_token, используем данные из QR-сессии (упрощённая регистрация)
    if registration.qr_token:
        logger.info(f"🔵 QR registration path - token: {registration.qr_token[:20]}...")
        logger.info(f"🔵 QR token full length: {len(registration.qr_token)}")
        from app.models.qr_session import QRSession
        result = await db.execute(
            select(QRSession).where(QRSession.session_token == registration.qr_token)
        )
        qr_session = result.scalar_one_or_none()
        
        if not qr_session:
            logger.warning(f"QR session not found for token: {registration.qr_token[:20]}... (full token length: {len(registration.qr_token)})")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="QR session not found"
            )
        
        logger.info(f"QR session found: id={qr_session.id}, status={qr_session.status}, telegram_id={qr_session.telegram_id}")
        
        if qr_session.status != "confirmed":
            logger.warning(f"QR session not confirmed. Status: {qr_session.status}, token: {registration.qr_token[:20]}...")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR session not confirmed. Please confirm QR code in Telegram bot first."
            )
        
        if not qr_session.telegram_id:
            logger.error(f"QR session does not have telegram_id. Session ID: {qr_session.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="QR session does not have telegram_id"
            )
        
        # Используем telegram_id из QR-сессии
        telegram_id = qr_session.telegram_id
        
        # Для QR-регистрации telegram_auth опционален
        # Если передан - используем данные из него (WebApp может передать)
        # ВАЖНО: Для QR-регистрации hash НЕ проверяется (пользователь уже подтверждён через бота)
        username = None
        if registration.telegram_auth:
            auth_data = registration.telegram_auth.model_dump()
            logger.info(f"QR registration with telegram_auth: id={auth_data.get('id')}, hash present={bool(auth_data.get('hash'))}, hash value='{auth_data.get('hash', '')[:10]}...'")
            
            # Проверяем, что telegram_id совпадает (если передан)
            if auth_data.get("id") and auth_data.get("id") != telegram_id:
                logger.warning(f"Telegram ID mismatch: QR session has {telegram_id}, auth_data has {auth_data.get('id')}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Telegram ID mismatch between QR session and auth data"
                )
            # Используем только username из auth_data (не используем first_name/last_name для ФИО!)
            username = auth_data.get("username")
        else:
            logger.info(f"QR registration without telegram_auth")
        
        # ВАЖНО: ФИО ДОЛЖНО быть указано пользователем вручную, не используем данные из Telegram!
        # Данные из Telegram (first_name/last_name) могут быть неверными
        if not registration.full_name or not registration.full_name.strip():
            logger.error("full_name is required but not provided in registration request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ФИО обязательно для регистрации. Пожалуйста, укажите ваше полное имя."
            )
        
        full_name = registration.full_name.strip()
        logger.info(f"Registration via QR token for telegram_id: {telegram_id}, full_name: {full_name} (provided by user)")
    else:
        # Обычная регистрация через Telegram WebApp
        # Для обычной регистрации telegram_auth обязателен
        if not registration.telegram_auth:
            logger.error("Regular registration attempted without telegram_auth")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_auth is required for registration without QR token"
            )
        
        auth_data = registration.telegram_auth.model_dump()
        
        logger.info(f"🔵 Regular registration attempt for telegram_id: {auth_data.get('id')}, hash present: {bool(auth_data.get('hash'))}, auth_date: {auth_data.get('auth_date')}")
        logger.info(f"🔵 Full auth_data keys: {list(auth_data.keys())}, hash value: '{auth_data.get('hash', '')[:20]}...'")
        
        # Проверяем hash только для обычной регистрации (не через QR)
        verification_result = verify_telegram_auth(auth_data)
        logger.info(f"🔵 Telegram auth verification result: {verification_result}")
        if not verification_result:
            logger.warning(f"❌ Telegram auth verification failed for telegram_id: {auth_data.get('id')}")
            logger.warning(f"❌ Auth data: id={auth_data.get('id')}, hash_present={bool(auth_data.get('hash'))}, hash_value='{auth_data.get('hash', '')[:20]}...', auth_date={auth_data.get('auth_date')}")
            logger.warning(f"❌ TELEGRAM_BOT_TOKEN configured: {bool(settings.TELEGRAM_BOT_TOKEN)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram authentication data. Please open this page through Telegram bot."
            )
        
        telegram_id = auth_data.get("id")
        if not telegram_id:
            logger.error("telegram_auth provided but id is missing")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="telegram_auth.id is required"
            )
        
        username = auth_data.get("username")
        
        # ВАЖНО: ФИО ДОЛЖНО быть указано пользователем вручную, не используем данные из Telegram!
        # Данные из Telegram (first_name/last_name) могут быть неверными
        if not registration.full_name or not registration.full_name.strip():
            logger.error("full_name is required but not provided in registration request")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ФИО обязательно для регистрации. Пожалуйста, укажите ваше полное имя."
            )
        
        full_name = registration.full_name.strip()
        logger.info(f"Regular registration for telegram_id: {telegram_id}, full_name: {full_name} (provided by user)")
    
    # Общая логика для обоих случаев (QR и обычная регистрация)
    
    # ВАЖНО: Проверяем, является ли пользователь VP4PR (из TELEGRAM_ADMIN_IDS)
    # Если да - создаём пользователя сразу активным с ролью VP4PR без модерации
    is_vp4pr = telegram_id in (settings.TELEGRAM_ADMIN_IDS or [])
    logger.info(f"User telegram_id {telegram_id} is VP4PR: {is_vp4pr}")
    
    # Проверяем, не зарегистрирован ли уже пользователь
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    existing_user = result.scalar_one_or_none()
    
    now = datetime.now(timezone.utc)
    existing_application = None  # Инициализируем переменную
    user = None  # Инициализируем переменную
    
    if existing_user:
        # Если пользователь уже существует, проверяем статус
        if existing_user.is_active:
            # Пользователь уже активен - не нужно регистрироваться заново
            logger.info(f"User with telegram_id {telegram_id} already exists and is active (user_id: {existing_user.id})")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already registered and active. Please login instead."
            )
        
        # Пользователь существует, но не активен - обновляем данные и создаём новую заявку на модерацию
        # ВАЖНО: Если пользователь VP4PR - активируем его сразу без модерации
        logger.info(f"User with telegram_id {telegram_id} exists but is inactive - updating data (user_id: {existing_user.id}, is_vp4pr: {is_vp4pr})")
        
        # Обновляем данные пользователя
        existing_user.username = username
        existing_user.full_name = full_name
        existing_user.personal_data_consent = True
        existing_user.consent_date = now
        existing_user.user_agreement_accepted = True
        existing_user.agreement_version = registration.user_agreement.version or "1.0"
        existing_user.agreement_accepted_at = now
        
        # Если пользователь VP4PR - активируем его сразу и устанавливаем роль
        if is_vp4pr:
            existing_user.is_active = True
            existing_user.role = UserRole.VP4PR
            logger.info(f"User {telegram_id} is VP4PR - activating immediately and setting role to VP4PR")
        
        user = existing_user
        await db.commit()
        await db.refresh(user)
        
        # Создаём заявку на модерацию ТОЛЬКО если пользователь НЕ VP4PR
        if not is_vp4pr:
            # Проверяем, есть ли уже активная заявка на модерацию
            from app.services.moderation_service import ModerationService
            from app.models.moderation import ModerationQueue, ModerationStatus
            
            existing_application_result = await db.execute(
                select(ModerationQueue).where(
                    ModerationQueue.user_id == user.id,
                    ModerationQueue.status == ModerationStatus.PENDING,
                    ModerationQueue.task_id.is_(None)  # Заявка на регистрацию (не на задачу)
                )
            )
            existing_application = existing_application_result.scalar_one_or_none()
            
            if not existing_application:
                # Создаём новую заявку на модерацию только если нет активной заявки
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
            else:
                logger.info(f"Active moderation application already exists for user {user.id}, skipping creation")
                application = existing_application
        else:
            logger.info(f"User {telegram_id} is VP4PR - skipping moderation request")
            existing_application = None
            application = None  # Нет заявки на модерацию для VP4PR
    else:
        # Создаём нового пользователя
        # ВАЖНО: Если пользователь VP4PR (в TELEGRAM_ADMIN_IDS), создаём его сразу активным с ролью VP4PR без модерации
        user = User(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            is_active=is_vp4pr,  # VP4PR сразу активен, остальные требуют модерации
            role=UserRole.VP4PR if is_vp4pr else UserRole.NOVICE,  # VP4PR получает роль сразу, остальные - novice
            personal_data_consent=True,
            consent_date=now,
            user_agreement_accepted=True,
            agreement_version=registration.user_agreement.version or "1.0",
            agreement_accepted_at=now
        )
        
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Создаём заявку на модерацию ТОЛЬКО если пользователь НЕ VP4PR
        if not is_vp4pr:
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
        else:
            logger.info(f"User {telegram_id} is VP4PR - skipping moderation request, user is immediately active")
            application = None  # Нет заявки на модерацию для VP4PR
    
    # Уведомляем админов о новой заявке (только если создали новую заявку на модерацию и пользователь НЕ VP4PR)
    # Если заявка уже существует - не отправляем повторное уведомление
    # VP4PR не требуют модерации, поэтому уведомления не отправляем
    if not is_vp4pr and (not existing_user or (existing_user and not existing_application)):
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
    elif is_vp4pr:
        logger.info(f"User {telegram_id} is VP4PR - skipping moderation notification")
    
    # Создаём JWT токен (пользователь может пользоваться системой, но не может брать задачи до модерации, если не VP4PR)
    access_token = create_access_token(data={"sub": str(user.id), "telegram_id": telegram_id})
    
    # Формируем сообщение в зависимости от статуса пользователя
    if is_vp4pr:
        success_message = "Регистрация успешна! Вы зарегистрированы как VP4PR и имеете полный доступ к системе."
    else:
        success_message = "Регистрация успешна! Ваша заявка отправлена на модерацию. Вы можете просматривать задачи, но не сможете брать их до одобрения."
    
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
        "message": success_message
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
    from app.services.agreement_service import AgreementService
    
    return AgreementService.get_agreement_content()
