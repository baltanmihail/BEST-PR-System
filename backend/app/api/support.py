"""
API endpoints для системы поддержки
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.services.notification_service import NotificationService
from app.utils.permissions import get_current_user, OptionalUser

router = APIRouter(prefix="/support", tags=["support"])


class SupportRequest(BaseModel):
    """Запрос в поддержку"""
    message: str
    contact: Optional[str] = None  # Telegram username или email для неавторизованных
    category: Optional[str] = None  # Тип вопроса (опционально)


@router.post("/request", response_model=dict)
async def create_support_request(
    request: SupportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Создать запрос в поддержку
    
    Доступно всем (авторизованным и неавторизованным)
    """
    # Определяем контакт
    contact_info = None
    user_name = "Неизвестный пользователь"
    
    if current_user:
        user_name = current_user.full_name
        contact_info = f"Telegram: @{current_user.username or current_user.telegram_id}"
    elif request.contact:
        contact_info = request.contact
    else:
        contact_info = "Контакт не указан"
    
    # Находим всех координаторов и VP4PR для уведомления
    from app.models.user import UserRole
    admins_query = select(User).where(
        User.role.in_([
            UserRole.COORDINATOR_SMM,
            UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL,
            UserRole.COORDINATOR_PRFR,
            UserRole.VP4PR
        ])
    )
    admins_result = await db.execute(admins_query)
    admins = admins_result.scalars().all()
    
    # Отправляем уведомление всем админам
    for admin in admins:
        await NotificationService.create_notification(
            db=db,
            user_id=admin.id,
            notification_type=NotificationType.SUPPORT_REQUEST,
            title="Новый запрос в поддержку",
            message=f"От: {user_name}\nКонтакт: {contact_info}\n\n{request.message}",
            data={
                "user_id": str(current_user.id) if current_user else None,
                "user_name": user_name,
                "contact": contact_info,
                "category": request.category,
                "message": request.message
            }
        )
    
    # Если пользователь авторизован, отправляем ему подтверждение
    if current_user:
        await NotificationService.create_notification(
            db=db,
            user_id=current_user.id,
            notification_type=NotificationType.SUPPORT_REQUEST,
            title="Запрос отправлен",
            message="Ваш запрос в поддержку получен. Мы ответим вам в ближайшее время.",
            data={"status": "sent"}
        )
    
    return {
        "status": "success",
        "message": "Ваш запрос отправлен. Мы свяжемся с вами в ближайшее время."
    }
