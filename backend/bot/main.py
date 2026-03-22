"""
Главный файл для запуска Telegram бота
"""
import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from bot.handlers import router

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_fsm_storage():
    """Получить FSM storage (Redis если доступен, иначе Memory)"""
    redis_url = os.getenv("REDIS_URL")
    
    if redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            storage = RedisStorage.from_url(redis_url)
            logger.info(f"✅ FSM Storage: Redis ({redis_url[:30]}...)")
            return storage
        except ImportError:
            logger.warning("⚠️ Redis библиотека не установлена, используем MemoryStorage")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось подключиться к Redis: {e}, используем MemoryStorage")
    
    logger.info("✅ FSM Storage: MemoryStorage (состояние теряется при перезапуске)")
    return MemoryStorage()


async def main():
    """Запуск бота"""
    # Проверяем наличие токена
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен! Проверьте переменные окружения.")
        return
    
    # Создаём бота и диспетчер
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
    
    # Устанавливаем команды бота для меню
    try:
        from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllGroupChats
        
        # Команды для личного чата (по умолчанию)
        private_commands = [
            BotCommand(command="start", description="Авторизация и главное меню"),
            BotCommand(command="register", description="Регистрация в системе"),
            BotCommand(command="tasks", description="Список моих задач"),
            BotCommand(command="stats", description="Моя статистика"),
            BotCommand(command="leaderboard", description="Рейтинг участников"),
            BotCommand(command="equipment", description="Заявки на оборудование"),
            BotCommand(command="notifications", description="Уведомления"),
            BotCommand(command="code", description="Код для входа на сайт"),
            BotCommand(command="help", description="Справка"),
        ]
        
        # Команды для групп
        group_commands = [
            BotCommand(command="help", description="Справка по чату"),
        ]
        
        await bot.set_my_commands(private_commands, scope=BotCommandScopeDefault())
        logger.info("✅ Команды для личного чата установлены")
        
        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
        logger.info("✅ Команды для групп установлены")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось установить команды бота: {e}")
    
    # Получаем FSM storage (Redis или Memory)
    storage = get_fsm_storage()
    dp = Dispatcher(storage=storage)
    
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
