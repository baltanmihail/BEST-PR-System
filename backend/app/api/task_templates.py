"""
API endpoints для шаблонов задач
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User, UserRole
from app.models.task_template import TemplateCategory
from app.models.task import TaskType
from app.schemas.task import (
    TaskTemplateResponse, TaskTemplateCreate, TaskTemplateUpdate
)
from app.services.task_template_service import TaskTemplateService
from app.services.google_service import GoogleService
from app.utils.permissions import get_current_user, require_coordinator

router = APIRouter(prefix="/task-templates", tags=["task-templates"])

# Singleton для GoogleService
_google_service: Optional[GoogleService] = None


def get_google_service() -> Optional[GoogleService]:
    """Получить экземпляр GoogleService"""
    global _google_service
    if _google_service is None:
        try:
            _google_service = GoogleService()
        except Exception as e:
            # Если Google Service недоступен, продолжаем без него
            pass
    return _google_service


@router.get("", response_model=List[TaskTemplateResponse])
async def get_templates(
    category: Optional[str] = Query(None, description="Категория шаблона"),
    task_type: Optional[str] = Query(None, description="Тип задачи"),
    is_active: Optional[bool] = Query(True, description="Только активные"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список шаблонов задач
    
    Доступно всем авторизованным пользователям
    """
    category_enum = None
    if category:
        try:
            category_enum = TemplateCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category: {category}"
            )
    
    task_type_enum = None
    if task_type:
        try:
            task_type_enum = TaskType(task_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task_type: {task_type}"
            )
    
    templates = await TaskTemplateService.get_templates(
        db, category=category_enum, task_type=task_type_enum, is_active=is_active
    )
    
    return [TaskTemplateResponse.model_validate(t) for t in templates]


@router.get("/{template_id}", response_model=TaskTemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить шаблон по ID"""
    template = await TaskTemplateService.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    return TaskTemplateResponse.model_validate(template)


@router.post("", response_model=TaskTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TaskTemplateCreate,
    category: str = Query(..., description="Категория шаблона"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать новый шаблон задачи
    
    Доступно координаторам и VP4PR
    """
    try:
        category_enum = TemplateCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}"
        )
    
    google_service = get_google_service()
    template = await TaskTemplateService.create_template(
        db, template_data, current_user.id, category_enum, google_service
    )
    
    return TaskTemplateResponse.model_validate(template)


@router.patch("/{template_id}", response_model=TaskTemplateResponse)
async def update_template(
    template_id: UUID,
    template_data: TaskTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Обновить шаблон задачи
    
    Доступно координаторам и VP4PR
    """
    google_service = get_google_service()
    template = await TaskTemplateService.update_template(
        db, template_id, template_data, google_service
    )
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found"
        )
    
    return TaskTemplateResponse.model_validate(template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Удалить шаблон задачи
    
    Доступно координаторам и VP4PR
    """
    try:
        success = await TaskTemplateService.delete_template(db, template_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return None


@router.post("/{template_id}/create-task", status_code=status.HTTP_201_CREATED)
async def create_task_from_template(
    template_id: UUID,
    title: str = Query(..., description="Название задачи"),
    due_date: Optional[str] = Query(None, description="Дедлайн задачи (ISO format)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать задачу из шаблона
    
    Доступно координаторам и VP4PR
    """
    from datetime import datetime
    
    due_date_dt = None
    if due_date:
        try:
            due_date_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid due_date format. Use ISO format."
            )
    
    try:
        task = await TaskTemplateService.create_task_from_template(
            db, template_id, title, current_user.id, due_date_dt
        )
        
        from app.schemas.task import TaskResponse
        return TaskResponse.model_validate(task)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
