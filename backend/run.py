"""
Скрипт для запуска приложения
"""
import uvicorn
import os
from pathlib import Path

if __name__ == "__main__":
    # Получаем порт из переменной окружения (для Railway) или используем 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=os.getenv("ENVIRONMENT", "development") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
