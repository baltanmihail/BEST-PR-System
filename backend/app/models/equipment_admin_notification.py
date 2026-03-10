"""
Модель для хранения ID уведомлений координаторам о новых заявках.
При approve/reject удаляем эти сообщения (как в BEST Channel Bot).
"""
from sqlalchemy import Column, Integer, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class EquipmentAdminNotification(Base):
    """ID сообщения в TG координатору о новой заявке — удаляется при approve/reject"""
    __tablename__ = "equipment_admin_notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("equipment_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
