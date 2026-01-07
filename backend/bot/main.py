"""
Главный файл для запуска Telegram бота
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from app.config import settings
from bot.handlers import router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота"""
    # Проверяем наличие токена
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен! Проверьте переменные окружения.")
        return
    
    # Создаём бота и диспетчер
    # Используем простой способ создания бота без DefaultBotProperties
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Регистрируем роутер
    dp.include_router(router)
    
    # Запускаем бота
    logger.info("🤖 Telegram бот запускается...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
