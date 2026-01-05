"""
Модель Telegram чата
"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class TelegramChat(Base):
    """Telegram чат для задачи"""
    __tablename__ = "telegram_chats"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)  # Telegram chat ID
    chat_type = Column(String, nullable=False, default="group")  # 'group', 'supergroup'
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<TelegramChat {self.chat_id} (type: {self.chat_type})>"
