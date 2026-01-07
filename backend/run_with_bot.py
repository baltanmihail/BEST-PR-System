"""
Запуск API и Telegram бота одновременно
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
from bot.main import main as bot_main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_api():
    """Запуск FastAPI сервера"""
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    config = uvicorn.Config(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
    server = uvicorn.Server(config)
    
    logger.info(f"🚀 Starting API server on {host}:{port}")
    await server.serve()


async def run_bot():
    """Запуск Telegram бота"""
    # Запускаем бота только в production, чтобы избежать конфликтов
    environment = os.getenv("ENVIRONMENT", "development")
    if environment != "production":
        logger.info(f"⚠️ Бот не запускается в окружении '{environment}'. Запустите только в production.")
        return
    
    logger.info("🤖 Starting Telegram bot...")
    try:
        # Используем прямое создание бота и диспетчера
        from aiogram import Bot, Dispatcher
        from aiogram.enums import ParseMode
        from app.config import settings
        from bot.handlers import router
        
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN не установлен, бот не запустится")
            return
        
        # Используем простой способ создания бота без DefaultBotProperties
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
        dp = Dispatcher()
        dp.include_router(router)
        
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def main():
    """Запуск API и бота параллельно"""
    # Запускаем API и бота параллельно
    await asyncio.gather(
        run_api(),
        run_bot(),
        return_exceptions=True
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
