"""
Сервис для управления кодами регистрации
"""
import secrets
import time
from typing import Optional, Dict
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

# In-memory хранилище кодов (в production можно заменить на Redis)
_registration_codes: Dict[str, Dict] = {}


class RegistrationCodeService:
    """Сервис для управления кодами регистрации"""
    
    CODE_LENGTH = 6
    CODE_EXPIRY_MINUTES = 10
    
    @staticmethod
    def generate_code() -> str:
        """Генерирует случайный 6-значный код"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(RegistrationCodeService.CODE_LENGTH)])
    
    @staticmethod
    def create_code(telegram_id: int, telegram_username: Optional[str] = None) -> str:
        """
        Создаёт код регистрации для пользователя
        
        Args:
            telegram_id: Telegram ID пользователя
            telegram_username: Telegram username (опционально)
        
        Returns:
            Сгенерированный код
        """
        code = RegistrationCodeService.generate_code()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=RegistrationCodeService.CODE_EXPIRY_MINUTES)
        
        _registration_codes[code] = {
            "telegram_id": telegram_id,
            "telegram_username": telegram_username,
            "created_at": datetime.now(timezone.utc),
            "expires_at": expires_at,
            "used": False
        }
        
        logger.info(f"Registration code created for telegram_id={telegram_id}, code={code}, expires_at={expires_at}")
        
        # Очистка старых кодов (можно сделать периодической задачей)
        RegistrationCodeService._cleanup_expired_codes()
        
        return code
    
    @staticmethod
    def verify_code(code: str) -> Optional[Dict]:
        """
        Проверяет код регистрации
        
        Args:
            code: Код для проверки
        
        Returns:
            Словарь с данными пользователя или None если код невалиден
        """
        code_data = _registration_codes.get(code)
        
        if not code_data:
            logger.warning(f"Registration code not found: {code}")
            return None
        
        if code_data["used"]:
            logger.warning(f"Registration code already used: {code}")
            return None
        
        if datetime.now(timezone.utc) > code_data["expires_at"]:
            logger.warning(f"Registration code expired: {code}")
            del _registration_codes[code]
            return None
        
        # Помечаем код как использованный
        code_data["used"] = True
        
        return {
            "telegram_id": code_data["telegram_id"],
            "telegram_username": code_data["telegram_username"]
        }
    
    @staticmethod
    def _cleanup_expired_codes():
        """Удаляет истёкшие коды"""
        now = datetime.now(timezone.utc)
        expired_codes = [
            code for code, data in _registration_codes.items()
            if now > data["expires_at"]
        ]
        
        for code in expired_codes:
            del _registration_codes[code]
        
        if expired_codes:
            logger.info(f"Cleaned up {len(expired_codes)} expired registration codes")
    
    @staticmethod
    def get_code_info(code: str) -> Optional[Dict]:
        """Получить информацию о коде без его использования"""
        return _registration_codes.get(code)
