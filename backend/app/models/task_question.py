"""
Модель вопросов пользователей к задачам
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from app.database import Base


class TaskQuestion(Base):
    """Вопрос пользователя к задаче"""
    __tablename__ = "task_questions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Связи
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    asked_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    answered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Вопрос и ответ
    question = Column(Text, nullable=False)  # Вопрос пользователя
    answer = Column(Text, nullable=True)     # Ответ координатора/VP4PR
    is_answered = Column(Boolean, nullable=False, default=False, index=True)
    
    # Timestamps
    asked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    answered_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    task = relationship("Task", foreign_keys=[task_id], back_populates="questions")
    asked_by = relationship("User", foreign_keys=[asked_by_id])
    answered_by = relationship("User", foreign_keys=[answered_by_id])
    
    def __repr__(self):
        return f"<TaskQuestion {self.id} (task: {self.task_id}, answered: {self.is_answered})>"
