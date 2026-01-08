"""
API endpoints для QR-код авторизации
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
import secrets
import io
import base64
import logging

# Импорт qrcode с обработкой ошибок
try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False
    logging.warning("qrcode module not available. QR code generation will be disabled.")

from app.database import get_db
from app.models.qr_session import QRSession
from app.models.user import User
from app.utils.auth import create_access_token
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth/qr", tags=["qr-auth"])


class QRGenerateResponse(BaseModel):
    """Ответ на генерацию QR-кода"""
    session_id: str
    qr_code: str  # Base64 encoded QR code image
    session_token: str
    expires_at: datetime


class QRStatusResponse(BaseModel):
    """Статус QR-сессии"""
    status: str  # pending, confirmed, expired, cancelled
    session_id: str
    session_token: Optional[str] = None
    access_token: Optional[str] = None
    user: Optional[dict] = None


class QRConfirmRequest(BaseModel):
    """Запрос на подтверждение QR-кода из бота"""
    session_token: str
    telegram_id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None


@router.post("/generate", response_model=QRGenerateResponse)
async def generate_qr(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Генерирует QR-код для авторизации
    
    Пользователь открывает эту страницу, получает QR-код,
    сканирует его через Telegram бота, подтверждает вход
    """
    if not QRCODE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QR code generation is not available. Please install qrcode and Pillow packages."
        )
    
    # Генерируем уникальный токен сессии
    session_token = secrets.token_urlsafe(32)
    
    # Создаём сессию (действительна 5 минут)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    qr_session = QRSession(
        session_token=session_token,
        status="pending",
        expires_at=expires_at,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    db.add(qr_session)
    await db.commit()
    await db.refresh(qr_session)
    
    # Формируем URL для QR-кода
    # Формат: bestpr://auth?token=TOKEN
    qr_data = f"bestpr://auth?token={session_token}"
    
    # Генерируем QR-код
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Создаём изображение
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Конвертируем в base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    logger.info(f"QR session generated: {qr_session.id} (token: {session_token[:8]}...)")
    
    return QRGenerateResponse(
        session_id=str(qr_session.id),
        qr_code=f"data:image/png;base64,{qr_code_base64}",
        session_token=session_token,
        expires_at=expires_at
    )


@router.get("/status/{session_token}", response_model=QRStatusResponse)
async def get_qr_status(
    session_token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Проверяет статус QR-сессии по токену
    
    Фронтенд опрашивает этот endpoint для проверки статуса
    """
    result = await db.execute(
        select(QRSession).where(QRSession.session_token == session_token)
    )
    qr_session = result.scalar_one_or_none()
    
    if not qr_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR session not found"
        )
    
    # Проверяем, не истекла ли сессия
    if qr_session.is_expired() and qr_session.status == "pending":
        qr_session.status = "expired"
        await db.commit()
    
    response = QRStatusResponse(
        status=qr_session.status,
        session_id=str(qr_session.id),
        session_token=session_token
    )
    
    # Если сессия подтверждена, возвращаем токен и данные пользователя
    if qr_session.status == "confirmed" and qr_session.user_id:
        # Получаем пользователя
        user_result = await db.execute(
            select(User).where(User.id == qr_session.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if user:
            # Создаём JWT токен
            access_token = create_access_token(
                data={"sub": str(user.id), "telegram_id": user.telegram_id}
            )
            
            response.access_token = access_token
            response.user = {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "role": user.role.value if hasattr(user.role, 'value') else str(user.role)
            }
    
    return response


@router.post("/confirm")
async def confirm_qr(
    request: QRConfirmRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Подтверждает QR-код авторизацию из Telegram бота
    
    Вызывается ботом после того, как пользователь подтвердил вход
    """
    # Находим сессию по токену
    result = await db.execute(
        select(QRSession).where(QRSession.session_token == request.session_token)
    )
    qr_session = result.scalar_one_or_none()
    
    if not qr_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR session not found"
        )
    
    # Проверяем статус
    if qr_session.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"QR session is already {qr_session.status}"
        )
    
    # Проверяем, не истекла ли сессия
    if qr_session.is_expired():
        qr_session.status = "expired"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR session expired"
        )
    
    # Находим или создаём пользователя
    user_result = await db.execute(
        select(User).where(User.telegram_id == request.telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        # Создаём нового пользователя (неактивного, требует модерации)
        from app.models.user import UserRole
        full_name = f"{request.first_name} {request.last_name or ''}".strip() or request.first_name
        
        user = User(
            telegram_id=request.telegram_id,
            username=request.username,
            full_name=full_name,
            role=UserRole.NOVICE,
            is_active=False,  # Требует модерации
            personal_data_consent=False,
            user_agreement_accepted=False
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
                "telegram_id": request.telegram_id,
                "username": request.username,
                "full_name": full_name,
                "source": "qr_auth"
            }
        )
        
        # Уведомляем админов
        from app.services.notification_service import NotificationService
        try:
            await NotificationService.notify_moderation_request(
                db=db,
                user_id=user.id,
                user_name=full_name,
                user_telegram_id=request.telegram_id
            )
        except Exception as e:
            logger.error(f"Failed to send moderation request notification: {e}")
    else:
        # Обновляем данные существующего пользователя
        user.username = request.username
        user.full_name = f"{request.first_name} {request.last_name or ''}".strip() or request.first_name
        await db.commit()
        await db.refresh(user)
    
    # Обновляем сессию
    qr_session.status = "confirmed"
    qr_session.telegram_id = request.telegram_id
    qr_session.user_id = user.id
    qr_session.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info(f"QR session confirmed: {qr_session.id} for user {user.telegram_id}")
    
    return {
        "success": True,
        "message": "QR session confirmed",
        "user_id": str(user.id)
    }
