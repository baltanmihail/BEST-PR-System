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
            # Используем .value для PostgreSQL ENUM (lowercase)
            type=notification_type.value if isinstance(notification_type, NotificationType) else notification_type,
            title=title,
            message=message,
            data=json.dumps(data) if data else None,
            is_read=False
        )
        
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        return notification
    
    # Храним уведомления не более 21 дня (3 недели)
    NOTIFICATION_RETENTION_DAYS = 21

    @staticmethod
    async def get_user_notifications(
        db: AsyncSession,
        user_id: UUID,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[List[Notification], int]:
        """Получить уведомления пользователя (не старше 21 дня)"""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=NotificationService.NOTIFICATION_RETENTION_DAYS)
        query = select(Notification).where(
            Notification.user_id == user_id,
            Notification.created_at >= cutoff
        )
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        count_query = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.created_at >= cutoff
        )
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
        """Получить количество непрочитанных уведомлений (не старше 21 дня)"""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=NotificationService.NOTIFICATION_RETENTION_DAYS)
        query = select(func.count(Notification.id)).where(
            and_(
                Notification.user_id == user_id,
                Notification.is_read == False,
                Notification.created_at >= cutoff
            )
        )
        result = await db.execute(query)
        return result.scalar_one() or 0

    @staticmethod
    async def cleanup_old_notifications(db: AsyncSession) -> int:
        """Удалить уведомления старше 21 дня из БД."""
        from datetime import timedelta
        from sqlalchemy import delete
        cutoff = datetime.now(timezone.utc) - timedelta(days=NotificationService.NOTIFICATION_RETENTION_DAYS)
        stmt = delete(Notification).where(Notification.created_at < cutoff)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0
    
    @staticmethod
    async def _send_task_telegram(db: AsyncSession, user_id: UUID, message: str):
        """Helper: send Telegram message to a user by their user_id."""
        try:
            from app.utils.telegram_sender import send_telegram_message
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.telegram_id and user.telegram_id > 0:
                await send_telegram_message(chat_id=user.telegram_id, message=message, parse_mode="HTML")
        except Exception as e:
            import logging
            logging.warning(f"TG notification to user {user_id} failed: {e}")

    @staticmethod
    async def notify_task_assigned(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Уведомить о назначении задачи (in-app + Telegram)"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_ASSIGNED,
            title="Новая задача",
            message=f"Вам назначена задача: {task_title}",
            data={"task_id": str(task_id)}
        )
        await NotificationService._send_task_telegram(
            db, user_id,
            f"📋 <b>Вам назначена задача</b>\n\n<b>{task_title}</b>\n\nОткройте систему для подробностей."
        )

    @staticmethod
    async def notify_task_completed(
        db: AsyncSession,
        user_id: UUID,
        task_id: UUID,
        task_title: str
    ):
        """Уведомить о завершении задачи (in-app + Telegram)"""
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_COMPLETED,
            title="Задача завершена",
            message=f"Задача '{task_title}' завершена. Баллы начислены!",
            data={"task_id": str(task_id)}
        )
        await NotificationService._send_task_telegram(
            db, user_id,
            f"✅ <b>Задача завершена</b>\n\n<b>{task_title}</b>\n\nБаллы начислены!"
        )
    
    @staticmethod
    async def notify_moderation_approved(
        db: AsyncSession,
        user_id: UUID
    ):
        """Уведомить об одобрении заявки с мотивирующим сообщением"""
        # Получаем пользователя
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            return
        
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
        
        # Мотивирующее сообщение с похвалой
        message = f"""🎉 <b>Поздравляем, {user.full_name}!</b>

✅ <b>Ваша заявка одобрена!</b>

Ты теперь официальный участник PR-отдела BEST Москва! 🚀

💪 <b>Ты молодец, что решил присоединиться к нам!</b>

🎯 <b>Что дальше?</b>
• 📝 Можешь брать интересные задачи
• 🎬 Бронировать оборудование для съёмок
• 🏆 Участвовать в рейтинге и зарабатывать баллы
• 💡 Развиваться вместе с командой энтузиастов

👥 <b>Наши координаторы:</b>
{coord_info if coord_info else "• Информация о координаторах доступна в разделе 'Помощь'"}

💬 <b>Есть вопросы?</b> Напиши координатору своего направления или VP4PR (@bfm5451)

🌐 <b>Перейди на сайт</b> и посмотри доступные задачи!

Удачи в работе! 🚀"""
        
        # Уведомляем всех зарегистрированных пользователей о новом участнике (ненавязчиво)
        await NotificationService.notify_new_user_joined(db=db, new_user_id=user_id)
        
        # Пытаемся добавить пользователя в общий чат и получаем ссылку
        from app.utils.telegram_sender import send_telegram_message
        from app.config import settings
        from app.services.telegram_chat_service import TelegramChatService
        
        general_chat_link = ""
        try:
            general_chat = await TelegramChatService.get_or_create_general_chat(db)
            if general_chat:
                # Пытаемся добавить пользователя в чат
                added = await TelegramChatService.add_user_to_chat(
                    chat_id=general_chat.chat_id,
                    user_telegram_id=user.telegram_id,
                    user_full_name=user.full_name
                )
                
                if added:
                    # Если пользователь успешно добавлен, отправляем приветственное сообщение в чат
                    await TelegramChatService.send_welcome_message_to_chat(
                        chat_id=general_chat.chat_id,
                        user_full_name=user.full_name,
                        is_new_user=True
                    )
                else:
                    # Если не удалось добавить автоматически, получаем ссылку-приглашение
                    invite_link = await TelegramChatService.get_chat_invite_link(db, general_chat.chat_id)
                    if invite_link:
                        general_chat_link = f"\n💬 <a href=\"{invite_link}\">Присоединиться к общему чату команды</a>"
        except Exception as e:
            import logging
            logging.error(f"Failed to add user {user.telegram_id} to general chat: {e}")
            # В случае ошибки всё равно получаем ссылку, если чат существует
            try:
                general_chat = await TelegramChatService.get_general_chat(db)
                if general_chat:
                    invite_link = await TelegramChatService.get_chat_invite_link(db, general_chat.chat_id)
                    if invite_link:
                        general_chat_link = f"\n💬 <a href=\"{invite_link}\">Присоединиться к общему чату команды</a>"
            except:
                pass
        
        # Формируем и отправляем сообщение в Telegram бот
        telegram_message = (
            f"🎉 <b>Поздравляем, {user.full_name}!</b>\n\n"
            f"✅ <b>Ваша заявка одобрена!</b>\n\n"
            f"Ты теперь официальный участник PR-отдела BEST Москва! 🚀\n\n"
            f"💪 <b>Ты молодец, что решил присоединиться к нам!</b>\n\n"
            f"🎯 <b>Что дальше?</b>\n"
            f"• 📝 Можешь брать интересные задачи\n"
            f"• 🎬 Бронировать оборудование для съёмок\n"
            f"• 🏆 Участвовать в рейтинге и зарабатывать баллы\n"
            f"{general_chat_link}\n"
            f"🌐 <a href=\"{settings.FRONTEND_URL}?from=bot&telegram_id={user.telegram_id}&approved=true\">Перейти на сайт</a>"
        )
        
        try:
            await send_telegram_message(
                chat_id=user.telegram_id,
                message=telegram_message,
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send Telegram notification to user {user.telegram_id}: {e}")
        
        # Создаём уведомление в системе (после отправки в Telegram)
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
        
        # Отправляем уведомление всем админам (in-app + Telegram)
        from app.utils.telegram_sender import send_telegram_message
        tg_text = (
            f"👤 <b>Новая заявка на регистрацию</b>\n\n"
            f"Имя: <b>{user_name}</b>\n"
            f"Telegram ID: <code>{user_telegram_id}</code>\n\n"
            f"Подтвердите или отклоните заявку на сайте."
        )
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
            if admin.telegram_id and admin.telegram_id > 0:
                try:
                    await send_telegram_message(
                        chat_id=admin.telegram_id,
                        message=tg_text,
                        parse_mode="HTML",
                        silent_fail=True,
                    )
                except Exception:
                    pass
    
    @staticmethod
    async def notify_moderation_rejected(
        db: AsyncSession,
        user_id: UUID,
        reason: str
    ):
        """Уведомить об отклонении заявки с возможностью связаться с админом"""
        # Получаем пользователя
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()
        
        if not user:
            return
        
        message = f"""❌ <b>К сожалению, ваша заявка отклонена</b>

<b>Причина:</b> {reason}

💬 <b>Если у вас есть вопросы или вы хотите обсудить решение:</b>
• Напишите VP4PR напрямую: @bfm5451
• Или задайте вопрос через поддержку на сайте

Мы всегда готовы помочь и ответить на ваши вопросы!"""
        
        # Создаём уведомление в системе
        await NotificationService.create_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.MODERATION_REJECTED,
            title="Заявка отклонена",
            message=message,
            data={"reason": reason}
        )
        
        # Отправляем сообщение в Telegram бот
        from app.utils.telegram_sender import send_telegram_message
        from app.config import settings
        
        telegram_message = (
            f"❌ <b>К сожалению, ваша заявка отклонена</b>\n\n"
            f"<b>Причина:</b> {reason}\n\n"
            f"💬 <b>Если у вас есть вопросы или вы хотите обсудить решение:</b>\n"
            f"• Напишите VP4PR напрямую: @bfm5451\n"
            f"• Или задайте вопрос через поддержку на сайте\n\n"
            f"Мы всегда готовы помочь и ответить на ваши вопросы!"
        )
        
        try:
            await send_telegram_message(
                chat_id=user.telegram_id,
                message=telegram_message,
                parse_mode="HTML"
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send Telegram notification to user {user.telegram_id}: {e}")
    
    @staticmethod
    async def notify_new_task(
        db: AsyncSession,
        user_ids: List[UUID],
        task_id: UUID,
        task_title: str,
        task_type: str
    ):
        """Уведомить о новой задаче (in-app + Telegram)"""
        type_labels = {'smm': 'SMM', 'design': 'Дизайн', 'channel': 'Channel', 'prfr': 'PR-FR', 'multitask': 'Мульти'}
        type_label = type_labels.get(task_type, task_type)
        for user_id in user_ids:
            await NotificationService.create_notification(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.NEW_TASK,
                title="Новая задача",
                message=f"Доступна новая задача типа {task_type}: {task_title}",
                data={"task_id": str(task_id), "task_type": task_type}
            )
            await NotificationService._send_task_telegram(
                db, user_id,
                f"🆕 <b>Новая задача [{type_label}]</b>\n\n<b>{task_title}</b>\n\nОткройте систему, чтобы взять задачу."
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
    
    @staticmethod
    async def notify_new_user_joined(
        db: AsyncSession,
        new_user_id: UUID
    ):
        """Уведомить всех зарегистрированных пользователей о новом участнике (ненавязчиво)"""
        # Получаем нового пользователя
        new_user_result = await db.execute(select(User).where(User.id == new_user_id))
        new_user = new_user_result.scalar_one_or_none()
        
        if not new_user:
            return
        
        # Получаем всех активных зарегистрированных пользователей (кроме самого нового)
        all_users_result = await db.execute(
            select(User).where(
                and_(
                    User.is_active == True,
                    User.id != new_user_id,
                    User.deleted_at.is_(None)
                )
            )
        )
        all_users = all_users_result.scalars().all()
        
        # Отправляем ненавязчивое уведомление всем (неважное, чтобы не раздражать)
        message = f"👋 Поздоровайтесь с новым участником: <b>{new_user.full_name}</b>!"
        
        for user in all_users:
            # Создаём ненавязчивое уведомление (неважное, чтобы не раздражать)
            await NotificationService.create_notification(
                db=db,
                user_id=user.id,
                notification_type=NotificationType.SYSTEM,  # Системное уведомление
                title="Новый участник",
                message=message,
                data={"new_user_id": str(new_user_id), "new_user_name": new_user.full_name}
            )
