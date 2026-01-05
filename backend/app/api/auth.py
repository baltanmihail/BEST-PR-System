"""
API endpoints для аутентификации
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserCreate
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import get_current_user

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
            # Создаём нового пользователя
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
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
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication error: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Получить текущего пользователя"""
    return UserResponse.model_validate(current_user)
