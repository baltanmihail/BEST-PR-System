"""
Сервис для работы с мероприятиями
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from uuid import UUID

from app.models.event import Event


class EventService:
    """Сервис для работы с мероприятиями"""
    
    @staticmethod
    async def get_events(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Event], int]:
        """Получить список мероприятий"""
        query = select(Event)
        count_query = select(func.count(Event.id))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.order_by(Event.date_start.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        events = result.scalars().all()
        
        return list(events), total
    
    @staticmethod
    async def get_event_by_id(
        db: AsyncSession,
        event_id: UUID
    ) -> Optional[Event]:
        """Получить мероприятие по ID"""
        query = select(Event).where(Event.id == event_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_event_tasks(
        db: AsyncSession,
        event_id: UUID
    ) -> List:
        """Получить задачи мероприятия"""
        from app.models.task import Task
        
        query = select(Task).where(Task.event_id == event_id)
        result = await db.execute(query)
        tasks = result.scalars().all()
        return list(tasks)
