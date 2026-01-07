"""
API endpoints для календаря/таймлайна
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal
from datetime import datetime, date
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.task import Task, TaskStage, TaskType
from app.models.event import Event
from app.utils.permissions import get_current_user
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from dateutil.relativedelta import relativedelta
import calendar as cal_lib

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("")
async def get_calendar(
    view: Literal["month", "week", "timeline"] = Query("month", description="Тип представления"),
    start_date: Optional[date] = Query(None, description="Начальная дата (для month/week)"),
    end_date: Optional[date] = Query(None, description="Конечная дата (для timeline)"),
    task_type: Optional[TaskType] = Query(None, description="Фильтр по типу задачи"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить календарь/таймлайн задач
    
    Поддерживает три вида:
    - month: календарь на месяц
    - week: недельный вид
    - timeline: горизонтальная шкала всего семестра
    """
    # Если дата не указана, используем текущую
    if not start_date:
        start_date = date.today()
    
    if view == "month":
        return await _get_month_view(db, start_date, task_type, current_user)
    elif view == "week":
        return await _get_week_view(db, start_date, task_type, current_user)
    elif view == "timeline":
        if not end_date:
            # По умолчанию показываем 6 месяцев от start_date
            end_date = start_date + relativedelta(months=6)
        return await _get_timeline_view(db, start_date, end_date, task_type, current_user)
    else:
        return {"error": "Invalid view type"}


async def _get_month_view(
    db: AsyncSession,
    month_date: date,
    task_type: Optional[TaskType],
    current_user: User
):
    """Получить календарь на месяц"""
    # Вычисляем начало и конец месяца
    first_day = month_date.replace(day=1)
    last_day = month_date.replace(day=cal_lib.monthrange(month_date.year, month_date.month)[1])
    
    # Получаем задачи и этапы в этом диапазоне
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, first_day, last_day, task_type, current_user
    )
    
    # Формируем структуру календаря
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_tasks = []
        day_stages = []
        
        # Находим задачи и этапы на эту дату
        for task in tasks:
            if task.due_date and task.due_date.date() == current_date:
                day_tasks.append({
                    "id": str(task.id),
                    "title": task.title,
                    "type": task.type.value,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "color": _get_task_color(task.status, task.priority),
                    "is_event": False
                })
        
        # Добавляем этапы
        for stage in stages:
            if stage.due_date and stage.due_date.date() == current_date:
                day_stages.append({
                    "id": str(stage.id),
                    "task_id": str(stage.task_id),
                    "stage_name": stage.stage_name,
                    "status_color": stage.status_color,
                    "status": stage.status.value
                })
        
        calendar_data.append({
            "date": current_date.isoformat(),
            "tasks": day_tasks,
            "stages": day_stages
        })
        
        current_date = current_date + relativedelta(days=1)
    
    # Добавляем мероприятия (events)
    events_query = select(Event).where(
        and_(
            Event.date_start <= last_day,
            Event.date_end >= first_day
        )
    )
    events_result = await db.execute(events_query)
    events = events_result.scalars().all()
    
    events_list = [
        {
            "id": str(event.id),
            "name": event.name,
            "date_start": event.date_start.isoformat(),
            "date_end": event.date_end.isoformat() if event.date_end else None,
            "color": "purple"
        }
        for event in events
    ]
    
    return {
        "view": "month",
        "month": month_date.month,
        "year": month_date.year,
        "first_day": first_day.isoformat(),
        "last_day": last_day.isoformat(),
        "days": calendar_data,
        "events": events_list
    }


