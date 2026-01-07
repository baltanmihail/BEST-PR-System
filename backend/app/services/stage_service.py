"""
Сервис для работы с этапами задач
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID

from app.models.task import TaskStage, StageStatus
from app.schemas.task import TaskStageCreate, TaskStageUpdate


class StageService:
    """Сервис для работы с этапами задач"""
    
    @staticmethod
    async def get_stages_by_task(
        db: AsyncSession,
        task_id: UUID
    ) -> List[TaskStage]:
        """Получить все этапы задачи"""
        query = select(TaskStage).where(
            TaskStage.task_id == task_id
        ).order_by(TaskStage.stage_order)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_stage_by_id(
        db: AsyncSession,
        stage_id: UUID
    ) -> Optional[TaskStage]:
        """Получить этап по ID"""
        query = select(TaskStage).where(TaskStage.id == stage_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_stage(
        db: AsyncSession,
        task_id: UUID,
        stage_data: TaskStageCreate
    ) -> TaskStage:
        """Создать новый этап"""
        stage = TaskStage(
            task_id=task_id,
            **stage_data.model_dump()
        )
        
        db.add(stage)
        await db.commit()
        await db.refresh(stage)
        
        return stage
    
    @staticmethod
    async def update_stage(
        db: AsyncSession,
        stage_id: UUID,
        stage_data: TaskStageUpdate
    ) -> Optional[TaskStage]:
        """Обновить этап"""
        stage = await StageService.get_stage_by_id(db, stage_id)
        
        if not stage:
            return None
        
        # Обновляем поля
        update_data = stage_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(stage, field, value)
        
        # Если статус меняется на completed, устанавливаем completed_at
        if update_data.get('status') == StageStatus.COMPLETED and not stage.completed_at:
            from datetime import datetime
            stage.completed_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(stage)
        
        return stage
    
    @staticmethod
    async def delete_stage(
        db: AsyncSession,
        stage_id: UUID
    ) -> bool:
        """Удалить этап"""
        stage = await StageService.get_stage_by_id(db, stage_id)
        
        if not stage:
            return False
        
        await db.delete(stage)
        await db.commit()
        
        return True
