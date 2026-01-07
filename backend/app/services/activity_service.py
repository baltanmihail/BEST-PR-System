"""
Сервис для логирования активности
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime, timezone

from app.models.activity import ActivityLog


class ActivityService:
    """Сервис для работы с активностью"""
    
    @staticmethod
    async def log_activity(
        db: AsyncSession,
        action: str,
        user_id: Optional[UUID] = None,
        details: Optional[Dict] = None
    ) -> ActivityLog:
        """Записать активность в лог"""
        activity = ActivityLog(
            user_id=user_id,
            action=action,
            details=details,
            timestamp=datetime.now(timezone.utc)
        )
        
        db.add(activity)
        await db.commit()
        await db.refresh(activity)
        
        return activity
    
    @staticmethod
    async def log_task_completed(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Записать завершение задачи"""
        await ActivityService.log_activity(
            db=db,
            action="task_completed",
            user_id=user_id,
            details={
                "task_id": str(task_id),
                "task_title": task_title,
                "message": f"Задача '{task_title}' завершена"
            }
        )
    
    @staticmethod
    async def log_task_assigned(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Записать взятие задачи"""
        await ActivityService.log_activity(
            db=db,
            action="task_assigned",
            user_id=user_id,
            details={
                "task_id": str(task_id),
                "task_title": task_title,
                "message": f"Задача '{task_title}' взята"
            }
        )
    
    @staticmethod
    async def log_achievement_unlocked(
        db: AsyncSession,
        user_id: UUID,
        achievement_type: str,
        achievement_name: str
    ):
        """Записать получение достижения"""
        await ActivityService.log_activity(
            db=db,
            action="achievement_unlocked",
            user_id=user_id,
            details={
                "achievement_type": achievement_type,
                "achievement_name": achievement_name,
                "message": f"Получено достижение '{achievement_name}'"
            }
        )
    
    @staticmethod
    async def log_task_created(
        db: AsyncSession,
        task_id: UUID,
        task_title: str,
        task_type: str
    ):
        """Записать создание задачи"""
        await ActivityService.log_activity(
            db=db,
            action="task_created",
            user_id=None,  # Не показываем координатора публично
            details={
                "task_id": str(task_id),
                "task_title": task_title,
                "task_type": task_type,
                "message": f"Создана новая задача '{task_title}'"
            }
        )
