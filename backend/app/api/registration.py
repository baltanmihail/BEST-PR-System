"""
API endpoints для регистрации с согласием и пользовательским соглашением
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.schemas.auth import TelegramAuthData, PersonalDataConsent, UserAgreementAccept
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import OptionalUser

router = APIRouter(prefix="/registration", tags=["registration"])


class RegistrationRequest(BaseModel):
    """Запрос на регистрацию"""
    telegram_auth: TelegramAuthData
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
    
    # Валидация данных Telegram
    auth_data = registration.telegram_auth.model_dump()
    
    # Логируем для отладки (без чувствительных данных)
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Registration attempt for telegram_id: {auth_data.get('id')}, hash present: {bool(auth_data.get('hash'))}, auth_date: {auth_data.get('auth_date')}")
    
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
            "source": "registration",
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
