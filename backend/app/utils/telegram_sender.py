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


async def send_telegram_message(chat_id: int, message: str, parse_mode: str = "HTML", silent_fail: bool = False) -> bool:
    """
    Отправить сообщение в Telegram
    
    Args:
        chat_id: ID чата (telegram_id пользователя)
        message: Текст сообщения
        parse_mode: Режим парсинга (HTML или Markdown)
        silent_fail: Если True, не логирует ошибку (для тестовых сообщений)
    
    Returns:
        True если сообщение отправлено успешно, False в противном случае
    """
    try:
        bot = await get_bot()
        if not bot:
            if not silent_fail:
                logger.warning("Bot instance not available, cannot send message")
            return False
        
        await bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
        if not silent_fail:
            logger.info(f"Message sent to Telegram user {chat_id}")
        return True
    except Exception as e:
        if not silent_fail:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
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
