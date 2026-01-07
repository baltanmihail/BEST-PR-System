"""
API endpoints для задач
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import timedelta

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


@router.post("/{task_id}/publish", response_model=TaskResponse)
async def publish_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Опубликовать задачу (изменить статус с DRAFT на OPEN)
    
    Доступно только координаторам и VP4PR
    """
    task = await TaskService.publish_task(
        db=db,
        task_id=task_id,
        current_user=current_user
    )
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found, already published, or you don't have permission"
        )
    
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/assign", response_model=dict)
async def assign_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Взять задачу в работу
    
    Для задач типа Channel автоматически предлагает доступное оборудование
    на даты этапа "Съёмка".
    
    Доступно всем авторизованным пользователям
    
    Returns:
        {
            "task": TaskResponse,
            "equipment_suggestions": List[EquipmentResponse] (для Channel задач)
        }
    """
    from app.models.task import TaskAssignment, AssignmentStatus, TaskType
    from app.services.equipment_service import EquipmentService
    from datetime import date
    
    # Получаем задачу
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Проверяем, не взята ли уже задача
    if task.status == TaskStatus.ASSIGNED or task.status == TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already assigned"
        )
    
    # Создаём назначение
    assignment = TaskAssignment(
        task_id=task_id,
        user_id=current_user.id,
        role_in_task="executor",
        status=AssignmentStatus.ASSIGNED
    )
    
    db.add(assignment)
    
    # Обновляем статус задачи
    task.status = TaskStatus.ASSIGNED
    
    # Если это задача типа Channel, предлагаем оборудование
    equipment_suggestions = []
    if task.type == TaskType.CHANNEL:
        # Находим этап "Съёмка"
        shooting_stage = None
        for stage in task.stages:
            if stage.stage_name.lower() in ["съёмка", "shooting", "съемка"]:
                shooting_stage = stage
                break
        
        if shooting_stage and shooting_stage.due_date:
            # Предлагаем оборудование на даты съёмки
            shooting_date = shooting_stage.due_date.date()
            # Предполагаем, что съёмка занимает 1-2 дня
            end_date = shooting_date + timedelta(days=1)
            
            try:
                available_equipment = await EquipmentService.get_available_equipment(
                    db=db,
                    start_date=shooting_date,
                    end_date=end_date,
                    category=None  # Показываем всё доступное
                )
                equipment_suggestions = available_equipment
            except Exception as e:
                # Если ошибка при получении оборудования, продолжаем без него
                pass
    
    # Начисляем баллы за взятие задачи
    from app.services.gamification_service import GamificationService
    try:
        await GamificationService.award_task_taken_points(
            db=db,
            user_id=current_user.id,
            task=task
        )
    except Exception as e:
        # Логируем ошибку, но не прерываем процесс
        import logging
        logging.error(f"Failed to award points for task taken: {e}")
    
    # Уведомляем о назначении задачи
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_task_assigned(
            db=db,
            user_id=current_user.id,
            task_id=task.id,
            task_title=task.title
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send notification: {e}")
    
    await db.commit()
    await db.refresh(task)
    
    return {
        "task": TaskResponse.model_validate(task),
        "equipment_suggestions": [
            {
                "id": str(eq.id),
                "name": eq.name,
                "category": eq.category,
                "available_dates": {
                    "start": shooting_stage.due_date.date().isoformat() if shooting_stage else None,
                    "end": (shooting_stage.due_date.date() + timedelta(days=1)).isoformat() if shooting_stage else None
                }
            }
            for eq in equipment_suggestions[:10]  # Ограничиваем до 10 предложений
        ] if equipment_suggestions else []
    }


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Завершить задачу
    
    Доступно исполнителю задачи или координаторам
    """
    from app.models.task import TaskAssignment, AssignmentStatus
    from sqlalchemy import select
    
    # Получаем задачу
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Проверяем, есть ли назначение на текущего пользователя
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == current_user.id
        )
    )
    assignment = result.scalar_one_or_none()
    
    # Проверка прав (исполнитель или координатор)
    from app.models.user import UserRole
    is_coordinator = current_user.role in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]
    
    if not assignment and not is_coordinator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this task"
        )
    
    # Обновляем назначение
    completed_at = None
    if assignment:
        assignment.status = AssignmentStatus.COMPLETED
        from datetime import datetime, timezone
        completed_at = datetime.now(timezone.utc)
        assignment.completed_at = completed_at
    
    # Обновляем статус задачи
    task.status = TaskStatus.COMPLETED
    
    # Начисляем баллы за выполнение задачи
    from app.services.gamification_service import GamificationService
    if assignment and completed_at:
        try:
            # Начисляем баллы за выполнение
            await GamificationService.award_task_completed_points(
                db=db,
                user_id=current_user.id,
                task=task,
                assignment=assignment,
                completed_at=completed_at
            )
            
            # Проверяем и начисляем ачивки
            new_achievements = await GamificationService.check_and_award_achievements(
                db=db,
                user_id=current_user.id,
                task=task
            )
            
            # Уведомляем о новых ачивках
            from app.services.notification_service import NotificationService
            achievement_names = {
                "first_task": "🎯 Первая кровь",
                "speedster": "⚡ Скорострел",
                "reliable": "🛡️ Надёжный",
                "director": "🎬 Режиссёр",
                "designer": "🖌️ Дизайнер",
                "smm_guru": "📢 SMM-гур",
                "helper": "🤝 Помощник",
                "unstoppable": "🔥 Неудержимый"
            }
            for achievement in new_achievements:
                await NotificationService.notify_achievement_unlocked(
                    db=db,
                    user_id=current_user.id,
                    achievement_type=achievement.achievement_type,
                    achievement_name=achievement_names.get(achievement.achievement_type, achievement.achievement_type)
                )
            
            # Уведомляем о завершении задачи
            await NotificationService.notify_task_completed(
                db=db,
                user_id=current_user.id,
                task_id=task.id,
                task_title=task.title
            )
        except Exception as e:
            # Логируем ошибку, но не прерываем процесс
            import logging
            logging.error(f"Failed to award points/achievements for task completion: {e}")
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)
