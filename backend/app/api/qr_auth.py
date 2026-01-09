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

# Создаём logger перед использованием
logger = logging.getLogger(__name__)

# Импорт qrcode с обработкой ошибок
try:
    import qrcode
    from PIL import Image
    QRCODE_AVAILABLE = True
    logger.info("✅ QR code module loaded successfully")
except ImportError as e:
    QRCODE_AVAILABLE = False
    logger.error(f"❌ QR code module not available: {e}")
    logger.error("Please ensure qrcode and Pillow are installed with system dependencies")

from app.database import get_db
from app.models.qr_session import QRSession
from app.models.user import User
from app.utils.auth import create_access_token
from app.config import settings
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
    
    Если пользователь перешёл через бота (параметр ?from=bot&telegram_id=...),
    QR-код будет содержать данные пользователя для упрощённой регистрации
    """
    if not QRCODE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="QR code generation is not available. Please install qrcode and Pillow packages."
        )
    
    # Проверяем, перешёл ли пользователь через бота
    query_params = dict(request.query_params)
    from_bot = query_params.get("from") == "bot"
    telegram_id = query_params.get("telegram_id")
    telegram_username = query_params.get("username")
    first_name = query_params.get("first_name")
    
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
    
    # Если пользователь перешёл через бота, сохраняем его данные в сессии
    if from_bot and telegram_id:
        try:
            qr_session.telegram_id = int(telegram_id)
        except (ValueError, TypeError):
            pass
    
    db.add(qr_session)
    await db.commit()
    await db.refresh(qr_session)
    
    # Формируем URL для QR-кода
    # Используем HTTPS ссылку на бота для совместимости с камерами (iPhone, Android)
    # Формат: https://t.me/BESTPRSystemBot?start=qr_TOKEN
    # Если есть данные пользователя, добавляем их в параметр start
    bot_username = "BESTPRSystemBot"  # TODO: можно получать из настроек или Bot API
    if from_bot and telegram_id:
        # Для упрощённой регистрации передаём данные в параметре start
        start_param = f"qr_{session_token}_{telegram_id}"
        if telegram_username:
            start_param += f"_{telegram_username}"
        qr_data = f"https://t.me/{bot_username}?start={start_param}"
    else:
        # Обычный QR-код для входа
        qr_data = f"https://t.me/{bot_username}?start=qr_{session_token}"
    
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
    
    # Если сессия подтверждена, возвращаем токен и данные пользователя ТОЛЬКО если пользователь зарегистрирован
    # Если user_id не установлен - это незарегистрированный пользователь, не возвращаем токен
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
    # Если сессия confirmed, но user_id нет - это незарегистрированный пользователь
    # Фронтенд должен перенаправить на регистрацию
    
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
    
    # Находим пользователя
    user_result = await db.execute(
        select(User).where(User.telegram_id == request.telegram_id)
    )
    user = user_result.scalar_one_or_none()
    
    # Обновляем сессию
    qr_session.status = "confirmed"
    qr_session.telegram_id = request.telegram_id
    qr_session.confirmed_at = datetime.now(timezone.utc)
    
    if user:
        # Пользователь уже существует - это вход
        qr_session.user_id = user.id
        
        # Обновляем данные существующего пользователя
        user.username = request.username
        user.full_name = f"{request.first_name} {request.last_name or ''}".strip() or request.first_name
        await db.commit()
        await db.refresh(user)
        
        # Создаём JWT токен для входа
        access_token = create_access_token(
            data={"sub": str(user.id), "telegram_id": user.telegram_id}
        )
        
        logger.info(f"QR session confirmed (login): {qr_session.id} for existing user {user.telegram_id}")
        
        return {
            "success": True,
            "message": "QR session confirmed",
            "user_id": str(user.id),
            "is_registration": False,
            "access_token": access_token  # Возвращаем токен для автоматического входа
        }
    else:
        # Пользователь не существует - это регистрация
        # НЕ создаём пользователя здесь - он будет создан при регистрации через /registration/register-from-bot
        # НЕ устанавливаем user_id в сессии - он будет установлен после регистрации
        # Это важно, чтобы фронтенд понимал, что пользователь не зарегистрирован
        await db.commit()
        
        logger.info(f"QR session confirmed (registration): {qr_session.id} for new user {request.telegram_id}")
        
        return {
            "success": True,
            "message": "QR session confirmed. Please complete registration in bot.",
            "is_registration": True,
            "user_data": {
                "telegram_id": request.telegram_id,
                "username": request.username,
                "first_name": request.first_name,
                "last_name": request.last_name,
                "full_name": f"{request.first_name} {request.last_name or ''}".strip() or request.first_name
            }
        }
