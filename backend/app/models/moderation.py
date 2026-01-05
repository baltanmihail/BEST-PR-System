"""
Модель модерации
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ModerationStatus(str, enum.Enum):
    """Статусы модерации"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ModerationQueue(Base):
    """Очередь модерации"""
    __tablename__ = "moderation_queue"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    application_data = Column(JSONB, nullable=False)  # данные заявки
    status = Column(Enum(ModerationStatus), nullable=False, default=ModerationStatus.PENDING, index=True)
    decision_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<ModerationQueue {self.id} (status: {self.status})>"
