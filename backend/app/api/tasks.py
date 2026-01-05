"""
API endpoints для задач
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.task import TaskType, TaskStatus, TaskPriority
from app.schemas.task import (
    TaskResponse, TaskDetailResponse, TaskCreate, TaskUpdate
)
from app.services.task_service import TaskService
from app.utils.permissions import get_current_user, require_coordinator

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=dict)
async def get_tasks(
    skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
    limit: int = Query(100, ge=1, le=100, description="Количество записей"),
    task_type: Optional[TaskType] = Query(None, description="Фильтр по типу задачи"),
    status: Optional[TaskStatus] = Query(None, description="Фильтр по статусу"),
    priority: Optional[TaskPriority] = Query(None, description="Фильтр по приоритету"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список задач с фильтрацией и пагинацией
    
    Доступно всем авторизованным пользователям
    """
    tasks, total = await TaskService.get_tasks(
        db=db,
        skip=skip,
        limit=limit,
        task_type=task_type,
        status=status,
        priority=priority
    )
    
    return {
        "items": [TaskResponse.model_validate(task) for task in tasks],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить детали задачи по ID
    
    Доступно всем авторизованным пользователям
    """
    task = await TaskService.get_task_by_id(db, task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    return TaskDetailResponse.model_validate(task)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать новую задачу
    
    Доступно только координаторам и VP4PR
    """
    task = await TaskService.create_task(
        db=db,
        task_data=task_data,
        created_by=current_user.id
    )
    
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить задачу
    
    Доступно создателю задачи или координаторам
    """
    task = await TaskService.update_task(
        db=db,
        task_id=task_id,
        task_data=task_data,
        current_user=current_user
    )
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you don't have permission to update it"
        )
    
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удалить задачу
    
    Доступно создателю задачи или VP4PR
    """
    success = await TaskService.delete_task(
        db=db,
        task_id=task_id,
        current_user=current_user
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you don't have permission to delete it"
        )
    
    return None
