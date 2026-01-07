"""
API endpoints для аутентификации
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserResponse, UserCreate
from app.utils.auth import create_access_token, verify_telegram_auth
from app.utils.permissions import get_current_user, require_vp4pr

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
            from app.models.user import UserRole
            # Явно передаём значение enum'а (строку), а не сам enum
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                role=UserRole.NOVICE,  # TypeDecorator сам конвертирует в "novice"
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


@router.get("/users", response_model=dict)
async def get_users(
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список пользователей (только для VP4PR)
    
    Используется для управления пользователями и удаления аккаунтов
    """
    from sqlalchemy import func, or_
    
    # Только VP4PR может видеть список пользователей
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only VP4PR can access user list"
        )
    
    # Исключаем удалённых пользователей
    query = select(User).where(
        User.deleted_at.is_(None)
    )
    
    # Поиск по имени или username
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                User.full_name.ilike(search_term),
                User.username.ilike(search_term)
            )
        )
    
    # Подсчёт общего количества
    count_query = select(func.count(User.id)).where(User.deleted_at.is_(None))
    if search:
        search_term = f"%{search}%"
        count_query = count_query.where(
            or_(
                User.full_name.ilike(search_term),
                User.username.ilike(search_term)
            )
        )
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Получаем пользователей
    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "items": [
            {
                "id": str(user.id),
                "telegram_id": user.telegram_id,
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role.value,
                "is_active": user.is_active,
                "points": user.points,
                "level": user.level,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.delete("/account/{user_id}", response_model=dict)
async def delete_account(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить аккаунт пользователя
    
    - Пользователь может удалить только свой аккаунт
    - VP4PR может удалить любой аккаунт
    """
    from app.models.user import UserRole
    from datetime import datetime, timezone
    from uuid import UUID
    
    try:
        target_user_id = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Проверяем права доступа
    is_vp4pr = current_user.role == UserRole.VP4PR
    is_own_account = current_user.id == target_user_id
    
    if not (is_vp4pr or is_own_account):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own account or must be VP4PR to delete other accounts"
        )
    
    # Получаем пользователя для удаления
    result = await db.execute(
        select(User).where(User.id == target_user_id)
    )
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Проверяем, не удалён ли уже аккаунт
    if target_user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is already deleted"
        )
    
    # Не позволяем удалять VP4PR (кроме самого себя)
    if target_user.role == UserRole.VP4PR and not is_own_account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete VP4PR account"
        )
    
    # Сохраняем данные для уведомления до очистки
    deleted_user_name = target_user.full_name
    deleted_telegram_id = target_user.telegram_id
    
    # Выполняем мягкое удаление
    now = datetime.now(timezone.utc)
    target_user.deleted_at = now
    target_user.is_active = False  # Деактивируем аккаунт
    
    # Очищаем персональные данные (GDPR compliance)
    target_user.username = None
    target_user.full_name = f"Deleted User {target_user.id}"
    target_user.personal_data_consent = False
    target_user.user_agreement_accepted = False
    
    await db.commit()
    await db.refresh(target_user)
    
    logger.info(f"Account deleted: user_id={target_user_id}, deleted_by={current_user.id}, is_vp4pr={is_vp4pr}")
    
    # Если пользователь удалил свой аккаунт, отправляем уведомление админам
    if is_own_account:
        from app.services.notification_service import NotificationService
        from app.models.notification import NotificationType
        try:
            # Уведомляем VP4PR о удалении аккаунта
            vp4pr_result = await db.execute(
                select(User).where(
                    User.role == UserRole.VP4PR,
                    User.deleted_at.is_(None),
                    User.id != target_user_id  # Не уведомляем самого себя
                )
            )
            vp4pr_users = vp4pr_result.scalars().all()
            
            for admin in vp4pr_users:
                await NotificationService.create_notification(
                    db=db,
                    user_id=admin.id,
                    notification_type=NotificationType.SYSTEM,
                    title="Аккаунт удалён",
                    message=f"Пользователь {deleted_user_name} (Telegram ID: {deleted_telegram_id}) удалил свой аккаунт.",
                    data={"deleted_user_id": str(target_user_id)}
                )
        except Exception as e:
            logger.error(f"Failed to send account deletion notification: {e}")
    
    return {
        "message": "Account deleted successfully",
        "user_id": str(target_user_id),
        "deleted_at": now.isoformat()
    }
