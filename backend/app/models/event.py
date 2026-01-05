"""
Модель мероприятия
"""
from sqlalchemy import Column, String, Date, Integer, Text, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class Event(Base):
    """Мероприятие"""
    __tablename__ = "events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    date_start = Column(Date, nullable=False, index=True)
    date_end = Column(Date, nullable=False, index=True)
    priority = Column(Integer, nullable=False, default=5, index=True)  # 1-10
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint("priority >= 1 AND priority <= 10", name="events_priority_check"),
        CheckConstraint("date_end >= date_start", name="events_dates_check"),
    )
    
    def __repr__(self):
        return f"<Event {self.name} ({self.date_start} - {self.date_end})>"
