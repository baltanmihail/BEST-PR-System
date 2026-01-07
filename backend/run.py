"""
Скрипт для запуска приложения
"""
import uvicorn
import os
import logging
from pathlib import Path

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Получаем порт из переменной окружения (для Railway) или используем 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    logger.info(f"🚀 Starting server on {host}:{port}")
    logger.info(f"📝 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"🔗 Docs will be available at: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
