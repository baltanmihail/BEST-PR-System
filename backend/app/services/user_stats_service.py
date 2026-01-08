"""
Сервис для статистики пользователей
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta

from app.models.user import User
from app.models.task import Task, TaskAssignment, TaskStatus, AssignmentStatus
from app.models.file import File
from app.models.gallery import GalleryItem
from app.schemas.user import UserStats


class UserStatsService:
    """Сервис для получения статистики пользователей"""
    
    @staticmethod
    async def get_user_stats(db: AsyncSession, user_id: UUID) -> UserStats:
        """
        Получить полную статистику пользователя
        
        Returns:
            UserStats с полной статистикой
        """
        # Получаем пользователя
        user_query = select(User).where(User.id == user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Подсчитываем выполненные задачи
        completed_tasks_query = select(func.count(TaskAssignment.id)).join(Task).where(
            TaskAssignment.user_id == user_id,
            TaskAssignment.status == AssignmentStatus.COMPLETED
        )
        completed_result = await db.execute(completed_tasks_query)
        completed_tasks = completed_result.scalar_one() or 0
        
        # Подсчитываем активные задачи
        active_tasks_query = select(func.count(TaskAssignment.id)).where(
            TaskAssignment.user_id == user_id,
            TaskAssignment.status.in_([AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS])
        )
        active_result = await db.execute(active_tasks_query)
        active_tasks = active_result.scalar_one() or 0
        
        # Подсчитываем достижения (пока заглушка, нужно будет добавить модель Achievement)
        achievements_count = 0  # TODO: реализовать подсчёт достижений
        
        # Подсчитываем процент выполнения в срок
        on_time_completion_rate = await UserStatsService._calculate_on_time_completion_rate(
            db, user_id
        )
        
        # Подсчитываем среднее время выполнения
        average_completion_time = await UserStatsService._calculate_average_completion_time(
            db, user_id
        )
        
        # Подсчитываем загруженные файлы
        files_query = select(func.count(File.id)).where(File.uploaded_by == user_id)
        files_result = await db.execute(files_query)
        total_files_uploaded = files_result.scalar_one() or 0
        
        # Подсчитываем работы в галерее
        gallery_query = select(func.count(GalleryItem.id)).where(GalleryItem.created_by == user_id)
        gallery_result = await db.execute(gallery_query)
        gallery_items_count = gallery_result.scalar_one() or 0
        
        return UserStats(
            id=user.id,
            telegram_id=user.telegram_id,
            full_name=user.full_name,
            role=user.role,
            level=user.level,
            points=user.points,
            streak_days=user.streak_days,
            completed_tasks=completed_tasks,
            active_tasks=active_tasks,
            achievements_count=achievements_count,
            on_time_completion_rate=on_time_completion_rate,
            average_completion_time=average_completion_time,
            total_files_uploaded=total_files_uploaded,
            gallery_items_count=gallery_items_count
        )
    
    @staticmethod
    async def _calculate_on_time_completion_rate(
        db: AsyncSession,
        user_id: UUID
    ) -> Optional[float]:
        """
        Вычислить процент выполнения задач в срок
        
        Returns:
            Процент выполнения в срок (0-100) или None, если нет выполненных задач
        """
        # Получаем все выполненные задачи пользователя с дедлайнами
        completed_assignments_query = select(TaskAssignment, Task).join(Task).where(
            TaskAssignment.user_id == user_id,
            TaskAssignment.status == AssignmentStatus.COMPLETED,
            TaskAssignment.completed_at.isnot(None),
            Task.due_date.isnot(None)
        )
        completed_result = await db.execute(completed_assignments_query)
        completed_items = completed_result.all()
        
        if not completed_items:
            return None
        
        on_time_count = 0
        total_count = len(completed_items)
        
        for assignment, task in completed_items:
            # Задача выполнена в срок, если completed_at <= due_date
            if assignment.completed_at and task.due_date:
                if assignment.completed_at <= task.due_date:
                    on_time_count += 1
        
        if total_count == 0:
            return None
        
        return (on_time_count / total_count) * 100
    
    @staticmethod
    async def _calculate_average_completion_time(
        db: AsyncSession,
        user_id: UUID
    ) -> Optional[float]:
        """
        Вычислить среднее время выполнения задачи (в днях)
        
        Returns:
            Среднее время выполнения в днях или None, если нет выполненных задач
        """
        # Получаем все выполненные задачи пользователя
        completed_assignments_query = select(TaskAssignment, Task).join(Task).where(
            TaskAssignment.user_id == user_id,
            TaskAssignment.status == AssignmentStatus.COMPLETED,
            TaskAssignment.completed_at.isnot(None),
            TaskAssignment.assigned_at.isnot(None)
        )
        completed_result = await db.execute(completed_assignments_query)
        completed_items = completed_result.all()
        
        if not completed_items:
            return None
        
        total_days = 0
        count = 0
        
        for assignment, task in completed_items:
            if assignment.assigned_at and assignment.completed_at:
                delta = assignment.completed_at - assignment.assigned_at
                total_days += delta.total_seconds() / (24 * 3600)  # Конвертируем в дни
                count += 1
        
        if count == 0:
            return None
        
        return total_days / count
