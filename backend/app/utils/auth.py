"""
Утилиты для аутентификации
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from hashlib import sha256
import hmac
import time
import os

from app.config import settings


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Создать JWT токен
    
    Args:
        data: Данные для кодирования в токен
        expires_delta: Время жизни токена
    
    Returns:
        JWT токен
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Проверить JWT токен
    
    Args:
        token: JWT токен
    
    Returns:
        Payload токена или None если невалиден
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_telegram_auth(auth_data: dict) -> bool:
    """
    Проверить данные авторизации от Telegram Web App
    
    Args:
        auth_data: Данные от Telegram (id, first_name, hash, auth_date, etc.)
    
    Returns:
        True если данные валидны
    """
    # ВРЕМЕННО: для тестирования в development можно отключить проверку
    if os.getenv("ENVIRONMENT", "production") == "development":
        # Проверяем только наличие обязательных полей
        required_fields = ["id", "first_name", "auth_date", "hash"]
        return all(field in auth_data for field in required_fields)
    
    # Реальная проверка для production
    if "hash" not in auth_data:
        return False
    
    received_hash = auth_data.pop("hash")
    auth_date = auth_data.get("auth_date", 0)
    
    # Проверка времени (не старше 24 часов)
    current_time = int(time.time())
    if abs(current_time - auth_date) > 86400:  # 24 часа
        return False
    
    # Создаём строку для проверки
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(auth_data.items())
    )
    
    # Получаем секретный ключ от Telegram Bot API
    secret_key = sha256(settings.TELEGRAM_BOT_TOKEN.encode()).digest()
    
    # Вычисляем hash
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        sha256
    ).hexdigest()
    
    # Сравниваем
    return calculated_hash == received_hash
