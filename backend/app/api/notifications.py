"""
API endpoints для уведомлений
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from uuid import UUID
import json

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification, NotificationType
from app.services.notification_service import NotificationService
from app.utils.permissions import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=dict)
async def get_notifications(
    unread_only: bool = Query(False, description="Только непрочитанные"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    important_only: bool = Query(False, description="Только важные"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список уведомлений пользователя
    
    Доступно всем авторизованным пользователям
    """
    notifications, total = await NotificationService.get_user_notifications(
        db=db,
        user_id=current_user.id,
        unread_only=unread_only,
        skip=skip,
        limit=limit
    )
    
    # Фильтр по важности
    important_types = [
        NotificationType.MODERATION_REQUEST,
        NotificationType.SUPPORT_REQUEST,
        NotificationType.TASK_DEADLINE,
        NotificationType.MODERATION_APPROVED,
        NotificationType.MODERATION_REJECTED
    ]
    
    if important_only:
        notifications = [n for n in notifications if n.type in important_types]
        total = len(notifications)
    
    # Группировка по важности
    important = [n for n in notifications if n.type in important_types]
    regular = [n for n in notifications if n.type not in important_types]
    
    return {
        "items": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "data": json.loads(n.data) if n.data else None,
                "is_read": n.is_read,
                "is_important": n.type in important_types,
                "created_at": n.created_at.isoformat()
            }
            for n in notifications
        ],
        "important": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "data": json.loads(n.data) if n.data else None,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat()
            }
            for n in important
        ],
        "regular": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "message": n.message,
                "data": json.loads(n.data) if n.data else None,
                "is_read": n.is_read,
                "created_at": n.created_at.isoformat()
            }
            for n in regular
        ],
        "total": total,
        "unread_count": await NotificationService.get_unread_count(db, current_user.id),
        "important_count": len(important),
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
    
    # Подсчитываем важные непрочитанные
    important_types = [
        NotificationType.MODERATION_REQUEST,
        NotificationType.SUPPORT_REQUEST,
        NotificationType.TASK_DEADLINE,
        NotificationType.MODERATION_APPROVED,
        NotificationType.MODERATION_REJECTED
    ]
    
    query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.is_read == False,
            Notification.type.in_(important_types)
        )
    )
    result = await db.execute(query)
    important_count = result.scalar() or 0
    
    return {
        "unread_count": count,
        "important_unread_count": important_count
    }


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