async def _get_week_view(
    db: AsyncSession,
    week_start: date,
    task_type: Optional[TaskType],
    current_user: User
):
    """Получить недельный вид"""
    # Вычисляем начало недели (понедельник)
    days_since_monday = week_start.weekday()
    monday = week_start - relativedelta(days=days_since_monday)
    sunday = monday + relativedelta(days=6)
    
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, monday, sunday, task_type, current_user
    )
    
    week_data = []
    current_date = monday
    
    while current_date <= sunday:
        day_items = []
        
        # Задачи
        for task in tasks:
            if task.due_date and task.due_date.date() == current_date:
                day_items.append({
                    "type": "task",
                    "id": str(task.id),
                    "title": task.title,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "color": _get_task_color(task.status, task.priority)
                })
        
        # Этапы
        for stage in stages:
            if stage.due_date and stage.due_date.date() == current_date:
                day_items.append({
                    "type": "stage",
                    "id": str(stage.id),
                    "task_id": str(stage.task_id),
                    "title": f"{stage.task.title} - {stage.stage_name}",
                    "color": stage.status_color,
                    "status": stage.status.value
                })
        
        week_data.append({
            "date": current_date.isoformat(),
            "day_name": current_date.strftime("%A"),
            "items": day_items
        })
        
        current_date = current_date + relativedelta(days=1)
    
    return {
        "view": "week",
        "start_date": monday.isoformat(),
        "end_date": sunday.isoformat(),
        "days": week_data
    }


async def _get_timeline_view(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    task_type: Optional[TaskType],
    current_user: User
):
    """Получить таймлайн (горизонтальная шкала)"""
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, start_date, end_date, task_type, current_user
    )
    
    timeline_items = []
    
    # Задачи
    for task in tasks:
        if task.due_date and start_date <= task.due_date.date() <= end_date:
            timeline_items.append({
                "type": "task",
                "id": str(task.id),
                "title": task.title,
                "type_task": task.type.value,
                "start_date": task.created_at.date().isoformat(),
                "end_date": task.due_date.date().isoformat() if task.due_date else None,
                "color": _get_task_color(task.status, task.priority),
                "status": task.status.value
            })
    
    # Этапы
    for stage in stages:
        if stage.due_date and start_date <= stage.due_date.date() <= end_date:
            timeline_items.append({
                "type": "stage",
                "id": str(stage.id),
                "task_id": str(stage.task_id),
                "task_title": stage.task.title,
                "stage_name": stage.stage_name,
                "date": stage.due_date.date().isoformat(),
                "color": stage.status_color,
                "status": stage.status.value
            })
    
    # Мероприятия
    events_query = select(Event).where(
        and_(
            Event.date_start <= end_date,
            or_(
                Event.date_end >= start_date,
                Event.date_end == None
            )
        )
    )
    events_result = await db.execute(events_query)
    events = events_result.scalars().all()
    
    for event in events:
        timeline_items.append({
            "type": "event",
            "id": str(event.id),
            "title": event.name,
            "start_date": event.date_start.isoformat(),
            "end_date": event.date_end.isoformat() if event.date_end else None,
            "color": "purple"
        })
    
    return {
        "view": "timeline",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": sorted(timeline_items, key=lambda x: x.get("start_date") or x.get("date", ""))
    }


async def _get_tasks_and_stages_in_range(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    task_type: Optional[TaskType],
    current_user: User
):
    """Получить задачи и этапы в диапазоне дат"""
    # Запрос для задач
    conditions = [
        or_(
            and_(Task.due_date >= datetime.combine(start_date, datetime.min.time())),
            Task.created_at >= datetime.combine(start_date, datetime.min.time())
        ),
        or_(
            Task.due_date <= datetime.combine(end_date, datetime.max.time()),
            Task.created_at <= datetime.combine(end_date, datetime.max.time())
        )
    ]
    
    if task_type:
        conditions.append(Task.type == task_type)
    
    tasks_query = select(Task).where(and_(*conditions))
    tasks_query = tasks_query.options(
        selectinload(Task.stages)
    )
    
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    # Запрос для этапов
    stages_query = select(TaskStage).join(Task).where(
        and_(
            TaskStage.due_date >= datetime.combine(start_date, datetime.min.time()),
            TaskStage.due_date <= datetime.combine(end_date, datetime.max.time())
        )
    )
    
    if task_type:
        stages_query = stages_query.where(Task.type == task_type)
    
    stages_query = stages_query.options(selectinload(TaskStage.task))
    
    stages_result = await db.execute(stages_query)
    stages = stages_result.scalars().all()
    
    return list(tasks), list(stages)


def _get_task_color(status, priority):
    """Определить цвет задачи на основе статуса и приоритета"""
    if status.value == "completed":
        return "blue"
    elif status.value in ["review"]:
        return "yellow"
    elif priority.value == "critical":
        return "red"
    elif status.value in ["in_progress", "assigned"]:
        return "green"
    else:
        return "gray"
