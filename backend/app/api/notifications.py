"""
API endpoints для уведомлений
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.services.notification_service import NotificationService
from app.utils.permissions import get_current_user
from pydantic import BaseModel
import json

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    """Ответ с уведомлением"""
    id: str
    type: str
    title: str
    message: str
    data: Optional[dict] = None
    is_read: bool
    created_at: str


@router.get("", response_model=dict)
async def get_notifications(
    unread_only: bool = Query(False, description="Только непрочитанные"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить мои уведомления
    
    Доступно всем авторизованным пользователям
    """
    notifications, total = await NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit
    )
    
    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "data": json.loads(n.data) if n.data else None,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ],
        "total": total,
        "unread_count": await NotificationService.get_unread_count(db, current_user.id),
        "skip": skip,
        "limit": limit
    }


@router.get("/unread-count", response_model=dict)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить количество непрочитанных уведомлений
    
    Доступно всем авторизованным пользователям
    """
    count = await NotificationService.get_unread_count(db, current_user.id)
    return {"unread_count": count}


@router.patch("/{notification_id}/read", response_model=dict)
async def mark_as_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Отметить уведомление как прочитанное
    
    Доступно всем авторизованным пользователям
    """
    import json
    notification = await NotificationService.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=current_user.id
    )
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {
        "id": str(notification.id),
        "is_read": notification.is_read,
        "message": "Notification marked as read"
    }


@router.post("/mark-all-read", response_model=dict)
async def mark_all_as_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Отметить все уведомления как прочитанные
    
    Доступно всем авторизованным пользователям
    """
    count = await NotificationService.mark_all_as_read(db, current_user.id)
    return {
        "marked_count": count,
        "message": f"Marked {count} notifications as read"
    }
