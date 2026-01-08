"""
Модель Telegram чата
"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class TelegramChat(Base):
    """Telegram чат для задачи или общий чат с поддержкой тем (Topics)"""
    __tablename__ = "telegram_chats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, unique=True, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)  # Telegram chat ID (общий чат для всех тем)
    chat_type = Column(String, nullable=False, default="group")  # 'group', 'supergroup'
    chat_name = Column(String, nullable=True)  # Название чата
    invite_link = Column(String, nullable=True)  # Ссылка-приглашение
    is_general = Column(Boolean, nullable=False, default=False, index=True)  # Общий чат для всех пользователей
    is_active = Column(Boolean, nullable=False, default=True)  # Активен ли чат
    
    # Поля для работы с темами (Topics)
    topic_id = Column(BigInteger, nullable=True, index=True)  # ID темы (message_thread_id) - для задач
    topic_name = Column(String, nullable=True)  # Название темы
    is_open_topic = Column(Boolean, nullable=False, default=True)  # Открытая тема (видят все) или закрытая (только участники)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self):
        if self.is_general:
            return f"<TelegramChat {self.chat_id} (general chat)>"
        if self.topic_id:
            return f"<TelegramChat {self.chat_id} (topic: {self.topic_id}, task: {self.task_id})>"
        return f"<TelegramChat {self.chat_id} (task: {self.task_id}, type: {self.chat_type})>"
