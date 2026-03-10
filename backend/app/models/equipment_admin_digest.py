"""
Одно обновляемое сообщение-дайджест для VP4PR и Channel.
Оборудование — зона Channel, не PR-FR.
"""
from sqlalchemy import Column, Integer, BigInteger, DateTime, UniqueConstraint
from sqlalchemy.sql import func
import uuid

from app.database import Base


class EquipmentAdminDigest(Base):
    """Одно сообщение в TG на координатора — обновляется при новых заявках/напоминаниях"""
    __tablename__ = "equipment_admin_digest"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, nullable=False, unique=True, index=True)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=True)  # None = ещё не отправлено
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
