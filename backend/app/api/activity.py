"""
API endpoints для ленты активности
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta

from app.database import get_db
from app.models.activity import ActivityLog
from app.models.user import User
from app.models.task import Task, TaskStatus
from app.models.gamification import Achievement
from app.utils.permissions import OptionalUser

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/feed", response_model=dict)
async def get_activity_feed(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    days: int = Query(7, ge=1, le=30, description="Количество дней назад"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Получить публичную ленту активности
    
    Доступно всем (авторизованным и неавторизованным)
    """
    # Вычисляем дату начала периода
    start_date = datetime.now() - timedelta(days=days)
    
    # Получаем активность из лога
    query = select(ActivityLog).where(
        ActivityLog.timestamp >= start_date
    ).order_by(ActivityLog.timestamp.desc())
    
    # Подсчёт общего количества
    count_query = select(func.count(ActivityLog.id)).where(
        ActivityLog.timestamp >= start_date
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получение с пагинацией
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    activities = result.scalars().all()
    
    # Получаем информацию о пользователях
    user_ids = {a.user_id for a in activities if a.user_id}
    users = {}
    if user_ids:
        users_query = select(User).where(User.id.in_(user_ids))
        users_result = await db.execute(users_query)
        users = {u.id: u for u in users_result.scalars().all()}
    
    # Формируем ленту
    feed_items = []
    for activity in activities:
        user = users.get(activity.user_id) if activity.user_id else None
        user_name = user.full_name if user else "Неизвестный пользователь"
        
        # Формируем сообщение в зависимости от типа действия
        message = activity.details.get("message") if activity.details else None
        if not message:
            # Генерируем сообщение на основе действия
            if activity.action == "task_completed":
                task_title = activity.details.get("task_title", "задача") if activity.details else "задача"
                message = f"✅ {user_name} завершил(а) задачу '{task_title}'"
            elif activity.action == "task_assigned":
                task_title = activity.details.get("task_title", "задачу") if activity.details else "задачу"
                message = f"📋 {user_name} взял(а) задачу '{task_title}'"
            elif activity.action == "achievement_unlocked":
                achievement_name = activity.details.get("achievement_name", "достижение") if activity.details else "достижение"
                message = f"🏆 {user_name} получил(а) достижение '{achievement_name}'"
            elif activity.action == "task_created":
                task_title = activity.details.get("task_title", "задачу") if activity.details else "задачу"
                message = f"🆕 Создана новая задача '{task_title}'"
            else:
                message = f"{user_name} выполнил(а) действие: {activity.action}"
        
        feed_items.append({
            "id": str(activity.id),
            "action": activity.action,
            "message": message,
            "user_name": user_name if activity.action != "task_created" else None,  # Для создания задач не показываем имя координатора
            "timestamp": activity.timestamp.isoformat(),
            "details": activity.details
        })
    
    return {
        "items": feed_items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "period_days": days
    }


@router.get("/recent", response_model=List[dict])
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=20, description="Количество последних событий"),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить последние события активности (для виджета)
    
    Доступно всем (публичный endpoint)
    """
    query = select(ActivityLog).order_by(
        ActivityLog.timestamp.desc()
    ).limit(limit)
    
    result = await db.execute(query)
    activities = result.scalars().all()
    
    # Получаем имена пользователей
    user_ids = {a.user_id for a in activities if a.user_id}
    users = {}
    if user_ids:
        users_query = select(User).where(User.id.in_(user_ids))
        users_result = await db.execute(users_query)
        users = {u.id: u for u in users_result.scalars().all()}
    
    return [
        {
            "action": a.action,
            "message": a.details.get("message") if a.details else f"Действие: {a.action}",
            "timestamp": a.timestamp.isoformat()
        }
        for a in activities
    ]
