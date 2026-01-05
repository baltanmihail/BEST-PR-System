"""
Модель пользователя
"""
from sqlalchemy import Column, BigInteger, String, Integer, Boolean, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    """Роли пользователей"""
    NOVICE = "novice"
    PARTICIPANT = "participant"
    ACTIVE_PARTICIPANT = "active_participant"
    COORDINATOR_SMM = "coordinator_smm"
    COORDINATOR_DESIGN = "coordinator_design"
    COORDINATOR_CHANNEL = "coordinator_channel"
    COORDINATOR_PRFR = "coordinator_prfr"
    VP4PR = "vp4pr"


class User(Base):
    """Пользователь"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.NOVICE)
    level = Column(Integer, nullable=False, default=1)
    points = Column(Integer, nullable=False, default=0, index=True)
    streak_days = Column(Integer, nullable=False, default=0)
    last_activity = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    
    def __repr__(self):
        return f"<User {self.telegram_id} ({self.full_name})>"
