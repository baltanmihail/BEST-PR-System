"""
API endpoints для аутентификации
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/telegram", response_model=dict)
async def auth_telegram(
    auth_data: dict,
    db: AsyncSession = Depends(get_db)
):
    """
    Авторизация через Telegram
    
    Принимает данные от Telegram Web App:
    - id: Telegram user ID
    - first_name: Имя
    - last_name: Фамилия (опционально)
    - username: Username (опционально)
    - auth_date: Unix timestamp
    - hash: HMAC-SHA-256 hash
    """
    try:
        # Валидация данных Telegram
        if not verify_telegram_auth(auth_data):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram authentication data"
            )
        
        telegram_id = auth_data.get("id")
        first_name = auth_data.get("first_name", "")
        last_name = auth_data.get("last_name", "")
        username = auth_data.get("username")
        
        full_name = f"{first_name} {last_name}".strip() or first_name
        
        # Поиск или создание пользователя
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            # Создаём нового пользователя (неактивного, требует модерации)
            # Согласие и пользовательское соглашение будут добавлены позже через отдельный endpoint
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
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
                    "telegram_id": telegram_id,
                    "username": username,
                    "full_name": full_name,
                    "source": "telegram_auth"
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
        else:
            # Обновляем данные существующего пользователя
            user.username = username
            user.full_name = full_name
            await db.commit()
            await db.refresh(user)
        
        # Создаём JWT токен
        access_token = create_access_token(data={"sub": str(user.id), "telegram_id": telegram_id})
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = str(e) if str(e) else "Unknown error"
        logger.error(f"Auth error: {error_detail}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {error_detail}"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Получить текущего пользователя"""
    return UserResponse.model_validate(current_user)
