"""
Сервис для работы с задачами
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID

from app.models.task import Task, TaskType, TaskStatus, TaskPriority, TaskAssignment, TaskStage, StageStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from datetime import timedelta, datetime, timezone


class TaskService:
    """Сервис для работы с задачами"""
    
    @staticmethod
    async def get_tasks(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        created_by: Optional[UUID] = None
    ) -> tuple[List[Task], int]:
        """
        Получить список задач с фильтрацией и пагинацией
        
        Returns:
            tuple: (список задач, общее количество)
        """
        # Базовый запрос
        query = select(Task)
        count_query = select(func.count(Task.id))
        
        # Применяем фильтры
        conditions = []
        
        if task_type:
            conditions.append(Task.type == task_type)
        if status:
            conditions.append(Task.status == status)
        if priority:
            conditions.append(Task.priority == priority)
        if created_by:
            conditions.append(Task.created_by == created_by)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Получаем общее количество
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # Применяем пагинацию и сортировку
        query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
        
        # Загружаем связанные данные
        query = query.options(
            selectinload(Task.stages),
            selectinload(Task.assignments).selectinload(TaskAssignment.user)
        )
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return list(tasks), total
    
    @staticmethod
    async def get_task_by_id(
        db: AsyncSession,
        task_id: UUID
    ) -> Optional[Task]:
        """Получить задачу по ID"""
        query = select(Task).where(Task.id == task_id)
        query = query.options(
            selectinload(Task.stages),
            selectinload(Task.assignments).selectinload(TaskAssignment.user)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_task(
        db: AsyncSession,
        task_data: TaskCreate,
        created_by: UUID
    ) -> Task:
        """Создать новую задачу"""
        task = Task(
            **task_data.model_dump(),
            created_by=created_by,
            status=TaskStatus.DRAFT  # Новые задачи создаются как черновики
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        return task
    
    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: UUID,
        task_data: TaskUpdate,
        current_user: User
    ) -> Optional[Task]:
        """Обновить задачу"""
        task = await TaskService.get_task_by_id(db, task_id)
        
        if not task:
            return None
        
        # Проверка прав (только создатель или координатор)
        from app.models.user import UserRole
        if task.created_by != current_user.id and current_user.role not in [
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN, 
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
        ]:
            return None
        
        # Обновляем поля
        update_data = task_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(task, field, value)
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    @staticmethod
    async def delete_task(
        db: AsyncSession,
        task_id: UUID,
        current_user: User
    ) -> bool:
        """Удалить задачу"""
        task = await TaskService.get_task_by_id(db, task_id)
        
        if not task:
            return False
        
        # Проверка прав (только создатель или VP4PR)
        from app.models.user import UserRole
        if task.created_by != current_user.id and current_user.role != UserRole.VP4PR:
            return False
        
        # Удаляем задачу
        # В SQLAlchemy 2.0 async используем delete() напрямую
        from sqlalchemy import delete
        await db.execute(delete(Task).where(Task.id == task_id))
        await db.commit()
        
        return True
