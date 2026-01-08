"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List, Union, Any
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
    
    # Google Credentials (для ротации клиентов, как в существующем боте)
    # Формат: JSON строка из credentials-1.json, credentials-2.json и т.д.
    GOOGLE_CREDENTIALS_1_JSON: str = os.getenv("GOOGLE_CREDENTIALS_1_JSON", "")
    GOOGLE_CREDENTIALS_2_JSON: str = os.getenv("GOOGLE_CREDENTIALS_2_JSON", "")
    GOOGLE_CREDENTIALS_3_JSON: str = os.getenv("GOOGLE_CREDENTIALS_3_JSON", "")
    GOOGLE_CREDENTIALS_4_JSON: str = os.getenv("GOOGLE_CREDENTIALS_4_JSON", "")
    GOOGLE_CREDENTIALS_5_JSON: str = os.getenv("GOOGLE_CREDENTIALS_5_JSON", "")
    
    # CORS - используем model_validator для перехвата до парсинга
    CORS_ORIGINS: List[str] = []
    
    @model_validator(mode='before')
    @classmethod
    def parse_cors_origins_before(cls, data: Any) -> Any:
        """Парсинг CORS_ORIGINS из строки с запятыми до парсинга Pydantic"""
        if isinstance(data, dict):
            # Если CORS_ORIGINS есть в данных как строка, парсим её
            if 'CORS_ORIGINS' in data and isinstance(data['CORS_ORIGINS'], str):
                cors_str = data['CORS_ORIGINS'].strip()
                if cors_str:
                    data['CORS_ORIGINS'] = [origin.strip() for origin in cors_str.split(",") if origin.strip()]
                else:
                    data['CORS_ORIGINS'] = [
                        "http://localhost:3000",
                        "http://localhost:5173",
                        "https://best-pr-system.up.railway.app"
                    ]
            # Если CORS_ORIGINS нет, используем дефолтное значение
            elif 'CORS_ORIGINS' not in data:
                data['CORS_ORIGINS'] = [
                    "http://localhost:3000",
                    "http://localhost:5173",
                    "https://best-pr-system.up.railway.app"
                ]
        return data
    
    # Frontend URL (для ссылок в боте и уведомлениях)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://best-pr-system.up.railway.app")
    
    # Environment
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
