"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Настройки приложения"""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./best_pr_system.db"
    )
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ADMIN_IDS: List[int] = [
        int(id.strip()) for id in os.getenv("TELEGRAM_ADMIN_IDS", "5079636941").split(",")
    ]
    
    # Google
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    
    # Google Credentials (для ротации клиентов, как в существующем боте)
    # Формат: JSON строка из credentials-1.json, credentials-2.json и т.д.
    GOOGLE_CREDENTIALS_1_JSON: str = os.getenv("GOOGLE_CREDENTIALS_1_JSON", "")
    GOOGLE_CREDENTIALS_2_JSON: str = os.getenv("GOOGLE_CREDENTIALS_2_JSON", "")
    GOOGLE_CREDENTIALS_3_JSON: str = os.getenv("GOOGLE_CREDENTIALS_3_JSON", "")
    GOOGLE_CREDENTIALS_4_JSON: str = os.getenv("GOOGLE_CREDENTIALS_4_JSON", "")
    GOOGLE_CREDENTIALS_5_JSON: str = os.getenv("GOOGLE_CREDENTIALS_5_JSON", "")
    
    # CORS
    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173"
        ).split(",")
    ]
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
