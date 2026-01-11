"""
API endpoints для геймификации
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.services.gamification_service import GamificationService
from app.utils.permissions import get_current_user, get_current_user_allow_inactive, OptionalUser

router = APIRouter(prefix="/gamification", tags=["gamification"])


@router.get("/stats", response_model=dict)
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_allow_inactive())
):
    """
    Получить мою статистику (баллы, уровень, ачивки)
    
    Доступно всем авторизованным пользователям (включая неактивных)
    """
    stats = await GamificationService.get_user_stats(db, current_user.id)
    return stats


@router.get("/stats/{user_id}", response_model=dict)
async def get_user_stats(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить статистику пользователя по ID
    
    Доступно всем авторизованным пользователям
    """
    stats = await GamificationService.get_user_stats(db, user_id)
    return stats


@router.get("/leaderboard", response_model=List[dict])
async def get_leaderboard(
    limit: int = Query(10, ge=1, le=100, description="Количество участников в рейтинге"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Получить рейтинг пользователей (ТОП-N)
    
    Координаторы и VP4PR исключены из рейтинга
    
    Доступно всем авторизованным пользователям (включая неактивных)
    """
    leaderboard = await GamificationService.get_leaderboard(db, limit=limit)
    return leaderboard


@router.get("/achievements", response_model=List[dict])
async def get_my_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить мои ачивки
    
    Доступно всем авторизованным пользователям
    """
    from app.models.gamification import Achievement
    from sqlalchemy import select
    
    query = select(Achievement).where(
        Achievement.user_id == current_user.id
    ).order_by(Achievement.unlocked_at.desc())
    
    result = await db.execute(query)
    achievements = result.scalars().all()
    
    # Маппинг типов ачивок на названия
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
    
    return [
        {
            "id": str(a.id),
            "type": a.achievement_type,
            "name": achievement_names.get(a.achievement_type, a.achievement_type),
            "unlocked_at": a.unlocked_at.isoformat()
        }
        for a in achievements
    ]
