"""
Модель уведомлений
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
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
    MODERATION_APPROVED = "moderation_approved"
    MODERATION_REJECTED = "moderation_rejected"
    NEW_TASK = "new_task"
    TASK_REVIEW = "task_review"
    ACHIEVEMENT_UNLOCKED = "achievement_unlocked"


class Notification(Base):
    """Уведомление"""
    __tablename__ = "notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    data = Column(String, nullable=True)  # JSON строка с дополнительными данными (task_id, etc.)
    is_read = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<Notification {self.type.value} for user {self.user_id}>"
