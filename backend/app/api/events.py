"""
API endpoints для мероприятий
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.task import TaskResponse
from app.services.event_service import EventService
from app.utils.permissions import get_current_user

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=dict)
async def get_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список мероприятий
    
    Доступно всем авторизованным пользователям
    """
    events, total = await EventService.get_events(db, skip=skip, limit=limit)
    
    return {
        "items": [
            {
                "id": str(event.id),
                "name": event.name,
                "date_start": event.date_start.isoformat() if event.date_start else None,
                "date_end": event.date_end.isoformat() if event.date_end else None,
                "priority": event.priority,
                "description": event.description,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{event_id}/tasks", response_model=List[TaskResponse])
async def get_event_tasks(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить задачи мероприятия
    
    Доступно всем авторизованным пользователям
    """
    # Проверяем, что мероприятие существует
    event = await EventService.get_event_by_id(db, event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    tasks = await EventService.get_event_tasks(db, event_id)
    return [TaskResponse.model_validate(task) for task in tasks]
