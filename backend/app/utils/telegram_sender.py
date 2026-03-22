"""
Утилита для отправки сообщений в Telegram из FastAPI
"""
import asyncio
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Глобальный экземпляр бота (ленивая инициализация)
_bot_instance = None
_bot_lock = asyncio.Lock()


async def get_bot():
    """Получить экземпляр Telegram бота (ленивая инициализация)"""
    global _bot_instance
    
    if _bot_instance is None:
        async with _bot_lock:
            if _bot_instance is None:
                try:
                    from aiogram import Bot
                    from aiogram.enums import ParseMode
                    
                    if not settings.TELEGRAM_BOT_TOKEN:
                        logger.warning("TELEGRAM_BOT_TOKEN не установлен, отправка сообщений в Telegram недоступна")
                        return None
                    
                    _bot_instance = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
                    logger.info("Telegram bot instance created for message sending")
                except Exception as e:
                    logger.error(f"Failed to create Telegram bot instance: {e}")
                    return None
    
    return _bot_instance


async def edit_telegram_message(
    chat_id: int,
    message_id: int,
    text: str,
    parse_mode: str = "HTML",
    reply_markup=None,
    silent_fail: bool = False
) -> bool:
    """Редактировать сообщение в Telegram"""
    try:
        bot = await get_bot()
        if not bot:
            if not silent_fail:
                logger.warning("Bot instance not available, cannot edit message")
            return False
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
        if not silent_fail:
            logger.debug(f"Message {message_id} edited for chat {chat_id}")
        return True
    except Exception as e:
        if not silent_fail:
            logger.error(f"Failed to edit Telegram message {message_id} in chat {chat_id}: {e}")
        return False


async def delete_telegram_message(chat_id: int, message_id: int, silent_fail: bool = False) -> bool:
    """Удалить сообщение в Telegram"""
    try:
        bot = await get_bot()
        if not bot:
            return False
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        if not silent_fail:
            logger.debug(f"Message {message_id} deleted in chat {chat_id}")
        return True
    except Exception as e:
        if not silent_fail:
            logger.debug(f"Could not delete message {message_id}: {e}")
        return False


async def send_telegram_message(
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    silent_fail: bool = False,
    return_message_id: bool = False
):
    """
    Отправить сообщение в Telegram
    
    Args:
        chat_id: ID чата (telegram_id пользователя)
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML или Markdown)
        silent_fail: Если True, не логирует ошибку (для тестовых сообщений)
        return_message_id: Если True, возвращает (success, message_id), иначе bool
    
    Returns:
        bool или (bool, int): success и опционально message_id
    """
    try:
        bot = await get_bot()
        if not bot:
            if not silent_fail:
                logger.warning("Bot instance not available, cannot send message")
            return (False, None) if return_message_id else False
        
        sent = await bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        if not silent_fail:
            logger.info(f"Message sent to Telegram user {chat_id}")
        if return_message_id and sent:
            return (True, sent.message_id)
        return (True, sent.message_id if sent else None) if return_message_id else True
    except Exception as e:
        if not silent_fail:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
        return (False, None) if return_message_id else False


async def create_chat_invite_link(chat_id: int, name: str = "PR System") -> Optional[str]:
    """Создать одноразовую ссылку-приглашение в группу"""
    try:
        bot = await get_bot()
        if not bot:
            return None
        link = await bot.create_chat_invite_link(
            chat_id=chat_id,
            name=name,
            member_limit=1,
        )
        return link.invite_link
    except Exception as e:
        logger.error(f"Failed to create invite link for chat {chat_id}: {e}")
        return None


async def invite_user_to_chat(user_telegram_id: int, chat_id: int) -> bool:
    """
    Пригласить пользователя в групповой чат.
    Создаёт invite link и отправляет его пользователю.
    """
    try:
        if not chat_id:
            return False

        invite_link = await create_chat_invite_link(chat_id)
        if not invite_link:
            logger.warning(f"Could not create invite link for chat {chat_id}")
            return False

        await send_telegram_message(
            chat_id=user_telegram_id,
            message=(
                "🎉 <b>Добро пожаловать в команду PR-отдела!</b>\n\n"
                "Твоя заявка одобрена! Присоединяйся к общему чату:\n\n"
                f"👉 <a href=\"{invite_link}\">Вступить в чат PR-отдела</a>"
            ),
        )
        logger.info(f"Invite link sent to user {user_telegram_id} for chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to invite user {user_telegram_id} to chat {chat_id}: {e}")
        return False


async def create_forum_topic(
    chat_id: int,
    name: str,
    icon_color: Optional[int] = None,
) -> Optional[int]:
    """Создать forum topic в группе и вернуть message_thread_id."""
    try:
        bot = await get_bot()
        if not bot:
            return None
        kwargs = {"chat_id": chat_id, "name": name[:128]}
        if icon_color:
            kwargs["icon_color"] = icon_color
        topic = await bot.create_forum_topic(**kwargs)
        logger.info(f"Forum topic created: {topic.message_thread_id} in chat {chat_id}")
        return topic.message_thread_id
    except Exception as e:
        logger.error(f"Failed to create forum topic in chat {chat_id}: {e}")
        return None


async def send_to_forum_topic(
    chat_id: int,
    message_thread_id: int,
    text: str,
    parse_mode: str = "HTML",
) -> bool:
    """Отправить сообщение в forum topic."""
    try:
        bot = await get_bot()
        if not bot:
            return False
        await bot.send_message(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            text=text,
            parse_mode=parse_mode,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send to forum topic {message_thread_id}: {e}")
        return False


async def close_bot():
    """Закрыть соединение с ботом (для cleanup)"""
    global _bot_instance
    
    if _bot_instance:
        try:
            await _bot_instance.session.close()
            _bot_instance = None
            logger.info("Telegram bot session closed")
        except Exception as e:
            logger.error(f"Error closing bot session: {e}")
