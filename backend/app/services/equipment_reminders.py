"""
Сервис напоминаний о выдаче и возврате оборудования
Аналогично BEST Channel Bot: напоминания за день до события
"""
import logging
from typing import List, Dict, Optional
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus
from app.models.user import User, UserRole
from app.services.google_service import GoogleService

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
        
        Args:
            db: Сессия БД
            bot: Экземпляр Telegram бота (опционально)
        
        Returns:
            Словарь с результатами отправки напоминаний
        """
        try:
            # Получаем все одобренные и активные заявки
            requests_query = select(EquipmentRequest).where(
                EquipmentRequest.status.in_([
                    EquipmentRequestStatus.APPROVED,
                    EquipmentRequestStatus.ACTIVE
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
            
            # Получаем координаторов и VP4PR для отправки напоминаний
            coordinators_query = select(User).where(
                User.role.in_([
                    UserRole.COORDINATOR_PRFR,
                    UserRole.VP4PR
                ])
            )
            coordinators_result = await db.execute(coordinators_query)
            coordinators = coordinators_result.scalars().all()
            
            for req in requests:
                if not req.user or not req.equipment:
                    continue
                
                # Напоминания о выдаче (за день до выдачи)
                days_until_issue = (req.start_date - today).days
                if days_until_issue == 1:
                    await self._send_issue_reminder(
                        req=req,
                        user=req.user,
                        coordinators=coordinators,
                        bot=bot
                    )
                    reminders_sent += 1
                
                # Напоминания о возврате (за день до возврата)
                days_until_return = (req.end_date - today).days
                if days_until_return == 1:
                    await self._send_return_reminder(
                        req=req,
                        user=req.user,
                        coordinators=coordinators,
                        bot=bot
                    )
                    reminders_sent += 1
            
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
        bot=None
    ):
        """Отправить напоминание о выдаче оборудования"""
        try:
            equipment_name = req.equipment.name if req.equipment else "Неизвестно"
            
            # Получаем название съёмки
            shooting_name = "Не указано"
            if req.task:
                shooting_name = req.task.title if req.task.title else "Не указано"
            
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
            
            # Отправляем пользователю
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
            
            # Отправляем координаторам
            if bot:
                for coord in coordinators:
                    if coord.telegram_id:
                        try:
                            await bot.send_message(
                                chat_id=coord.telegram_id,
                                text=message_text,
                                parse_mode="HTML"
                            )
                            logger.info(f"✅ Напоминание о выдаче отправлено координатору {coord.telegram_id}")
                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания координатору {coord.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о выдаче: {e}", exc_info=True)
    
    async def _send_return_reminder(
        self,
        req: EquipmentRequest,
        user: User,
        coordinators: List[User],
        bot=None
    ):
        """Отправить напоминание о возврате оборудования"""
        try:
            equipment_name = req.equipment.name if req.equipment else "Неизвестно"
            
            # Получаем название съёмки
            shooting_name = "Не указано"
            if req.task:
                shooting_name = req.task.title if req.task.title else "Не указано"
            
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
            
            # Отправляем пользователю
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
            
            # Отправляем координаторам
            if bot:
                for coord in coordinators:
                    if coord.telegram_id:
                        try:
                            await bot.send_message(
                                chat_id=coord.telegram_id,
                                text=message_text,
                                parse_mode="HTML"
                            )
                            logger.info(f"✅ Напоминание о возврате отправлено координатору {coord.telegram_id}")
                        except Exception as e:
                            logger.error(f"Ошибка отправки напоминания координатору {coord.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки напоминания о возврате: {e}", exc_info=True)
