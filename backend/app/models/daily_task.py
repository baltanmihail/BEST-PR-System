"""
Модель быстрых задач на день (планёрка)
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


class DailyTask(Base):
    __tablename__ = "daily_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    notes = Column(Text, nullable=True)
    date = Column(Date, nullable=False, index=True)
    is_done = Column(Boolean, default=False, nullable=False)
    done_at = Column(DateTime(timezone=True), nullable=True)

    creator_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    creator = relationship("User", foreign_keys=[creator_id], lazy="selectin")
    assignee = relationship("User", foreign_keys=[assignee_id], lazy="selectin")
