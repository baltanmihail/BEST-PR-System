"""
Сервис уведомлений
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone
import json

from app.models.notification import Notification, NotificationType
from app.models.user import User


class NotificationService:
    """Сервис для работы с уведомлениями"""
    
    @staticmethod
    async def create_notification(
        db: AsyncSession,
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict] = None
    ) -> Notification:
        """Создать уведомление"""
        notification = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            data=json.dumps(data) if data else None,
            is_read=False
        )
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        return notification
    
    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[Notification], int]:
        """Получить уведомления пользователя"""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        count_query = select(func.count(Notification.id)).where(Notification.user_id == user_id)
        if unread_only:
            count_query = count_query.where(Notification.is_read == False)
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        notifications = result.scalars().all()
        
        return list(notifications), total
    
    @staticmethod
    async def mark_as_read(
        db: AsyncSession,
        notification_id: UUID,
        user_id: UUID
    ) -> Optional[Notification]:
        """Отметить уведомление как прочитанное"""
        query = select(Notification).where(
            and_(
                Notification.id == notification_id,
                Notification.user_id == user_id
            )
        )
        result = await db.execute(query)
        notification = result.scalar_one_or_none()
        
        if notification:
            notification.is_read = True
            await db.commit()
            await db.refresh(notification)
        
        return notification
    
    @staticmethod
    async def mark_all_as_read(
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """Отметить все уведомления пользователя как прочитанные"""
        from sqlalchemy import update
        
        stmt = update(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        ).values(is_read=True)
        
        result = await db.execute(stmt)
        await db.commit()
        
        return result.rowcount
    
    @staticmethod
    async def get_unread_count(
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """Получить количество непрочитанных уведомлений"""
        query = select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False
            )
        )
        result = await db.execute(query)
        return result.scalar_one() or 0
    
    @staticmethod
    async def notify_task_assigned(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Уведомить о назначении задачи"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_ASSIGNED,
            title="Новая задача",
            message=f"Вам назначена задача: {task_title}",
            data={"task_id": str(task_id)}
        )
    
    @staticmethod
    async def notify_task_completed(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Уведомить о завершении задачи"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_COMPLETED,
            title="Задача завершена",
            message=f"Задача '{task_title}' завершена. Баллы начислены!",
            data={"task_id": str(task_id)}
        )
    
    @staticmethod
    async def notify_moderation_approved(
        db: AsyncSession,
        user_id: UUID
    ):
        """Уведомить об одобрении заявки с мотивирующим сообщением"""
        # Получаем информацию о координаторах
        from app.models.user import UserRole
        coordinators_query = select(User).where(
            User.role.in_([
                UserRole.COORDINATOR_SMM,
                UserRole.COORDINATOR_DESIGN, 
                UserRole.COORDINATOR_CHANNEL,
                UserRole.COORDINATOR_PRFR,
                UserRole.VP4PR
            ])
        )
        coord_result = await db.execute(coordinators_query)
        coordinators = coord_result.scalars().all()
        
        coord_info = "\n".join([
            f"• {coord.full_name} ({coord.role.value.replace('coordinator_', '').upper() if 'coordinator' in coord.role.value else coord.role.value.upper()})"
            for coord in coordinators[:5]  # Показываем до 5 координаторов
        ])
        
        message = f"""🎉 Добро пожаловать в команду BEST Moscow!

Ваша заявка одобрена, теперь вы можете брать задачи и участвовать в проектах.

📋 Важно знать:
• Следите за дедлайнами - они критичны для успеха проекта
• Координаторы помогут вам разобраться с задачами
• Не стесняйтесь задавать вопросы - мы всегда готовы помочь

👥 Наши координаторы:
{coord_info if coord_info else "• Информация о координаторах доступна в разделе 'Помощь'"}

💬 Есть вопросы? Напишите координатору вашего направления или мне лично. Также можете прочитать раздел "Помощь" для детальной информации.

Удачи в работе! 🚀"""
        
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.MODERATION_APPROVED,
            title="🎉 Добро пожаловать в команду!",
            message=message,
            data=None
        )
    
    @staticmethod
    async def notify_moderation_request(
        db: AsyncSession,
        user_id: UUID,
        user_name: str,
        user_telegram_id: int
    ):
        """Уведомить админа о новой заявке на регистрацию"""
        # Находим всех координаторов и VP4PR
        from app.models.user import UserRole
        admins_query = select(User).where(
            User.role.in_([
                UserRole.COORDINATOR_SMM,
                UserRole.COORDINATOR_DESIGN,
                UserRole.COORDINATOR_CHANNEL, 
                UserRole.COORDINATOR_PRFR,
                UserRole.VP4PR
            ])
        )
        admins_result = await db.execute(admins_query)
        admins = admins_result.scalars().all()
        
        # Отправляем уведомление всем админам
        for admin in admins:
            await NotificationService.create_notification(
                db=db,
                user_id=admin.id,
                notification_type=NotificationType.MODERATION_REQUEST,
                title="Новая заявка на регистрацию",
                message=f"Пользователь {user_name} (@{user_telegram_id}) подал заявку на регистрацию. Можете уточнить детали в личном чате перед одобрением.",
                data={
                    "user_id": str(user_id),
                    "user_name": user_name,
                    "user_telegram_id": user_telegram_id
                }
            )
    
    @staticmethod
    async def notify_moderation_rejected(
        db: AsyncSession,
        user_id: UUID,
        reason: str
    ):
        """Уведомить об отклонении заявки"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.MODERATION_REJECTED,
            title="Заявка отклонена",
            message=f"Ваша заявка отклонена. Причина: {reason}",
            data={"reason": reason}
        )
    
    @staticmethod
    async def notify_new_task(
        db: AsyncSession,
        user_ids: List[UUID],
        task_id: UUID,
        task_title: str,
        task_type: str
    ):
        """Уведомить о новой задаче"""
        for user_id in user_ids:
            await NotificationService.create_notification(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.NEW_TASK,
                title="Новая задача",
                message=f"Доступна новая задача типа {task_type}: {task_title}",
                data={"task_id": str(task_id), "task_type": task_type}
            )
    
    @staticmethod
    async def notify_achievement_unlocked(
        db: AsyncSession,
        user_id: UUID,
        achievement_type: str,
        achievement_name: str
    ):
        """Уведомить о получении ачивки"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.ACHIEVEMENT_UNLOCKED,
            title="Новая ачивка!",
            message=f"Вы получили ачивку: {achievement_name}",
            data={"achievement_type": achievement_type}
        )
