"""
Сервис для работы с Telegram чатами и группами
"""
import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from uuid import UUID

from app.models.telegram import TelegramChat
from app.models.user import User
from app.config import settings
from app.utils.telegram_sender import get_bot

logger = logging.getLogger(__name__)


class TelegramChatService:
    """Сервис для управления Telegram чатами"""
    
    @staticmethod
    async def get_or_create_general_chat(db: AsyncSession) -> Optional[TelegramChat]:
        """
        Получить или создать общий чат для всех зарегистрированных пользователей
        
        Returns:
            TelegramChat или None, если не удалось создать
        """
        # Проверяем, существует ли уже общий чат
        result = await db.execute(
            select(TelegramChat).where(
                and_(
                    TelegramChat.is_general == True,
                    TelegramChat.is_active == True
                )
            )
        )
        general_chat = result.scalar_one_or_none()
        
        if general_chat:
            return general_chat
        
        # Если общего чата нет, создаём его
        # Примечание: Telegram Bot API не позволяет создавать группы программно
        # Нужно создать группу вручную и добавить бота как администратора
        # Затем установить TELEGRAM_GENERAL_CHAT_ID в переменных окружения
        
        if settings.TELEGRAM_GENERAL_CHAT_ID:
            try:
                # Создаём запись в БД
                general_chat = TelegramChat(
                    chat_id=int(settings.TELEGRAM_GENERAL_CHAT_ID),
                    chat_type="supergroup",  # Обычно общие чаты - это супергруппы
                    chat_name="BEST PR System - Общий чат",
                    is_general=True,
                    is_active=True
                )
                
                db.add(general_chat)
                await db.commit()
                await db.refresh(general_chat)
                
                logger.info(f"General chat created in DB: {general_chat.chat_id}")
                return general_chat
            except Exception as e:
                await db.rollback()
                logger.error(f"Failed to create general chat in DB: {e}")
                return None
        else:
            logger.warning("TELEGRAM_GENERAL_CHAT_ID not set, cannot create general chat")
            return None
    
    @staticmethod
    async def get_general_chat(db: AsyncSession) -> Optional[TelegramChat]:
        """Получить общий чат"""
        result = await db.execute(
            select(TelegramChat).where(
                and_(
                    TelegramChat.is_general == True,
                    TelegramChat.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_task_chat(db: AsyncSession, task_id: UUID) -> Optional[TelegramChat]:
        """Получить чат для задачи (теперь это тема в общем чате)"""
        result = await db.execute(
            select(TelegramChat).where(
                and_(
                    TelegramChat.task_id == task_id,
                    TelegramChat.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_task_topic(db: AsyncSession, task_id: UUID) -> Optional[TelegramChat]:
        """Получить тему для задачи"""
        result = await db.execute(
            select(TelegramChat).where(
                and_(
                    TelegramChat.task_id == task_id,
                    TelegramChat.topic_id.isnot(None),  # Тема должна иметь topic_id
                    TelegramChat.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_task_topic(
        db: AsyncSession,
        task_id: UUID,
        task_title: str
    ) -> Optional[TelegramChat]:
        """
        Создать тему (topic) для задачи в общем чате
        
        Args:
            db: Сессия БД
            task_id: ID задачи
            task_title: Название задачи (для названия темы)
        
        Returns:
            TelegramChat с topic_id или None
        """
        # Проверяем, не существует ли уже тема для этой задачи
        existing_topic = await TelegramChatService.get_task_topic(db, task_id)
        if existing_topic:
            return existing_topic
        
        # Получаем общий чат
        general_chat = await TelegramChatService.get_or_create_general_chat(db)
        if not general_chat:
            logger.error("General chat not found, cannot create task topic")
            return None
        
        try:
            bot = await get_bot()
            if not bot:
                logger.error("Bot instance not available")
                return None
            
            # Создаём тему в общем чате
            topic_name = f"🔒 Задача: {task_title[:100]}"  # Ограничение 128 символов
            
            # Используем метод create_forum_topic из aiogram 3.2.0
            forum_topic = await bot.create_forum_topic(
                chat_id=general_chat.chat_id,
                name=topic_name,
                icon_color=0x6FB9F0  # Синий цвет иконки
            )
            
            if forum_topic and hasattr(forum_topic, 'message_thread_id'):
                topic_id = forum_topic.message_thread_id
                
                # Создаём запись в БД
                task_topic = TelegramChat(
                    chat_id=general_chat.chat_id,  # Тот же chat_id, что и общий чат
                    task_id=task_id,
                    topic_id=topic_id,
                    topic_name=topic_name,
                    is_open_topic=False,  # Закрытая тема (только для координаторов и исполнителей)
                    chat_type="supergroup",
                    is_active=True
                )
                
                db.add(task_topic)
                await db.commit()
                await db.refresh(task_topic)
                
                logger.info(f"Task topic created: {topic_id} for task {task_id}")
                return task_topic
            else:
                logger.error(f"Failed to create topic: forum_topic is None or missing message_thread_id")
                return None
                
        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating task topic: {e}")
            return None
    
    @staticmethod
    async def create_task_chat(
        db: AsyncSession,
        task_id: UUID,
        task_title: str,
        coordinator_ids: List[int],
        participant_ids: List[int]
    ) -> Optional[TelegramChat]:
        """
        Создать чат для задачи (DEPRECATED - используй create_task_topic)
        
        Теперь создаём тему в общем чате вместо отдельного чата.
        """
        # Используем новый метод создания темы
        return await TelegramChatService.create_task_topic(db, task_id, task_title)
    
    @staticmethod
    async def add_user_to_chat(
        chat_id: int,
        user_telegram_id: int,
        user_full_name: str
    ) -> bool:
        """
        Добавить пользователя в чат
        
        Args:
            chat_id: ID чата в Telegram
            user_telegram_id: Telegram ID пользователя
            user_full_name: Полное имя пользователя
        
        Returns:
            True если успешно, False в противном случае
        """
        try:
            bot = await get_bot()
            if not bot:
                logger.error("Bot instance not available")
                return False
            
            # Пытаемся добавить пользователя в группу
            # В aiogram 3.2.0 нет метода add_chat_member, используем прямой вызов Bot API
            try:
                import aiohttp
                from app.config import settings
                
                # Прямой вызов Telegram Bot API
                async with aiohttp.ClientSession() as session:
                    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/addChatMember"
                    async with session.post(url, json={
                        "chat_id": chat_id,
                        "user_id": user_telegram_id
                    }) as response:
                        result = await response.json()
                        if result.get("ok"):
                            logger.info(f"User {user_telegram_id} ({user_full_name}) added to chat {chat_id}")
                            return True
                        else:
                            # Если пользователь уже в группе или другая ошибка
                            error_description = result.get("description", "Unknown error")
                            if "already a member" in error_description.lower() or "user is already a participant" in error_description.lower():
                                logger.info(f"User {user_telegram_id} is already in chat {chat_id}")
                                return True
                            else:
                                logger.warning(f"Could not add user {user_telegram_id} to chat {chat_id}: {error_description}")
                                return False
            except Exception as e:
                # Если не удалось добавить (нет прав или пользователь уже в группе)
                logger.warning(f"Could not add user {user_telegram_id} to chat {chat_id}: {e}")
                # Возвращаем False, чтобы система могла отправить ссылку-приглашение
                return False
                
        except Exception as e:
            logger.error(f"Error adding user to chat: {e}")
            return False
    
    @staticmethod
    async def send_welcome_message_to_chat(
        chat_id: int,
        user_full_name: str,
        is_new_user: bool = True,
        topic_id: Optional[int] = None
    ) -> bool:
        """
        Отправить приветственное сообщение в чат или тему
        
        Args:
            chat_id: ID чата
            user_full_name: Полное имя пользователя
            is_new_user: Новый ли это пользователь
            topic_id: ID темы (если отправляем в тему)
        
        Returns:
            True если успешно
        """
        try:
            bot = await get_bot()
            if not bot:
                return False
            
            if is_new_user:
                message = (
                    f"👋 <b>Добро пожаловать, {user_full_name}!</b>\n\n"
                    f"Ты теперь часть команды PR-отдела BEST Москва! 🚀\n\n"
                    f"💡 <b>Что дальше?</b>\n"
                    f"• Изучи доступные задачи\n"
                    f"• Бери интересные задания\n"
                    f"• Развивайся вместе с командой\n\n"
                    f"Если есть вопросы - пиши здесь или координаторам!"
                )
            else:
                message = f"👋 Привет, {user_full_name}! Рады видеть тебя снова!"
            
            # Если указан topic_id, отправляем в тему
            if topic_id:
                await bot.send_message(
                    chat_id=chat_id,
                    message_thread_id=topic_id,
                    text=message,
                    parse_mode="HTML"
                )
                logger.info(f"Welcome message sent to topic {topic_id} in chat {chat_id} for {user_full_name}")
            else:
                await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
                logger.info(f"Welcome message sent to chat {chat_id} for {user_full_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            return False
    
    @staticmethod
    async def get_chat_invite_link(db: AsyncSession, chat_id: int) -> Optional[str]:
        """
        Получить или создать ссылку-приглашение для чата
        
        Args:
            db: Сессия БД
            chat_id: ID чата
        
        Returns:
            Ссылка-приглашение или None
        """
        try:
            # Получаем чат из БД
            result = await db.execute(
                select(TelegramChat).where(TelegramChat.chat_id == chat_id)
            )
            chat = result.scalar_one_or_none()
            
            if chat and chat.invite_link:
                return chat.invite_link
            
            # Если ссылки нет, пытаемся создать через Bot API
            bot = await get_bot()
            if not bot:
                return None
            
            try:
                # Создаём ссылку-приглашение
                # В aiogram 3.2.0 метод называется create_invite_link
                invite_link_obj = await bot.create_invite_link(
                    chat_id=chat_id,
                    name="BEST PR System Invite",
                    creates_join_request=False  # Прямое присоединение
                )
                
                invite_link = invite_link_obj.invite_link
                
                # Сохраняем ссылку в БД
                if chat:
                    chat.invite_link = invite_link
                    await db.commit()
                
                return invite_link
            except Exception as e:
                logger.error(f"Error creating invite link: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting invite link: {e}")
            return None
