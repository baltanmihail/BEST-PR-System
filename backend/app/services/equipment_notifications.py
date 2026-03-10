"""
Сервис уведомлений об изменении статусов заявок на оборудование
Одно обновляемое сообщение-дайджест для VP4PR и Channel (не PR-FR).
Приоритеты: 1) Новые заявки, 2) Напоминания.
"""
import logging
from typing import List, Dict, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus, Equipment
from app.models.user import User, UserRole
from app.models.equipment_admin_notification import EquipmentAdminNotification
from app.services.equipment_digest_service import EquipmentDigestService

logger = logging.getLogger(__name__)

# Текст уведомления о новой заявке (из BEST Channel Bot messages.py)
NEW_APPLICATION_NOTIFICATION = """🔔 <b>Новая заявка на оборудование</b>

📋 <b>Номер заявки:</b> #{application_number}
👤 <b>Пользователь:</b> {fio}
🎬 <b>Съёмка:</b> {shooting_name}
📅 <b>Дата съёмки:</b> {shooting_date}
📥 <b>Получение:</b> {rental_start}
📤 <b>Возврат:</b> {rental_end}
📦 <b>Оборудование:</b> #{equipment_number} {equipment_name}
💬 <b>Комментарий:</b> {comment}

Используйте сайт или бот для просмотра и обработки заявки."""


class EquipmentNotifications:
    """Сервис для отправки уведомлений об изменении статусов заявок"""
    
    async def send_new_application_notification(
        self,
        db: AsyncSession,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User,
        application_number: int,
        shooting_name: str = ""
    ) -> dict:
        """
        Обновить дайджест для VP4PR и Channel (одно сообщение, приоритеты).
        Не создаём отдельные сообщения — только дайджест.
        """
        try:
            bot = await self._get_bot()
            if not bot:
                return {"status": "skipped", "reason": "bot_not_available"}

            # Обновляем одно сообщение-дайджест для координаторов (VP4PR, Channel, TELEGRAM_ADMIN_IDS)
            sent = await EquipmentDigestService.update_digest_for_coordinators(db, bot)

            logger.info(f"✅ Дайджест обновлён для {sent} получателей (заявка #{application_number})")
            return {"status": "success", "notified_count": sent}
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления о новой заявке: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    @staticmethod
    async def delete_admin_notifications_for_request(db: AsyncSession, request_id: UUID) -> int:
        """
        Удалить уведомления координаторам о заявке при approve/reject (как в BEST Channel Bot).
        Возвращает количество удалённых сообщений в TG.
        """
        try:
            from app.utils.telegram_sender import get_bot, delete_telegram_message
            
            result = await db.execute(
                select(EquipmentAdminNotification).where(EquipmentAdminNotification.request_id == request_id)
            )
            recs = result.scalars().all()
            if not recs:
                return 0
            
            bot = await get_bot()
            deleted = 0
            for rec in recs:
                try:
                    ok = await delete_telegram_message(rec.telegram_id, rec.message_id, silent_fail=True)
                    if ok:
                        deleted += 1
                except Exception:
                    pass
                db.delete(rec)
            await db.commit()
            logger.info(f"✅ Удалено {deleted} уведомлений координаторам для заявки {request_id}")
            return deleted
        except Exception as e:
            logger.warning(f"Ошибка удаления уведомлений для заявки {request_id}: {e}")
            return 0
    
    async def _get_bot(self):
        """Получить экземпляр бота для отправки сообщений"""
        from app.utils.telegram_sender import get_bot
        return await get_bot()
    
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
