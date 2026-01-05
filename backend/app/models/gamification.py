"""
Модели геймификации
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class PointsLog(Base):
    """Лог начисления баллов"""
    __tablename__ = "points_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    points = Column(Integer, nullable=False)  # может быть отрицательным
    reason = Column(String, nullable=False)  # 'task_completed', 'early_completion', 'quality_bonus', etc.
    awarded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    def __repr__(self):
        return f"<PointsLog {self.points} points ({self.reason})>"


class Achievement(Base):
    """Ачивка"""
    __tablename__ = "achievements"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_type = Column(String, nullable=False, index=True)  # 'first_task', 'speedster', 'reliable', etc.
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<Achievement {self.achievement_type}>"
