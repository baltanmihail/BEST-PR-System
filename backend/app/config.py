"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Union
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
    TELEGRAM_ADMIN_IDS: Union[str, int, List[int]] = os.getenv("TELEGRAM_ADMIN_IDS", "")
    TELEGRAM_GENERAL_CHAT_ID: str = os.getenv("TELEGRAM_GENERAL_CHAT_ID", "")  # ID общего чата для всех пользователей
    
    @field_validator('TELEGRAM_ADMIN_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        """Парсинг TELEGRAM_ADMIN_IDS из строки, числа или списка"""
        if isinstance(v, list):
            return v
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            if not v or not v.strip():
                return []  # Пустой список, если не задано
            # Если строка с запятыми - разбиваем
            if "," in v:
                ids = [int(id.strip()) for id in v.split(",") if id.strip()]
                return ids if ids else []
            else:
                # Один ID
                try:
                    return [int(v.strip())]
                except ValueError:
                    return []  # Пустой список при ошибке парсинга
        return []  # Пустой список по умолчанию
    
    # Google
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_DRIVE_FOLDER_ID: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
    GOOGLE_TIMELINE_SHEETS_ID: str = os.getenv("GOOGLE_TIMELINE_SHEETS_ID", "")  # ID таблицы с таймлайнами
    GOOGLE_EQUIPMENT_SHEETS_ID: str = os.getenv("GOOGLE_EQUIPMENT_SHEETS_ID", "")  # ID таблицы с оборудованием (будет найден в папке Equipment)
    GOOGLE_EQUIPMENT_TIMELINE_SHEETS_ID: str = os.getenv("GOOGLE_EQUIPMENT_TIMELINE_SHEETS_ID", "")  # ID таблицы с таймлайном занятости оборудования
    
    # Google Credentials (для ротации клиентов, как в существующем боте)
    # Формат: JSON строка из credentials-1.json, credentials-2.json и т.д.
    GOOGLE_CREDENTIALS_1_JSON: str = os.getenv("GOOGLE_CREDENTIALS_1_JSON", "")
    GOOGLE_CREDENTIALS_2_JSON: str = os.getenv("GOOGLE_CREDENTIALS_2_JSON", "")
    GOOGLE_CREDENTIALS_3_JSON: str = os.getenv("GOOGLE_CREDENTIALS_3_JSON", "")
    GOOGLE_CREDENTIALS_4_JSON: str = os.getenv("GOOGLE_CREDENTIALS_4_JSON", "")
    GOOGLE_CREDENTIALS_5_JSON: str = os.getenv("GOOGLE_CREDENTIALS_5_JSON", "")
    
    # Email пользователя для передачи ownership файлов (чтобы файлы использовали квоту пользователя, а не сервисного аккаунта)
    GOOGLE_DRIVE_OWNER_EMAIL: str = os.getenv("GOOGLE_DRIVE_OWNER_EMAIL", "")
    
    # Frontend URL (для ссылок в боте и уведомлениях)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://best-pr-system.up.railway.app")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def CORS_ORIGINS(self) -> List[str]:
        """
        CORS_ORIGINS - парсится вручную из переменной окружения
        НЕ объявляем как поле Pydantic, чтобы избежать автоматического JSON парсинга
        """
        cors_str = os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5173,https://best-pr-system.up.railway.app"
        )
        if not cors_str or not cors_str.strip():
            return [
                "http://localhost:3000",
                "http://localhost:5173",
                "https://best-pr-system.up.railway.app"
            ]
        origins = [origin.strip() for origin in cors_str.split(",") if origin.strip()]
        return origins if origins else [
            "http://localhost:3000",
            "http://localhost:5173",
            "https://best-pr-system.up.railway.app"
        ]


settings = Settings()
