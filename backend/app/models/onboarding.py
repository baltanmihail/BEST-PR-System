"""
Модель для онбординга новых пользователей
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class OnboardingResponse(Base):
    """Ответы пользователя на вопросы онбординга"""
    __tablename__ = "onboarding_responses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(String(20), nullable=False, index=True)  # Telegram ID пользователя
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Если пользователь зарегистрирован
    
    # Ответы на вопросы
    experience = Column(Text, nullable=True)  # Опыт в PR/SMM/дизайне
    goals = Column(Text, nullable=True)  # Цели и что хочет получить
    motivation = Column(Text, nullable=True)  # Мотивация присоединиться
    additional_info = Column(JSONB, nullable=True)  # Дополнительная информация (свободная форма)
    
    # Метаданные
    from_website = Column(Boolean, default=False)  # Перешёл ли с сайта
    from_qr = Column(Boolean, default=False)  # Перешёл ли по QR-коду
    website_url = Column(String(500), nullable=True)  # URL сайта, с которого перешёл
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Связь с пользователем (если зарегистрирован)
    user = relationship("User", back_populates="onboarding_responses")


class OnboardingReminder(Base):
    """Напоминания о регистрации для незарегистрированных пользователей"""
    __tablename__ = "onboarding_reminders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(String(20), nullable=False, index=True)
    
    # Статистика
    first_visit_at = Column(DateTime(timezone=True), nullable=False)  # Первый визит
    last_reminder_at = Column(DateTime(timezone=True), nullable=True)  # Последнее напоминание
    reminder_count = Column(String(10), default="0")  # Количество напоминаний
    
    # Время на сайте (в секундах)
    time_on_site = Column(String(20), default="0")
    
    # Последний визит на сайт
    last_visit_at = Column(DateTime(timezone=True), nullable=True)
    
    # Статус
    responded = Column(Boolean, default=False)  # Ответил ли на вопросы
    registered = Column(Boolean, default=False)  # Зарегистрировался ли
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
