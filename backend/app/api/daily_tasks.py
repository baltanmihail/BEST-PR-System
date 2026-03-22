"""
API endpoints для быстрых задач (планёрка на день)
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc, asc, nulls_last
from sqlalchemy.orm import selectinload
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime, timezone, timedelta
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import User
from app.models.daily_task import DailyTask
from app.utils.permissions import get_current_user

router = APIRouter(prefix="/daily-tasks", tags=["daily-tasks"])

MSK = timezone(timedelta(hours=3))


class DailyTaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    notes: Optional[str] = None
    date: Optional[date] = None
    scheduled_time: Optional[str] = None  # "HH:MM"
    priority: Optional[int] = Field(0, ge=0, le=2)
    assignee_id: Optional[str] = None


class DailyTaskUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    is_done: Optional[bool] = None
    date: Optional[date] = None
    scheduled_time: Optional[str] = None
    priority: Optional[int] = Field(None, ge=0, le=2)
    assignee_id: Optional[str] = None


class DailyTaskResponse(BaseModel):
    id: str
    title: str
    notes: Optional[str] = None
    date: str
    scheduled_time: Optional[str] = None
    priority: int = 0
    is_done: bool
    done_at: Optional[str] = None
    creator_id: str
    assignee_id: str
    creator_name: Optional[str] = None
    assignee_name: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


def _task_to_response(task: DailyTask) -> DailyTaskResponse:
    return DailyTaskResponse(
        id=str(task.id),
        title=task.title,
        notes=task.notes,
        date=str(task.date),
        scheduled_time=task.scheduled_time.strftime("%H:%M") if task.scheduled_time else None,
        priority=task.priority or 0,
        is_done=task.is_done,
        done_at=task.done_at.isoformat() if task.done_at else None,
        creator_id=str(task.creator_id),
        assignee_id=str(task.assignee_id),
        creator_name=task.creator.full_name if task.creator else None,
        assignee_name=task.assignee.full_name if task.assignee else None,
        created_at=task.created_at.isoformat() if task.created_at else None,
    )


@router.get("", response_model=List[DailyTaskResponse])
async def get_daily_tasks(
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD, default today MSK"),
    assignee_id: Optional[str] = Query(None),
    include_done: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить задачи на день."""
    if target_date:
        d = date.fromisoformat(target_date)
    else:
        d = datetime.now(MSK).date()

    conditions = [DailyTask.date == d]
    if assignee_id:
        conditions.append(DailyTask.assignee_id == UUID(assignee_id))
    if not include_done:
        conditions.append(DailyTask.is_done == False)

    query = (
        select(DailyTask)
        .where(and_(*conditions))
        .options(selectinload(DailyTask.creator), selectinload(DailyTask.assignee))
        .order_by(
            asc(DailyTask.is_done),
            nulls_last(asc(DailyTask.scheduled_time)),
            desc(DailyTask.priority),
            asc(DailyTask.created_at),
        )
    )
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [_task_to_response(t) for t in tasks]


@router.get("/my", response_model=List[DailyTaskResponse])
async def get_my_daily_tasks(
    target_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Мои задачи на сегодня."""
    if target_date:
        d = date.fromisoformat(target_date)
    else:
        d = datetime.now(MSK).date()

    query = (
        select(DailyTask)
        .where(
            DailyTask.assignee_id == current_user.id,
            DailyTask.date == d,
        )
        .options(selectinload(DailyTask.creator), selectinload(DailyTask.assignee))
        .order_by(
            asc(DailyTask.is_done),
            nulls_last(asc(DailyTask.scheduled_time)),
            desc(DailyTask.priority),
            asc(DailyTask.created_at),
        )
    )
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [_task_to_response(t) for t in tasks]


@router.post("", response_model=DailyTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_daily_task(
    data: DailyTaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать быструю задачу."""
    task_date = data.date or datetime.now(MSK).date()
    assignee_uuid = UUID(data.assignee_id) if data.assignee_id else current_user.id

    sched_time = None
    if data.scheduled_time:
        try:
            from datetime import time as _time
            parts = data.scheduled_time.split(":")
            sched_time = _time(int(parts[0]), int(parts[1]))
        except Exception:
            pass

    task = DailyTask(
        title=data.title,
        notes=data.notes,
        date=task_date,
        scheduled_time=sched_time,
        priority=data.priority or 0,
        creator_id=current_user.id,
        assignee_id=assignee_uuid,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Перезагрузить с relationships
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == task.id)
        .options(selectinload(DailyTask.creator), selectinload(DailyTask.assignee))
    )
    task = result.scalar_one()
    return _task_to_response(task)


@router.patch("/{task_id}", response_model=DailyTaskResponse)
async def update_daily_task(
    task_id: str,
    data: DailyTaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить быструю задачу (пометить выполненной и т.д.)."""
    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == UUID(task_id))
        .options(selectinload(DailyTask.creator), selectinload(DailyTask.assignee))
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if data.title is not None:
        task.title = data.title
    if data.notes is not None:
        task.notes = data.notes
    if data.date is not None:
        task.date = data.date
    if data.assignee_id is not None:
        task.assignee_id = UUID(data.assignee_id)
    if data.priority is not None:
        task.priority = data.priority
    if data.scheduled_time is not None:
        try:
            from datetime import time as _time
            parts = data.scheduled_time.split(":")
            task.scheduled_time = _time(int(parts[0]), int(parts[1]))
        except Exception:
            task.scheduled_time = None
    if data.is_done is not None:
        task.is_done = data.is_done
        task.done_at = datetime.now(timezone.utc) if data.is_done else None

    await db.commit()
    await db.refresh(task)

    result = await db.execute(
        select(DailyTask)
        .where(DailyTask.id == task.id)
        .options(selectinload(DailyTask.creator), selectinload(DailyTask.assignee))
    )
    task = result.scalar_one()
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_daily_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Удалить быструю задачу."""
    result = await db.execute(select(DailyTask).where(DailyTask.id == UUID(task_id)))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()


@router.get("/stats", response_model=dict)
async def daily_tasks_stats(
    target_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статистика: сколько сделано / всего для текущего пользователя."""
    if target_date:
        d = date.fromisoformat(target_date)
    else:
        d = datetime.now(MSK).date()

    total_q = await db.execute(
        select(func.count(DailyTask.id)).where(
            DailyTask.assignee_id == current_user.id,
            DailyTask.date == d,
        )
    )
    done_q = await db.execute(
        select(func.count(DailyTask.id)).where(
            DailyTask.assignee_id == current_user.id,
            DailyTask.date == d,
            DailyTask.is_done == True,
        )
    )
    total = total_q.scalar() or 0
    done = done_q.scalar() or 0
    return {"date": str(d), "total": total, "done": done, "pending": total - done}
