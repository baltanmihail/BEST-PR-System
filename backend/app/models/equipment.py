"""
Модели оборудования
"""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, CheckConstraint, Integer, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM
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


# PostgreSQL ENUM типы (уже существуют в БД, create_type=False)
# Важно: values_callable возвращает lowercase значения
equipment_category_enum = PG_ENUM(
    'camera', 'lens', 'lighting', 'audio', 'tripod', 'accessories', 'storage', 'other',
    name='equipmentcategory',
    create_type=False  # НЕ создавать тип, он уже есть в БД
)

equipment_status_enum = PG_ENUM(
    'available', 'rented', 'maintenance', 'broken',
    name='equipment_status',
    create_type=False  # НЕ создавать тип, он уже есть в БД
)


class EquipmentCategoryType(TypeDecorator):
    """
    TypeDecorator для EquipmentCategory.
    Использует PostgreSQL ENUM как impl и конвертирует Python enum в lowercase строки.
    """
    impl = equipment_category_enum
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """При записи в БД — всегда lowercase строка"""
        if value is None:
            return 'other'
        if isinstance(value, EquipmentCategory):
            return value.value  # value уже lowercase
        if isinstance(value, str):
            return value.lower()
        return str(value).lower()
    
    def process_result_value(self, value, dialect):
        """При чтении из БД — конвертируем в Python enum"""
        if value is None:
            return EquipmentCategory.OTHER
        try:
            return EquipmentCategory(value.lower() if isinstance(value, str) else value)
        except (ValueError, AttributeError):
            return EquipmentCategory.OTHER


class EquipmentStatusType(TypeDecorator):
    """
    TypeDecorator для EquipmentStatus.
    Использует PostgreSQL ENUM как impl и конвертирует Python enum в lowercase строки.
    """
    impl = equipment_status_enum
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """При записи в БД — всегда lowercase строка"""
        if value is None:
            return 'available'
        if isinstance(value, EquipmentStatus):
            return value.value  # value уже lowercase
        if isinstance(value, str):
            return value.lower()
        return str(value).lower()
    
    def process_result_value(self, value, dialect):
        """При чтении из БД — конвертируем в Python enum"""
        if value is None:
            return EquipmentStatus.AVAILABLE
        try:
            return EquipmentStatus(value.lower() if isinstance(value, str) else value)
        except (ValueError, AttributeError):
            return EquipmentStatus.AVAILABLE


class Equipment(Base):
    """Оборудование"""
    __tablename__ = "equipment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    # Используем TypeDecorator с PG_ENUM для правильной работы с PostgreSQL ENUM типом
    category = Column(EquipmentCategoryType(), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    specs = Column(JSONB, nullable=True)
    # Используем TypeDecorator с PG_ENUM для правильной работы с PostgreSQL ENUM типом
    status = Column(EquipmentStatusType(), nullable=False, default="available", index=True)
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
