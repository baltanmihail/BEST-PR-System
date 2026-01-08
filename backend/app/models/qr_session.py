"""
Модель для QR-код сессий авторизации
"""
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
import uuid

from app.database import Base


class QRSession(Base):
    """Сессия QR-кода для авторизации"""
    __tablename__ = "qr_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_token = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, confirmed, expired, cancelled
    telegram_id = Column(BigInteger, nullable=True)  # Заполняется после подтверждения
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    
    # IP и User-Agent для безопасности
    ip_address = Column(String(45), nullable=True)  # IPv6 может быть до 45 символов
    user_agent = Column(Text, nullable=True)
    
    # Связь с пользователем
    user = relationship("User", back_populates="qr_sessions")
    
    def is_expired(self) -> bool:
        """Проверка, истекла ли сессия"""
        return datetime.now(timezone.utc) > self.expires_at
    
    def is_valid(self) -> bool:
        """Проверка, валидна ли сессия"""
        return self.status == "pending" and not self.is_expired()
