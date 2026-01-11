"""
Модель уведомлений
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class NotificationType(str, enum.Enum):
    """Типы уведомлений"""
    TASK_ASSIGNED = "task_assigned"
    TASK_COMPLETED = "task_completed"
    TASK_DEADLINE = "task_deadline"
    EQUIPMENT_REQUEST = "equipment_request"
    EQUIPMENT_APPROVED = "equipment_approved"
    EQUIPMENT_REJECTED = "equipment_rejected"
    MODERATION_REQUEST = "moderation_request"  # Новая заявка на регистрацию (для админа)
    MODERATION_APPROVED = "moderation_approved"
    MODERATION_REJECTED = "moderation_rejected"
    NEW_TASK = "new_task"
    TASK_REVIEW = "task_review"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"
    SUPPORT_REQUEST = "support_request"  # Запрос в поддержку (для админа)
    SYSTEM = "system"  # Системные уведомления


class NotificationTypeType(TypeDecorator):
    """TypeDecorator для правильной конвертации NotificationType в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            # Используем правильное имя типа из базы данных: notification_type (с подчеркиванием)
            return dialect.type_descriptor(PG_ENUM(
                NotificationType, 
                name='notification_type', 
                create_type=False, 
                values_callable=lambda x: [e.value for e in NotificationType]
            ))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, NotificationType):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return NotificationType(value)
            except ValueError:
                return NotificationType.SYSTEM
        return value


class Notification(Base):
    """Уведомление"""
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Используем существующий в БД ENUM notification_type (создан в миграции 001)
    type = Column(NotificationTypeType(), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(String, nullable=True)  # JSON строка с дополнительными данными (task_id, etc.)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Notification {self.type.value} for user {self.user_id}>"
