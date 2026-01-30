"""
Модели оборудования
"""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, CheckConstraint, Integer, TypeDecorator, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class EquipmentStatus(str, enum.Enum):
    """Статусы оборудования"""
    AVAILABLE = "available"
    RENTED = "rented"
    MAINTENANCE = "maintenance"
    BROKEN = "broken"


class EquipmentCategory(str, enum.Enum):
    """Категории оборудования"""
    CAMERA = "camera"
    LENS = "lens"
    LIGHTING = "lighting"
    AUDIO = "audio"
    TRIPOD = "tripod"
    ACCESSORIES = "accessories"
    STORAGE = "storage"
    OTHER = "other"


class EquipmentRequestStatus(str, enum.Enum):
    """Статусы заявок на оборудование"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Equipment(Base):
    """Оборудование"""
    __tablename__ = "equipment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    # Используем String для category - PostgreSQL сам кастит к equipmentcategory
    category = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    specs = Column(JSONB, nullable=True)
    # Используем String для status - PostgreSQL сам кастит к equipment_status
    status = Column(String(50), nullable=False, default="available", index=True)
    current_holder_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(name)) > 0", name="equipment_name_not_empty"),
        CheckConstraint("quantity > 0", name="equipment_quantity_positive"),
    )
    
    def __repr__(self):
        return f"<Equipment {self.name} ({self.category}, qty: {self.quantity})>"


class EquipmentRequestStatusType(TypeDecorator):
    """TypeDecorator для EquipmentRequestStatus - всегда lowercase"""
    impl = String(50)
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, EquipmentRequestStatus):
            return value.value
        if isinstance(value, str):
            return value.lower()
        return str(value).lower()
    
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return EquipmentRequestStatus(value.lower())
            except ValueError:
                return EquipmentRequestStatus.PENDING
        return value


class EquipmentRequest(Base):
    """Заявка на оборудование"""
    __tablename__ = "equipment_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    status = Column(EquipmentRequestStatusType(), nullable=False, default=EquipmentRequestStatus.PENDING, index=True)
    rejection_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="equipment_requests_dates_check"),
    )
    
    def __repr__(self):
        return f"<EquipmentRequest {self.id} ({self.status})>"
