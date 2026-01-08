"""
Модель пользователя
"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, Enum, TypeDecorator
from sqlalchemy.orm import validates, relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """Роли пользователей"""
    NOVICE = "novice"
    PARTICIPANT = "participant"
    ACTIVE_PARTICIPANT = "active_participant"
    COORDINATOR_SMM = "coordinator_smm"
    COORDINATOR_DESIGN = "coordinator_design"
    COORDINATOR_CHANNEL = "coordinator_channel"
    COORDINATOR_PRFR = "coordinator_prfr"
    VP4PR = "vp4pr"


class UserRoleType(TypeDecorator):
    """TypeDecorator для правильной конвертации UserRole в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            # Возвращаем PG_ENUM, но TypeDecorator всё равно будет вызывать process_bind_param
            return dialect.type_descriptor(PG_ENUM(UserRole, name='userrole', create_type=False, values_callable=lambda x: [e.value for e in UserRole]))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку) - ВАЖНО: вызывается ДО передачи в БД"""
        if value is None:
            return None
        if isinstance(value, UserRole):
            # Возвращаем значение enum'а ("novice"), а не имя ("NOVICE")
            return value.value
        # Если уже строка, возвращаем как есть
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return UserRole(value)
            except ValueError:
                # Если значение не найдено в enum, возвращаем NOVICE по умолчанию
                return UserRole.NOVICE
        return value


class User(Base):
    """Пользователь"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    role = Column(UserRoleType(), nullable=False, default=UserRole.NOVICE, server_default='novice')
    level = Column(Integer, nullable=False, default=1)
    points = Column(Integer, nullable=False, default=0, index=True)
    streak_days = Column(Integer, nullable=False, default=0)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    # Мягкое удаление (soft delete)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    # Согласие на обработку персональных данных
    personal_data_consent = Column(Boolean, nullable=False, default=False)
    consent_date = Column(DateTime(timezone=True), nullable=True)
    # Пользовательское соглашение
    user_agreement_accepted = Column(Boolean, nullable=False, default=False)
    agreement_version = Column(String, nullable=True)  # Версия соглашения
    agreement_accepted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Связь с QR-сессиями
    qr_sessions = relationship("QRSession", back_populates="user")
    
    @validates('role')
    def validate_role(self, key, value):
        """Валидация и конвертация роли - гарантируем, что передаётся строка"""
        if value is None:
            return None
        if isinstance(value, UserRole):
            # Конвертируем enum в его значение (строку)
            return value.value
        # Если уже строка, возвращаем как есть
        return str(value) if value else None
    
    def __repr__(self):
        return f"<User {self.telegram_id} ({self.full_name})>"
