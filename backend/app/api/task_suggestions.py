"""
API endpoints для предложений концептов и идей к задачам
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User, UserRole
from app.models.task import Task
from app.models.task_suggestion import TaskSuggestion, SuggestionType, SuggestionStatus
from app.models.notification import NotificationType
from app.utils.permissions import get_current_user, require_coordinator

router = APIRouter(prefix="/tasks/{task_id}/suggestions", tags=["task_suggestions"])


class SuggestionCreate(BaseModel):
    """Схема для создания предложения"""
    type: SuggestionType
    title: str
    content: str
    files: Optional[List[str]] = None  # Google Drive IDs


class SuggestionUpdate(BaseModel):
    """Схема для обновления предложения (только координаторы)"""
    status: Optional[SuggestionStatus] = None
    feedback: Optional[str] = None


class SuggestionResponse(BaseModel):
    """Схема ответа с предложением"""
    id: UUID
    task_id: UUID
    user_id: UUID
    user_name: str
    type: SuggestionType
    title: str
    content: str
    files: Optional[List[str]] = None
    status: SuggestionStatus
    feedback: Optional[str] = None
    ai_analysis: Optional[dict] = None
    created_at: str
    updated_at: str
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[str] = None
    
    class Config:
        from_attributes = True


@router.post("", response_model=SuggestionResponse, status_code=status.HTTP_201_CREATED)
async def create_suggestion(
    task_id: UUID,
    suggestion: SuggestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создать предложение концепта/идеи для задачи
    
    Доступно всем активным пользователям
    """
    # Проверяем, что задача существует
    task_query = select(Task).where(Task.id == task_id)
    task_result = await db.execute(task_query)
    task = task_result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Создаём предложение
    new_suggestion = TaskSuggestion(
        task_id=task_id,
        user_id=current_user.id,
        type=suggestion.type,
        title=suggestion.title,
        content=suggestion.content,
        files={"drive_ids": suggestion.files} if suggestion.files else None,
        status=SuggestionStatus.PENDING
    )
    
    db.add(new_suggestion)
    await db.commit()
    await db.refresh(new_suggestion)
    
    # Уведомляем координаторов о новом предложении
    from app.services.notification_service import NotificationService
    from app.models.user import UserRole
    
    coordinators_query = select(User).where(
        User.role.in_([
            UserRole.COORDINATOR_SMM,
            UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL,
            UserRole.COORDINATOR_PRFR,
            UserRole.VP4PR
        ])
    )
    coord_result = await db.execute(coordinators_query)
    coordinators = coord_result.scalars().all()
    
    for coordinator in coordinators:
        await NotificationService.create_notification(
            db=db,
            user_id=coordinator.id,
            notification_type=NotificationType.NEW_TASK,
            title="Новое предложение к задаче",
            message=f"Пользователь {current_user.full_name} предложил {suggestion.type.value} для задачи '{task.title}'",
            data={
                "task_id": str(task_id),
                "suggestion_id": str(new_suggestion.id),
                "suggestion_type": suggestion.type.value
            }
        )
    
    # Формируем ответ
    return SuggestionResponse(
        id=new_suggestion.id,
        task_id=new_suggestion.task_id,
        user_id=new_suggestion.user_id,
        user_name=current_user.full_name,
        type=new_suggestion.type,
        title=new_suggestion.title,
        content=new_suggestion.content,
        files=new_suggestion.files.get("drive_ids") if new_suggestion.files else None,
        status=new_suggestion.status,
        feedback=new_suggestion.feedback,
        ai_analysis=new_suggestion.ai_analysis,
        created_at=new_suggestion.created_at.isoformat(),
        updated_at=new_suggestion.updated_at.isoformat(),
        reviewed_by=new_suggestion.reviewed_by,
        reviewed_at=new_suggestion.reviewed_at.isoformat() if new_suggestion.reviewed_at else None
    )


@router.get("", response_model=List[SuggestionResponse])
async def get_suggestions(
    task_id: UUID,
    status_filter: Optional[SuggestionStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список предложений для задачи
    
    Доступно всем активным пользователям
    """
    query = select(TaskSuggestion).where(TaskSuggestion.task_id == task_id)
    
    if status_filter:
        query = query.where(TaskSuggestion.status == status_filter)
    
    query = query.order_by(TaskSuggestion.created_at.desc())
    
    result = await db.execute(query)
    suggestions = result.scalars().all()
    
    # Получаем имена пользователей
    user_ids = {s.user_id for s in suggestions}
    users_query = select(User).where(User.id.in_(user_ids))
    users_result = await db.execute(users_query)
    users = {u.id: u for u in users_result.scalars().all()}
    
    return [
        SuggestionResponse(
            id=s.id,
            task_id=s.task_id,
            user_id=s.user_id,
            user_name=users.get(s.user_id).full_name if users.get(s.user_id) else "Неизвестный",
            type=s.type,
            title=s.title,
            content=s.content,
            files=s.files.get("drive_ids") if s.files else None,
            status=s.status,
            feedback=s.feedback,
            ai_analysis=s.ai_analysis,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat(),
            reviewed_by=s.reviewed_by,
            reviewed_at=s.reviewed_at.isoformat() if s.reviewed_at else None
        )
        for s in suggestions
    ]


@router.patch("/{suggestion_id}", response_model=SuggestionResponse)
async def update_suggestion(
    task_id: UUID,
    suggestion_id: UUID,
    update: SuggestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Обновить предложение (одобрить/отклонить, добавить обратную связь)
    
    Доступно только координаторам и VP4PR
    """
    query = select(TaskSuggestion).where(
        and_(
            TaskSuggestion.id == suggestion_id,
            TaskSuggestion.task_id == task_id
        )
    )
    result = await db.execute(query)
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found"
        )
    
    # Обновляем статус и обратную связь
    if update.status:
        suggestion.status = update.status
        suggestion.reviewed_by = current_user.id
        from datetime import datetime, timezone
        suggestion.reviewed_at = datetime.now(timezone.utc)
    
    if update.feedback:
        suggestion.feedback = update.feedback
    
    await db.commit()
    await db.refresh(suggestion)
    
    # Уведомляем автора предложения
    from app.services.notification_service import NotificationService
    await NotificationService.create_notification(
        db=db,
        user_id=suggestion.user_id,
        notification_type=NotificationType.TASK_REVIEW,
        title="Обратная связь по вашему предложению",
        message=f"Координатор оставил обратную связь по вашему предложению '{suggestion.title}'",
        data={
            "suggestion_id": str(suggestion_id),
            "task_id": str(task_id),
            "status": suggestion.status.value
        }
    )
    
    # Получаем имя пользователя для ответа
    user_query = select(User).where(User.id == suggestion.user_id)
    user_result = await db.execute(user_query)
    user = user_result.scalar_one()
    
    return SuggestionResponse(
        id=suggestion.id,
        task_id=suggestion.task_id,
        user_id=suggestion.user_id,
        user_name=user.full_name,
        type=suggestion.type,
        title=suggestion.title,
        content=suggestion.content,
        files=suggestion.files.get("drive_ids") if suggestion.files else None,
        status=suggestion.status,
        feedback=suggestion.feedback,
        ai_analysis=suggestion.ai_analysis,
        created_at=suggestion.created_at.isoformat(),
        updated_at=suggestion.updated_at.isoformat(),
        reviewed_by=suggestion.reviewed_by,
        reviewed_at=suggestion.reviewed_at.isoformat() if suggestion.reviewed_at else None
    )
