"""
Сервис для логирования активности
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, List
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
    
    @staticmethod
    async def log_points_adjustment(
        db: AsyncSession,
        user_id: UUID,
        points_delta: int,
        reason: str,
        adjusted_by: UUID
    ):
        """Записать изменение баллов пользователя"""
        await ActivityService.log_activity(
            db=db,
            action="points_adjusted",
            user_id=user_id,
            details={
                "points_delta": points_delta,
                "reason": reason,
                "adjusted_by": str(adjusted_by),
                "message": f"Баллы изменены на {points_delta} ({reason})"
            }
        )
    
    @staticmethod
    async def log_profile_updated(
        db: AsyncSession,
        user_id: UUID,
        updated_fields: List[str]
    ):
        """Записать обновление профиля"""
        await ActivityService.log_activity(
            db=db,
            action="profile_updated",
            user_id=user_id,
            details={
                "updated_fields": updated_fields,
                "message": f"Обновлены поля профиля: {', '.join(updated_fields)}"
            }
        )
    
    @staticmethod
    async def log_user_blocked(
        db: AsyncSession,
        user_id: UUID,
        blocked_by: UUID,
        reason: Optional[str] = None
    ):
        """Записать блокировку пользователя"""
        await ActivityService.log_activity(
            db=db,
            action="user_blocked",
            user_id=user_id,
            details={
                "blocked_by": str(blocked_by),
                "reason": reason,
                "message": f"Пользователь заблокирован ({reason or 'без указания причины'})"
            }
        )
    
    @staticmethod
    async def log_user_unblocked(
        db: AsyncSession,
        user_id: UUID,
        unblocked_by: UUID
    ):
        """Записать разблокировку пользователя"""
        await ActivityService.log_activity(
            db=db,
            action="user_unblocked",
            user_id=user_id,
            details={
                "unblocked_by": str(unblocked_by),
                "message": "Пользователь разблокирован"
            }
        )
    
    @staticmethod
    async def log_role_changed(
        db: AsyncSession,
        user_id: UUID,
        old_role: str,
        new_role: str,
        changed_by: UUID
    ):
        """Записать изменение роли пользователя"""
        await ActivityService.log_activity(
            db=db,
            action="role_changed",
            user_id=user_id,
            details={
                "old_role": old_role,
                "new_role": new_role,
                "changed_by": str(changed_by),
                "message": f"Роль изменена с '{old_role}' на '{new_role}'"
            }
        )
