"""
API endpoints для модерации
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.moderation import ModerationQueue, ModerationStatus
from app.services.moderation_service import ModerationService
from app.utils.permissions import get_current_user, require_coordinator
from pydantic import BaseModel

router = APIRouter(prefix="/moderation", tags=["moderation"])


class ApplicationData(BaseModel):
    """Данные заявки"""
    experience: Optional[str] = None
    direction: Optional[str] = None
    motivation: Optional[str] = None
    telegram_username: Optional[str] = None


class ModerationResponse(BaseModel):
    """Ответ с данными модерации"""
    id: str
    user_id: str
    user_name: str
    user_telegram_id: int
    application_data: dict
    status: str
    created_at: str
    decision_by: Optional[str] = None
    decision_at: Optional[str] = None


@router.post("/apply", response_model=dict)
async def create_application(
    application_data: ApplicationData,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создать заявку на регистрацию/активацию
    
    Доступно всем авторизованным пользователям
    """
    # Проверяем, активен ли уже пользователь
    if current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already active"
        )
    
    application = await ModerationService.create_user_application(
        db=db,
        user_id=current_user.id,
        application_data=application_data.model_dump()
    )
    
    return {
        "id": str(application.id),
        "status": application.status.value,
        "message": "Application submitted successfully"
    }


@router.get("/applications", response_model=dict)
async def get_applications(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[ModerationStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Получить список заявок на модерацию
    
    Доступно только координаторам и VP4PR
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    query = select(ModerationQueue).where(
        ModerationQueue.task_id.is_(None)  # Только заявки на регистрацию
    )
    
    if status_filter:
        query = query.where(ModerationQueue.status == status_filter)
    else:
        query = query.where(ModerationQueue.status == ModerationStatus.PENDING)
    
    query = query.options(selectinload(ModerationQueue.user)).order_by(
        ModerationQueue.created_at.desc()
    )
    
    # Подсчёт общего количества
    from sqlalchemy import func
    count_query = select(func.count(ModerationQueue.id)).where(
        ModerationQueue.task_id.is_(None)
    )
    if status_filter:
        count_query = count_query.where(ModerationQueue.status == status_filter)
    else:
        count_query = count_query.where(ModerationQueue.status == ModerationStatus.PENDING)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()
    
    # Получаем заявки
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    applications = result.scalars().all()
    
    return {
        "items": [
            {
                "id": str(app.id),
                "user_id": str(app.user_id),
                "user_name": app.user.full_name,
                "user_telegram_id": app.user.telegram_id,
                "application_data": app.application_data,
                "status": app.status.value,
                "created_at": app.created_at.isoformat(),
                "decision_by": str(app.decision_by) if app.decision_by else None,
                "decision_at": app.decision_at.isoformat() if app.decision_at else None
            }
            for app in applications
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/applications/{application_id}/approve", response_model=dict)
async def approve_application(
    application_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Одобрить заявку пользователя
    
    Доступно только координаторам и VP4PR
    """
    application = await ModerationService.approve_user_application(
        db=db,
        application_id=application_id,
        moderator_id=current_user.id
    )
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found or already processed"
        )
    
    # Уведомляем пользователя об одобрении
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_moderation_approved(
            db=db,
            user_id=application.user_id
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send notification: {e}")
    
    return {
        "id": str(application.id),
        "status": application.status.value,
        "message": "Application approved successfully"
    }


@router.post("/applications/{application_id}/reject", response_model=dict)
async def reject_application(
    application_id: UUID,
    reason: str = Query(..., description="Причина отклонения"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Отклонить заявку пользователя
    
    Доступно только координаторам и VP4PR
    """
    application = await ModerationService.reject_user_application(
        db=db,
        application_id=application_id,
        moderator_id=current_user.id,
        reason=reason
    )
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found or already processed"
        )
    
    # Уведомляем пользователя об отклонении
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_moderation_rejected(
            db=db,
            user_id=application.user_id,
            reason=reason
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send notification: {e}")
    
    return {
        "id": str(application.id),
        "status": application.status.value,
        "message": "Application rejected"
    }


@router.get("/my-application", response_model=dict)
async def get_my_application(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить мою заявку на регистрацию
    
    Доступно всем авторизованным пользователям
    """
    application = await ModerationService.get_user_application(
        db=db,
        user_id=current_user.id
    )
    
    if not application:
        return {
            "status": "not_found",
            "message": "No application found"
        }
    
    return {
        "id": str(application.id),
        "status": application.status.value,
        "application_data": application.application_data,
        "created_at": application.created_at.isoformat(),
        "decision_at": application.decision_at.isoformat() if application.decision_at else None
    }
