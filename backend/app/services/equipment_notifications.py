"""
Сервис уведомлений об изменении статусов заявок на оборудование
Аналогично BEST Channel Bot: уведомления при одобрении, отклонении и т.д.
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)


class EquipmentNotifications:
    """Сервис для отправки уведомлений об изменении статусов заявок"""
    
    async def send_status_change_notifications(
        self,
        db: AsyncSession,
        status_changes: List[Dict],
        bot=None  # Telegram bot instance
    ) -> dict:
        """
        Отправляет уведомления пользователям об изменении статуса заявки
        
        Args:
            db: Сессия БД
            status_changes: Список изменений статусов [{'request_id': uuid, 'old_status': str, 'new_status': str, 'user_id': uuid}, ...]
            bot: Экземпляр Telegram бота (опционально)
        
        Returns:
            Словарь с результатами отправки уведомлений
        """
        try:
            notifications_sent = 0
            
            for change in status_changes:
                request_id = change.get('request_id')
                old_status = change.get('old_status')
                new_status = change.get('new_status')
                user_id = change.get('user_id')
                
                if not request_id or not user_id:
                    continue
                
                # Получаем заявку и пользователя
                request_result = await db.execute(
                    select(EquipmentRequest).where(EquipmentRequest.id == request_id)
                )
                request = request_result.scalar_one_or_none()
                
                user_result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not request or not user:
                    continue
                
                # Загружаем связанные данные
                from app.models.equipment import Equipment
                equipment_result = await db.execute(
                    select(Equipment).where(Equipment.id == request.equipment_id)
                )
                request.equipment = equipment_result.scalar_one_or_none()
                
                # Отправляем уведомление в зависимости от изменения статуса
                if old_status == EquipmentRequestStatus.PENDING.value and new_status == EquipmentRequestStatus.APPROVED.value:
                    # Статус изменился с "На рассмотрении" на "Одобрено"
                    await self._send_approval_notification(request, user, bot)
                    notifications_sent += 1
                
                elif old_status == EquipmentRequestStatus.PENDING.value and new_status == EquipmentRequestStatus.REJECTED.value:
                    # Статус изменился с "На рассмотрении" на "Отклонено"
                    rejection_reason = change.get('rejection_reason', 'Не указана')
                    await self._send_rejection_notification(request, user, rejection_reason, bot)
                    notifications_sent += 1
                
                elif old_status == EquipmentRequestStatus.APPROVED.value and new_status == EquipmentRequestStatus.PENDING.value:
                    # Статус изменился с "Одобрено" на "На рассмотрении" (откат одобрения)
                    await self._send_pending_notification(request, user, bot)
                    notifications_sent += 1
                
                elif old_status == EquipmentRequestStatus.REJECTED.value and new_status == EquipmentRequestStatus.PENDING.value:
                    # Статус изменился с "Отклонено" на "На рассмотрении" (восстановление заявки)
                    await self._send_restored_notification(request, user, bot)
                    notifications_sent += 1
                
                elif old_status == EquipmentRequestStatus.REJECTED.value and new_status == EquipmentRequestStatus.APPROVED.value:
                    # Статус изменился с "Отклонено" на "Одобрено" (исправление ошибки)
                    await self._send_approval_notification(request, user, bot)
                    notifications_sent += 1
            
            logger.info(f"✅ Отправлено {notifications_sent} уведомлений об изменении статусов")
            
            return {
                "status": "success",
                "notifications_sent": notifications_sent
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомлений: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _send_approval_notification(
        self,
        request: EquipmentRequest,
        user: User,
        bot=None
    ):
        """Отправить уведомление об одобрении заявки"""
        try:
            equipment_name = request.equipment.name if request.equipment else "Неизвестно"
            
            message_text = (
                f"✅ <b>Ваша заявка одобрена!</b>\n\n"
                f"📋 <b>Заявка #{str(request.id)[:8]}</b>\n\n"
                f"📦 <b>Оборудование:</b> {equipment_name}\n"
                f"📅 <b>Дата выдачи:</b> {request.start_date.strftime('%d.%m.%Y')}\n"
                f"📅 <b>Дата возврата:</b> {request.end_date.strftime('%d.%m.%Y')}\n\n"
                f"Вы получите напоминание за день до выдачи оборудования."
            )
            
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Уведомление об одобрении отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об одобрении: {e}", exc_info=True)
    
    async def _send_rejection_notification(
        self,
        request: EquipmentRequest,
        user: User,
        rejection_reason: str,
        bot=None
    ):
        """Отправить уведомление об отклонении заявки"""
        try:
            equipment_name = request.equipment.name if request.equipment else "Неизвестно"
            
            message_text = (
                f"❌ <b>Ваша заявка отклонена</b>\n\n"
                f"📋 <b>Заявка #{str(request.id)[:8]}</b>\n\n"
                f"📦 <b>Оборудование:</b> {equipment_name}\n"
                f"📅 <b>Дата выдачи:</b> {request.start_date.strftime('%d.%m.%Y')}\n"
                f"📅 <b>Дата возврата:</b> {request.end_date.strftime('%d.%m.%Y')}\n\n"
                f"💬 <b>Причина отказа:</b> {rejection_reason}\n\n"
                f"Если у вас есть вопросы, обратитесь к координатору."
            )
            
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Уведомление об отклонении отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об отклонении: {e}", exc_info=True)
    
    async def _send_pending_notification(
        self,
        request: EquipmentRequest,
        user: User,
        bot=None
    ):
        """Отправить уведомление о возврате заявки на рассмотрение"""
        try:
            message_text = (
                f"📋 <b>Ваша заявка находится на рассмотрении</b>\n\n"
                f"Заявка #{str(request.id)[:8]} снова находится на рассмотрении администратором.\n\n"
                f"Если произошла ошибка или возникли вопросы, пишите координатору."
            )
            
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Уведомление о возврате на рассмотрение отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о возврате на рассмотрение: {e}", exc_info=True)
    
    async def _send_restored_notification(
        self,
        request: EquipmentRequest,
        user: User,
        bot=None
    ):
        """Отправить уведомление о восстановлении заявки"""
        try:
            message_text = (
                f"📋 <b>Ваша заявка восстановлена</b>\n\n"
                f"Заявка #{str(request.id)[:8]} снова находится на рассмотрении администратором.\n\n"
                f"Если произошла ошибка или возникли вопросы, пишите координатору."
            )
            
            if bot and user.telegram_id:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=message_text,
                        parse_mode="HTML"
                    )
                    logger.info(f"✅ Уведомление о восстановлении отправлено пользователю {user.telegram_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.telegram_id}: {e}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления о восстановлении: {e}", exc_info=True)
