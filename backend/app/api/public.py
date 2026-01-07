"""
Публичные API endpoints (без авторизации)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, cast, String
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.models.task import Task, TaskType, TaskStatus, TaskPriority, TaskAssignment, AssignmentStatus
from app.models.user import User, UserRole

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/tasks", response_model=dict)
async def get_public_tasks(
    skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
    limit: int = Query(20, ge=1, le=50, description="Количество записей"),
    task_type: Optional[TaskType] = Query(None, description="Фильтр по типу задачи"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить публичный список задач (без авторизации)
    
    Показывает только открытые задачи (open, assigned, in_progress)
    Без детальной информации
    """
    # Фильтр: только публичные статусы (используем строковые значения для запросов)
    status_filter = Task.status.in_([
        TaskStatus.OPEN.value,
        TaskStatus.ASSIGNED.value,
        TaskStatus.IN_PROGRESS.value
    ])
    
    query = select(Task).where(status_filter)
    
    if task_type:
        query = query.where(Task.type == task_type)
    
    # Подсчёт общего количества
    count_query = select(func.count()).select_from(Task).where(status_filter)
    if task_type:
        count_query = count_query.where(Task.type == task_type)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получение задач с пагинацией
    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Формируем ограниченный ответ (без деталей)
    items = []
    for task in tasks:
        # Вычисляем относительный дедлайн
        due_date_info = None
        if task.due_date:
            now = datetime.now(task.due_date.tzinfo)
            delta = task.due_date - now
            if delta.days > 0:
                if delta.days == 1:
                    due_date_info = "завтра"
                elif delta.days <= 7:
                    due_date_info = f"через {delta.days} дня"
                else:
                    due_date_info = f"через {delta.days} дней"
            elif delta.days == 0:
                due_date_info = "сегодня"
            else:
                due_date_info = "просрочено"
        
        # Подсчитываем количество участников
        participants_count = len(task.assignments) if task.assignments else 0
        
        # Подсчитываем количество этапов
        stages_count = len(task.stages) if task.stages else 0
        
        items.append({
            "id": str(task.id),
            "title": task.title,
            "type": task.type.value,
            "priority": task.priority.value,
            "status": task.status.value,
            "due_date_relative": due_date_info,
            "participants_count": participants_count,
            "stages_count": stages_count,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            # Скрываем: description, детальные дедлайны, имена участников, детали этапов
        })
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/tasks/{task_id}", response_model=dict)
async def get_public_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить публичную информацию о задаче (без авторизации)
    
    Ограниченная информация без деталей
    """
    query = select(Task).where(
        and_(
            Task.id == task_id,
            Task.status.in_([
                TaskStatus.OPEN.value,
                TaskStatus.ASSIGNED.value,
                TaskStatus.IN_PROGRESS.value
            ])
        )
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not available"
        )
    
    # Вычисляем относительный дедлайн
    due_date_info = None
    if task.due_date:
        now = datetime.now(task.due_date.tzinfo)
        delta = task.due_date - now
        if delta.days > 0:
            if delta.days == 1:
                due_date_info = "завтра"
            elif delta.days <= 7:
                due_date_info = f"через {delta.days} дня"
            else:
                due_date_info = f"через {delta.days} дней"
        elif delta.days == 0:
            due_date_info = "сегодня"
        else:
            due_date_info = "просрочено"
    
    # Информация о координаторе (показываем имя)
    coordinator_name = None
    if task.created_by:
        coord_query = select(User).where(User.id == task.created_by)
        coord_result = await db.execute(coord_query)
        coordinator = coord_result.scalar_one_or_none()
        if coordinator:
            coordinator_name = coordinator.full_name
    
    # Подсчитываем участников
    participants_count = len(task.assignments) if task.assignments else 0
    
    # Информация об этапах (только количество и общее описание)
    stages_info = []
    if task.stages:
        for stage in sorted(task.stages, key=lambda s: s.stage_order):
            stages_info.append({
                "name": stage.stage_name,
                "order": stage.stage_order,
                "status": stage.status.value,
                "color": stage.status_color
            })
    
    return {
        "id": str(task.id),
        "title": task.title,
        "type": task.type.value,
        "priority": task.priority.value,
        "status": task.status.value,
        "due_date_relative": due_date_info,
        "coordinator_name": coordinator_name,
        "participants_count": participants_count,
        "stages": stages_info,
        "stages_count": len(stages_info),
        "created_at": task.created_at.isoformat() if task.created_at else None,
        # Скрываем: полное описание, детальные дедлайны, имена участников, файлы
    }


@router.get("/leaderboard", response_model=List[dict])
async def get_public_leaderboard(
    limit: int = Query(10, ge=1, le=50, description="Количество участников"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить публичный рейтинг пользователей (без авторизации)
    
    Показывает топ пользователей, исключая координаторов и VP4PR
    """
    # Исключаем координаторов и VP4PR
    excluded_roles = [
        UserRole.COORDINATOR_SMM,
        UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL,
        UserRole.COORDINATOR_PRFR,
        UserRole.VP4PR
    ]
    
    query = select(User).where(
        and_(
            User.is_active == True,
            User.deleted_at.is_(None),  # Исключаем удалённых пользователей
            ~User.role.in_(excluded_roles)
        )
    ).order_by(
        User.points.desc(),
        User.level.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    # Подсчитываем выполненные задачи для каждого пользователя
    from app.models.task import TaskAssignment, AssignmentStatus
    leaderboard = []
    for user in users:
        # Подсчитываем выполненные задачи через task_assignments
        completed_query = select(func.count(TaskAssignment.id)).where(
            and_(
                TaskAssignment.user_id == user.id,
                TaskAssignment.status == AssignmentStatus.COMPLETED
            )
        )
        completed_result = await db.execute(completed_query)
        tasks_count = completed_result.scalar() or 0
        
        leaderboard.append({
            "rank": len(leaderboard) + 1,
            "name": user.full_name,
            "username": user.username,
            "level": user.level,
            "points": user.points,
            "completed_tasks": tasks_count,
            # Скрываем: telegram_id, детальную статистику
        })
    
    return leaderboard


@router.get("/stats", response_model=dict)
async def get_public_stats(
    db: AsyncSession = Depends(get_db)
):
    """
    Получить публичную статистику системы (без авторизации)
    """
    # Общее количество выполненных задач
    completed_tasks_query = select(func.count(Task.id)).where(
        Task.status == TaskStatus.COMPLETED.value
    )
    completed_result = await db.execute(completed_tasks_query)
    completed_tasks = completed_result.scalar() or 0
    
    # Активные задачи
    active_tasks_query = select(func.count(Task.id)).where(
        Task.status.in_([
            TaskStatus.ASSIGNED.value,
            TaskStatus.IN_PROGRESS.value,
            TaskStatus.REVIEW.value
        ])
    )
    active_result = await db.execute(active_tasks_query)
    active_tasks = active_result.scalar() or 0
    
    # Количество участников (активных)
    users_query = select(func.count(User.id)).where(
        and_(
            User.is_active == True,
            User.deleted_at.is_(None),  # Исключаем удалённых пользователей
            ~User.role.in_([
                UserRole.COORDINATOR_SMM,
                UserRole.COORDINATOR_DESIGN,
                UserRole.COORDINATOR_CHANNEL,
                UserRole.COORDINATOR_PRFR,
                UserRole.VP4PR
            ])
        )
    )
    users_result = await db.execute(users_query)
    participants_count = users_result.scalar() or 0
    
    # Средний рейтинг (из выполненных задач с рейтингом)
    # Упрощённо: считаем через баллы
    avg_points_query = select(func.avg(User.points)).where(
        and_(
            User.is_active == True,
            User.points > 0
        )
    )
    avg_result = await db.execute(avg_points_query)
    avg_points = round(avg_result.scalar() or 0, 1)
    
    # Общее количество задач
    total_tasks_query = select(func.count(Task.id))
    total_tasks_result = await db.execute(total_tasks_query)
    total_tasks = total_tasks_result.scalar() or 0
    
    # Общее количество баллов
    total_points_query = select(func.sum(User.points)).where(
        and_(
            User.is_active == True,
            User.deleted_at.is_(None)  # Исключаем удалённых пользователей
        )
    )
    total_points_result = await db.execute(total_points_query)
    total_points = total_points_result.scalar() or 0
    
    return {
        "total_users": participants_count,  # Используем participants_count как total_users
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "active_tasks": active_tasks,
        "participants_count": participants_count,
        "total_points": total_points,
        "average_points": avg_points,
        "updated_at": datetime.utcnow().isoformat()
    }
