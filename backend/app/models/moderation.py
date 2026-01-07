"""
Модель модерации
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM
from sqlalchemy.orm import validates
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ModerationStatus(str, enum.Enum):
    """Статусы модерации"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ModerationStatusType(TypeDecorator):
    """TypeDecorator для правильной конвертации ModerationStatus в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_ENUM(ModerationStatus, name='moderation_status', create_type=False, values_callable=lambda x: [e.value for e in ModerationStatus]))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, ModerationStatus):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return ModerationStatus(value)
            except ValueError:
                return ModerationStatus.PENDING
        return value


class ModerationQueue(Base):
    """Очередь модерации"""
    __tablename__ = "moderation_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    application_data = Column(JSONB, nullable=False)  # данные заявки
    status = Column(ModerationStatusType(), nullable=False, default=ModerationStatus.PENDING, server_default='pending', index=True)
    
    @validates('status')
    def validate_status(self, key, value):
        """Валидация и конвертация статуса"""
        if value is None:
            return None
        if isinstance(value, ModerationStatus):
            return value.value
        return str(value) if value else None
    
    decision_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ModerationQueue {self.id} (status: {self.status})>"
