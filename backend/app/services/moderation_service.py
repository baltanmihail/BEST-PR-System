"""
Сервис модерации пользователей и заявок
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone

from app.models.user import User, UserRole
from app.models.moderation import ModerationQueue, ModerationStatus
from app.models.task import Task


class ModerationService:
    """Сервис для работы с модерацией"""
    
    @staticmethod
    async def create_user_application(
        db: AsyncSession,
        user_id: UUID,
        application_data: Dict
    ) -> ModerationQueue:
        """Создать заявку на регистрацию пользователя"""
        # Проверяем, нет ли уже заявки
        existing_query = select(ModerationQueue).where(
            and_(
                ModerationQueue.user_id == user_id,
                ModerationQueue.status == ModerationStatus.PENDING,
                ModerationQueue.task_id.is_(None)  # Заявка на регистрацию (не на задачу)
            )
        )
        existing_result = await db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            return existing
        
        application = ModerationQueue(
            user_id=user_id,
            task_id=None,
            application_data=application_data,
            status=ModerationStatus.PENDING
        )
        
        db.add(application)
        await db.commit()
        await db.refresh(application)
        
        return application
    
    @staticmethod
    async def get_pending_applications(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[ModerationQueue], int]:
        """Получить список заявок на модерацию"""
        query = select(ModerationQueue).where(
            ModerationQueue.status == ModerationStatus.PENDING
        ).order_by(ModerationQueue.created_at.desc())
        
        count_query = select(func.count(ModerationQueue.id)).where(
            ModerationQueue.status == ModerationStatus.PENDING
        )
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        applications = result.scalars().all()
        
        return list(applications), total
    
    @staticmethod
    async def approve_user_application(
        db: AsyncSession,
        application_id: UUID,
        moderator_id: UUID
    ) -> Optional[ModerationQueue]:
        """Одобрить заявку пользователя"""
        application = await db.execute(
            select(ModerationQueue).where(ModerationQueue.id == application_id)
        )
        application = application.scalar_one_or_none()
        
        if not application or application.status != ModerationStatus.PENDING:
            return None
        
        # Получаем пользователя
        user_query = select(User).where(User.id == application.user_id)
        user_result = await db.execute(user_query)
        user = user_result.scalar_one()
        
        # Активируем пользователя
        user.is_active = True
        
        # Обновляем заявку
        application.status = ModerationStatus.APPROVED
        application.decision_by = moderator_id
        application.decision_at = datetime.now(timezone.utc)
        
        # Удаляем напоминания о регистрации, так как пользователь одобрен
        if user.telegram_id:
            from app.models.onboarding import OnboardingReminder
            from sqlalchemy import delete
            await db.execute(
                delete(OnboardingReminder).where(
                    OnboardingReminder.telegram_id == str(user.telegram_id)
                )
            )
        
        await db.commit()
        await db.refresh(application)
        
        return application
    
    @staticmethod
    async def reject_user_application(
        db: AsyncSession,
        application_id: UUID,
        moderator_id: UUID,
        reason: str
    ) -> Optional[ModerationQueue]:
        """Отклонить заявку пользователя"""
        application = await db.execute(
            select(ModerationQueue).where(ModerationQueue.id == application_id)
        )
        application = application.scalar_one_or_none()
        
        if not application or application.status != ModerationStatus.PENDING:
            return None
        
        # Обновляем заявку
        application.status = ModerationStatus.REJECTED
        application.decision_by = moderator_id
        application.decision_at = datetime.now(timezone.utc)
        # Сохраняем причину в application_data
        if isinstance(application.application_data, dict):
            application.application_data["rejection_reason"] = reason
            
        # Удаляем напоминания о регистрации, чтобы не беспокоить отклоненного пользователя
        telegram_id = None
        if isinstance(application.application_data, dict):
            telegram_id = application.application_data.get("telegram_id")
        
        if telegram_id:
            from app.models.onboarding import OnboardingReminder
            from sqlalchemy import delete
            await db.execute(
                delete(OnboardingReminder).where(
                    OnboardingReminder.telegram_id == str(telegram_id)
                )
            )
        
        await db.commit()
        await db.refresh(application)
        
        return application
    
    @staticmethod
    async def get_user_application(
        db: AsyncSession,
        user_id: UUID
    ) -> Optional[ModerationQueue]:
        """Получить заявку пользователя"""
        query = select(ModerationQueue).where(
            and_(
                ModerationQueue.user_id == user_id,
                ModerationQueue.task_id.is_(None)
            )
        ).order_by(ModerationQueue.created_at.desc())
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
