"""
Модель предложений концептов и идей для задач
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class SuggestionType(str, enum.Enum):
    """Типы предложений"""
    CONCEPT = "concept"  # Концепт
    IDEA = "idea"  # Идея
    SCRIPT = "script"  # Сценарий
    TEXT = "text"  # Текст поста
    OTHER = "other"  # Другое


class SuggestionStatus(str, enum.Enum):
    """Статусы предложений"""
    PENDING = "pending"  # На рассмотрении
    APPROVED = "approved"  # Одобрено
    REJECTED = "rejected"  # Отклонено
    IN_USE = "in_use"  # Используется


class TaskSuggestion(Base):
    """Предложение концепта/идеи для задачи"""
    __tablename__ = "task_suggestions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(SuggestionType), nullable=False, index=True)
    title = Column(String, nullable=False)  # Краткое название предложения
    content = Column(Text, nullable=False)  # Содержание (концепт, идея, сценарий, текст)
    files = Column(JSONB, nullable=True)  # Ссылки на файлы (Google Drive IDs)
    status = Column(Enum(SuggestionStatus), nullable=False, default=SuggestionStatus.PENDING, index=True)
    feedback = Column(Text, nullable=True)  # Обратная связь от координатора
    ai_analysis = Column(JSONB, nullable=True)  # Анализ от ИИ (структурированный, предложения)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    task = relationship("Task", backref="suggestions")
    user = relationship("User", foreign_keys=[user_id], backref="suggestions")
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<TaskSuggestion {self.type.value} for task {self.task_id}>"
