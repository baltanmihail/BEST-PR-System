"""
API endpoints для этапов задач
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.task import (
    TaskStageResponse, TaskStageCreate, TaskStageUpdate
)
from app.services.stage_service import StageService
from app.utils.permissions import get_current_user, require_coordinator

router = APIRouter(prefix="/tasks", tags=["stages"])


@router.get("/{task_id}/stages", response_model=List[TaskStageResponse])
async def get_task_stages(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить все этапы задачи
    
    Доступно всем авторизованным пользователям
    """
    stages = await StageService.get_stages_by_task(db, task_id)
    return [TaskStageResponse.model_validate(stage) for stage in stages]


@router.post("/{task_id}/stages", response_model=TaskStageResponse, status_code=status.HTTP_201_CREATED)
async def create_stage(
    task_id: UUID,
    stage_data: TaskStageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать новый этап для задачи
    
    Доступно координаторам
    """
    from app.services.task_service import TaskService
    
    # Проверяем, что задача существует
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    stage = await StageService.create_stage(db, task_id, stage_data)
    return TaskStageResponse.model_validate(stage)


@router.patch("/{task_id}/stages/{stage_id}", response_model=TaskStageResponse)
async def update_stage(
    task_id: UUID,
    stage_id: UUID,
    stage_data: TaskStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить этап задачи
    
    Доступно всем авторизованным пользователям
    """
    # Проверяем, что этап принадлежит задаче
    stage = await StageService.get_stage_by_id(db, stage_id)
    if not stage or stage.task_id != task_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    updated_stage = await StageService.update_stage(db, stage_id, stage_data)
    if not updated_stage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    return TaskStageResponse.model_validate(updated_stage)


@router.delete("/{task_id}/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stage(
    task_id: UUID,
    stage_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Удалить этап задачи
    
    Доступно координаторам
    """
    
    # Проверяем, что этап принадлежит задаче
    stage = await StageService.get_stage_by_id(db, stage_id)
    if not stage or stage.task_id != task_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    success = await StageService.delete_stage(db, stage_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stage not found"
        )
    
    return None
