"""
Сервис напоминаний о выдаче и возврате оборудования
Аналогично BEST Channel Bot: напоминания за день до события
VP4PR, глава Channel и пользователь получают уведомления (Telegram + сайт)
"""
import logging
from typing import List, Dict, Optional
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, cast, String

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus
from app.models.user import User, UserRole
from app.models.notification import NotificationType
from app.services.google_service import GoogleService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class EquipmentReminders:
    """Сервис для отправки напоминаний о выдаче и возврате оборудования"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
    
    async def check_and_send_reminders(
        self,
        db: AsyncSession,
        bot=None  # Telegram bot instance
    ) -> dict:
        """
        Проверяет даты выдачи и возврата и отправляет напоминания за день до события
        """
        # Если бот не передан, пытаемся получить его через get_bot
        if not bot:
            from app.utils.telegram_sender import get_bot
            bot = await get_bot()
            
        if not bot:
            logger.warning("Bot instance not available for reminders")
            return {
                "status": "skipped",
                "reason": "bot_not_available"
            }

        try:
            # Получаем все одобренные и активные заявки
            # Используем cast для совместимости с PostgreSQL ENUM
            requests_query = select(EquipmentRequest).where(
                cast(EquipmentRequest.status, String).in_([
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value
                ])
            )
            result = await db.execute(requests_query)
            requests = result.scalars().all()
            
            if not requests:
                return {
                    "status": "skipped",
                    "reason": "no_approved_requests"
                }
            
            # Загружаем связанные данные
            for req in requests:
                from app.models.equipment import Equipment
                equipment_result = await db.execute(
                    select(Equipment).where(Equipment.id == req.equipment_id)
                )
                req.equipment = equipment_result.scalar_one_or_none()
                
                user_result = await db.execute(
                    select(User).where(User.id == req.user_id)
                )
                req.user = user_result.scalar_one_or_none()
                
                # Получаем задачу для даты съёмки
                if req.task_id:
                    from app.models.task import Task
                    task_result = await db.execute(
                        select(Task).where(Task.id == req.task_id)
                    )
                    req.task = task_result.scalar_one_or_none()
            
            today = date.today()
            reminders_sent = 0
            
            # VP4PR и глава Channel — получают напоминания за день до выдачи/возврата
            coordinators_query = select(User).where(
                User.role.in_([
                    UserRole.VP4PR,
                    UserRole.COORDINATOR_CHANNEL
                ])
            )
            coordinators_result = await db.execute(coordinators_query)
            coordinators = coordinators_result.scalars().all()
            
            for req in requests:
                if not req.user or not req.equipment:
                    continue
                
                # Напоминания о выдаче (за день до выдачи)
                days_until_issue = (req.start_date - today).days
                if days_until_issue == 1 and req.issue_reminder_sent_for != req.start_date:
                    await self._send_issue_reminder(
                        req=req,
                        user=req.user,
                        coordinators=coordinators,
                        bot=bot,
                        db=db
                    )
                    req.issue_reminder_sent_for = req.start_date
                    reminders_sent += 1
                
                # Напоминания о возврате (за день до возврата)
                days_until_return = (req.end_date - today).days
                if days_until_return == 1 and req.return_reminder_sent_for != req.end_date:
                    await self._send_return_reminder(
                        req=req,
                        user=req.user,
                        coordinators=coordinators,
                        bot=bot,
                        db=db
                    )
                    req.return_reminder_sent_for = req.end_date
                    reminders_sent += 1
            
            if reminders_sent > 0:
                await db.commit()
                # Обновляем дайджест координаторам (одно сообщение, по важности)
                from app.services.equipment_digest_service import EquipmentDigestService
                await EquipmentDigestService.update_digest_for_coordinators(db, bot)
                # Батч-уведомление на сайте для VP4PR и Channel (одно на день)
                await EquipmentReminders._create_coordinator_site_batch(db, requests, today)
            
            logger.info(f"✅ Отправлено {reminders_sent} напоминаний")
            
            return {
                "status": "success",
                "reminders_sent": reminders_sent
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки напоминаний: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _send_issue_reminder(
        self,
        req: EquipmentRequest,
        user: User,
        coordinators: List[User],
        bot=None,
        db=None
    ):
        """Отправить напоминание о выдаче оборудования (VP4PR, глава Channel, пользователь)"""
        try:
            equipment_name = req.equipment.name if req.equipment else "Неизвестно"
            
            # Получаем название съёмки
            shooting_name = "Не указано"
            if req.task:
                shooting_name = req.task.title if req.task.title else "Не указано"
            
            short_msg = f"Завтра выдача: {equipment_name} — {user.full_name or f'{user.first_name} {user.last_name}'.strip()}"
            message_text = (
                f"🔔 <b>Напоминание о выдаче оборудования</b>\n\n"
                f"📋 <b>Заявка #{str(req.id)[:8]}</b>\n\n"
                f"👤 <b>ФИО:</b> {user.full_name or f'{user.first_name} {user.last_name}'.strip()}\n"
            )
            
            if user.telegram_username:
                message_text += f"📱 <b>Telegram:</b> <a href=\"https://t.me/{user.telegram_username.lstrip('@')}\">@{user.telegram_username.lstrip('@')}</a>\n"
            
            message_text += (
                f"🎬 <b>Съёмка:</b> {shooting_name}\n"
                f"📦 <b>Оборудование:</b> {equipment_name}\n"
                f"📅 <b>Дата выдачи:</b> {req.start_date.strftime('%d.%m.%Y')}\n"
                f"📅 <b>Дата возврата:</b> {req.end_date.strftime('%d.%m.%Y')}\n\n"
                f"⏰ До выдачи остался <b>1 день</b>"
            )
            
            # Уведомление на сайте: пользователь (кратко)
            if db:
                await self._create_site_notification(db, user.id, "Напоминание о выдаче", short_msg, req)
            # VP4PR и Channel — обновим дайджест в конце (одним вызовом)
            
            # Отправляем пользователю в Telegram
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Напоминание о выдаче отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")
            
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о выдаче: {e}", exc_info=True)
    
    async def _create_site_notification(
        self,
        db: AsyncSession,
        user_id: UUID,
        title: str,
        message: str,
        req: EquipmentRequest
    ):
        """Создать уведомление на сайте (в панели уведомлений)"""
        try:
            await NotificationService.create_notification(
                db=db,
                user_id=user_id,
                notification_type=NotificationType.EQUIPMENT_REQUEST,
                title=title,
                message=message,
                data={"request_id": str(req.id), "equipment_id": str(req.equipment_id)}
            )
        except Exception as e:
            logger.warning(f"Не удалось создать уведомление на сайте для {user_id}: {e}")

    @staticmethod
    async def _create_coordinator_site_batch(db: AsyncSession, requests: list, today) -> None:
        """Одно батч-уведомление на сайте для VP4PR и Channel (по типу/пользователю)."""
        from datetime import date
        from collections import defaultdict
        today = today or date.today()
        by_user_issue = defaultdict(list)
        by_user_return = defaultdict(list)
        for req in requests:
            if not req.user or not req.equipment:
                continue
            fio = (req.user.full_name or f"{req.user.first_name or ''} {req.user.last_name or ''}".strip()) or "—"
            eq = req.equipment.name if req.equipment else "?"
            if (req.start_date - today).days == 1:
                by_user_issue[fio].append(eq)
            if (req.end_date - today).days == 1:
                by_user_return[fio].append(eq)
        if not by_user_issue and not by_user_return:
            return
        parts = []
        for fio in sorted(set(by_user_issue) | set(by_user_return)):
            p = []
            if fio in by_user_issue:
                p.append(f"Выдача: {', '.join(by_user_issue[fio][:3])}" + (f" +{len(by_user_issue[fio])-3}" if len(by_user_issue[fio]) > 3 else ""))
            if fio in by_user_return:
                p.append(f"Возврат: {', '.join(by_user_return[fio][:3])}" + (f" +{len(by_user_return[fio])-3}" if len(by_user_return[fio]) > 3 else ""))
            if p:
                parts.append(f"{fio}: {'; '.join(p)}")
        msg = "Завтра (срочно)\n" + "\n".join(parts[:8])
        coord_result = await db.execute(select(User).where(User.role.in_([UserRole.VP4PR, UserRole.COORDINATOR_CHANNEL])))
        for coord in coord_result.scalars().all():
            if coord.id:
                try:
                    await NotificationService.create_notification(db, coord.id, NotificationType.EQUIPMENT_REQUEST, "Оборудование: завтра", msg, None)
                except Exception as e:
                    logger.warning(f"Не удалось создать батч-уведомление для {coord.id}: {e}")
    
    async def _send_return_reminder(
        self,
        req: EquipmentRequest,
        user: User,
        coordinators: List[User],
        bot=None,
        db=None
    ):
        """Отправить напоминание о возврате оборудования (VP4PR, глава Channel, пользователь)"""
        try:
            equipment_name = req.equipment.name if req.equipment else "Неизвестно"
            
            # Получаем название съёмки
            shooting_name = "Не указано"
            if req.task:
                shooting_name = req.task.title if req.task.title else "Не указано"
            
            short_msg = f"Завтра возврат: {equipment_name} — {user.full_name or f'{user.first_name} {user.last_name}'.strip()}"
            message_text = (
                f"🔔 <b>Напоминание о возврате оборудования</b>\n\n"
                f"📋 <b>Заявка #{str(req.id)[:8]}</b>\n\n"
                f"👤 <b>ФИО:</b> {user.full_name or f'{user.first_name} {user.last_name}'.strip()}\n"
            )
            
            if user.telegram_username:
                message_text += f"📱 <b>Telegram:</b> <a href=\"https://t.me/{user.telegram_username.lstrip('@')}\">@{user.telegram_username.lstrip('@')}</a>\n"
            
            message_text += (
                f"🎬 <b>Съёмка:</b> {shooting_name}\n"
                f"📦 <b>Оборудование:</b> {equipment_name}\n"
                f"📅 <b>Дата выдачи:</b> {req.start_date.strftime('%d.%m.%Y')}\n"
                f"📅 <b>Дата возврата:</b> {req.end_date.strftime('%d.%m.%Y')}\n\n"
                f"⏰ До возврата остался <b>1 день</b>"
            )
            
            # Уведомление на сайте: пользователь (кратко)
            if db:
                await self._create_site_notification(db, user.id, "Напоминание о возврате", short_msg, req)
            # VP4PR и Channel — дайджест обновится в конце check_and_send_reminders
            
            # Отправляем пользователю в Telegram
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Напоминание о возврате отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки напоминания пользователю {user.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о возврате: {e}", exc_info=True)
