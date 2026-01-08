"""
Сервис для отправки напоминаний о регистрации
"""
import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.onboarding import OnboardingReminder, OnboardingResponse
from app.utils.telegram_sender import send_telegram_message
from app.config import settings

logger = logging.getLogger(__name__)


class OnboardingService:
    """Сервис для управления онбордингом и напоминаниями"""
    
    @staticmethod
    async def send_registration_reminder(
        db: AsyncSession,
        telegram_id: str,
        reminder_count: int,
        onboarding_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Отправить напоминание о регистрации пользователю
        
        Args:
            db: Сессия базы данных
            telegram_id: Telegram ID пользователя
            reminder_count: Номер напоминания (0, 1, 2, ...)
            onboarding_data: Данные онбординга для персонализации
        
        Returns:
            bool: Успешно ли отправлено сообщение
        """
        try:
            # Формируем персонализированное сообщение
            message = OnboardingService._build_reminder_message(
                reminder_count=reminder_count,
                onboarding_data=onboarding_data
            )
            
            # Отправляем сообщение
            sent = await send_telegram_message(
                chat_id=int(telegram_id),
                message=message,
                parse_mode="HTML"
            )
            
            if sent:
                # Отмечаем, что напоминание отправлено
                result = await db.execute(
                    select(OnboardingReminder).where(
                        OnboardingReminder.telegram_id == telegram_id
                    )
                )
                reminder = result.scalar_one_or_none()
                
                if reminder:
                    from datetime import datetime, timezone
                    current_count = int(reminder.reminder_count or "0")
                    reminder.reminder_count = str(current_count + 1)
                    reminder.last_reminder_at = datetime.now(timezone.utc)
                    await db.commit()
                
                logger.info(f"Sent reminder #{reminder_count + 1} to telegram_id={telegram_id}")
            
            return sent
            
        except Exception as e:
            logger.error(f"Error sending reminder to telegram_id={telegram_id}: {e}")
            return False
    
    @staticmethod
    def _build_reminder_message(
        reminder_count: int,
        onboarding_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Построить персонализированное сообщение-напоминание
        
        Args:
            reminder_count: Номер напоминания
            onboarding_data: Данные онбординга
        
        Returns:
            str: Текст сообщения
        """
        # Базовое сообщение
        base_message = "💡 <b>Напоминание о регистрации</b>\n\n"
        
        # Персонализация на основе ответов онбординга
        personalization = ""
        if onboarding_data:
            if onboarding_data.get("goals"):
                goals = onboarding_data["goals"][:100]  # Первые 100 символов
                personalization = f"Ты хотел: {goals}...\n\n"
            elif onboarding_data.get("motivation"):
                motivation = onboarding_data["motivation"][:100]
                personalization = f"Твоя мотивация: {motivation}...\n\n"
        
        # Разные сообщения в зависимости от номера напоминания
        if reminder_count == 0:
            # Первое напоминание (через 3 минуты)
            message = (
                f"{base_message}"
                f"Привет! 👋\n\n"
                f"{personalization}"
                f"Ты уже изучил наш сайт - это здорово! 🎉\n\n"
                f"💼 <b>Что даёт регистрация?</b>\n"
                f"• 📝 Возможность брать интересные задачи\n"
                f"• 🎬 Бронирование оборудования для съёмок\n"
                f"• 🏆 Участие в рейтинге и получение баллов\n"
                f"• 💡 Развитие вместе с командой профессионалов\n\n"
                f"🔐 <b>Регистрация займёт всего пару минут!</b>\n"
                f"Просто отсканируй QR-код на сайте или перейди по ссылке ниже."
            )
        elif reminder_count == 1:
            # Второе напоминание (через 1 день)
            message = (
                f"{base_message}"
                f"Мы заметили, что ты ещё не зарегистрировался.\n\n"
                f"{personalization}"
                f"💡 <b>Не упусти возможность!</b>\n"
                f"Регистрация открывает доступ к:\n"
                f"• Задачам по SMM, дизайну и видеопроизводству\n"
                f"• Оборудованию BEST Channel\n"
                f"• Рейтингу и достижениям\n\n"
                f"🌐 <b>Готов зарегистрироваться?</b>\n"
                f"Перейди на сайт и отсканируй QR-код!"
            )
        elif reminder_count == 2:
            # Третье напоминание (через 3 дня) - только если пользователь заходил на сайт несколько раз
            message = (
                f"{base_message}"
                f"Последний раз напоминаем! 🎯\n\n"
                f"{personalization}"
                f"Мы заметили, что ты заходил на сайт несколько раз - значит, тебе интересно!\n\n"
                f"💼 <b>Не упусти возможность:</b>\n"
                f"• Интересные проекты и задачи\n"
                f"• Опыт работы в команде\n"
                f"• Развитие навыков\n"
                f"• Новые знакомства\n\n"
                f"🔐 <b>Регистрация:</b> {settings.FRONTEND_URL}/login\n\n"
                f"Если не зарегистрируешься сейчас, мы больше не будем беспокоить."
            )
        
        # Добавляем кнопку для перехода на сайт
        message += f"\n\n🌐 <a href=\"{settings.FRONTEND_URL}/login?from=bot&telegram_id={telegram_id}\">Перейти на сайт</a>"
        
        return message
    
    @staticmethod
    async def process_pending_reminders(db: AsyncSession) -> int:
        """
        Обработать все ожидающие напоминания
        
        Returns:
            int: Количество отправленных напоминаний
        """
        from datetime import datetime, timezone, timedelta
        
        now = datetime.now(timezone.utc)
        
        # Получаем всех незарегистрированных пользователей
        result = await db.execute(
            select(OnboardingReminder).where(
                OnboardingReminder.registered == False
            )
        )
        reminders = result.scalars().all()
        
        sent_count = 0
        
        for reminder in reminders:
            if not reminder.first_visit_at:
                continue
            
            time_since_first_visit = now - reminder.first_visit_at
            reminder_count = int(reminder.reminder_count or "0")
            time_on_site = int(reminder.time_on_site or "0")
            
            # Определяем интервалы для напоминаний (максимум 2-3)
            intervals = [
                timedelta(minutes=3),  # Первое напоминание через 3 минуты
                timedelta(days=1),     # Второе через 1 день
                timedelta(days=3),     # Третье через 3 дня (только если пользователь заходил на сайт несколько раз)
            ]
            
            # Проверяем, нужно ли отправить напоминание
            should_send = False
            
            # Максимум 2-3 напоминания
            max_reminders = 2
            # Третье напоминание только если пользователь заходил на сайт несколько раз (есть last_visit_at)
            if reminder.last_visit_at and reminder.last_visit_at != reminder.first_visit_at:
                max_reminders = 3  # Пользователь заходил не один раз
            
            if reminder_count < max_reminders and reminder_count < len(intervals):
                # Проверяем, прошло ли достаточно времени с последнего напоминания или первого визита
                if reminder_count == 0:
                    # Первое напоминание - через 3 минуты после первого визита, если провёл достаточно времени на сайте
                    if time_since_first_visit >= intervals[0] and time_on_site >= 120:
                        should_send = True
                else:
                    # Последующие напоминания - через определённые интервалы
                    if reminder.last_reminder_at:
                        time_since_last_reminder = now - reminder.last_reminder_at
                        if time_since_last_reminder >= intervals[reminder_count]:
                            should_send = True
            
            if should_send:
                # Получаем ответы онбординга для персонализации
                response_result = await db.execute(
                    select(OnboardingResponse).where(
                        OnboardingResponse.telegram_id == reminder.telegram_id
                    )
                )
                onboarding_response = response_result.scalar_one_or_none()
                
                onboarding_data = None
                if onboarding_response:
                    onboarding_data = {
                        "experience": onboarding_response.experience,
                        "goals": onboarding_response.goals,
                        "motivation": onboarding_response.motivation,
                    }
                
                sent = await OnboardingService.send_registration_reminder(
                    db=db,
                    telegram_id=reminder.telegram_id,
                    reminder_count=reminder_count,
                    onboarding_data=onboarding_data
                )
                
                if sent:
                    sent_count += 1
        
        logger.info(f"Processed {sent_count} pending reminders")
        return sent_count
