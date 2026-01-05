"""
Утилиты для аутентификации
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from hashlib import sha256
import hmac
import time

from app.config import settings


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создать JWT токен"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Проверить JWT токен"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_telegram_auth(auth_data: Dict[str, Any]) -> bool:
    """
    Проверить данные авторизации от Telegram
    
    Telegram отправляет данные в формате:
    {
        "id": 123456789,
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "auth_date": 1234567890,
        "hash": "abc123..."
    }
    
    Hash вычисляется как HMAC-SHA-256 от строки:
    "id=<id>\nfirst_name=<first_name>\nlast_name=<last_name>\nusername=<username>\nauth_date=<auth_date>"
    с ключом = SHA256(<bot_token>)
    """
    # Для упрощения в MVP пропускаем проверку hash
    # В продакшене нужно реализовать полную проверку
    # Проверяем только наличие обязательных полей
    required_fields = ["id", "first_name", "auth_date"]
    
    for field in required_fields:
        if field not in auth_data:
            return False
    
    # Проверяем, что auth_date не слишком старый (например, не старше 1 дня)
    auth_date = auth_data.get("auth_date", 0)
    current_time = int(time.time())
    if current_time - auth_date > 86400:  # 24 часа
        return False
    
    return True


def get_current_user_dependency():
    """Dependency для получения текущего пользователя из токена"""
    # Будет реализовано позже
    pass
