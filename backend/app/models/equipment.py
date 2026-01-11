"""
Модели оборудования
"""
from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Enum, CheckConstraint, Integer, TypeDecorator
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
    CAMERA = "camera"  # Камеры
    LENS = "lens"  # Объективы
    LIGHTING = "lighting"  # Свет
    AUDIO = "audio"  # Аудио оборудование
    TRIPOD = "tripod"  # Штативы
    ACCESSORIES = "accessories"  # Аксессуары
    STORAGE = "storage"  # Накопители
    OTHER = "other"  # Прочее


class EquipmentCategoryType(TypeDecorator):
    """TypeDecorator для правильной конвертации EquipmentCategory в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_ENUM(EquipmentCategory, name='equipmentcategory', create_type=False, values_callable=lambda x: [e.value for e in EquipmentCategory]))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, EquipmentCategory):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return EquipmentCategory(value)
            except ValueError:
                return EquipmentCategory.OTHER
        return value


class EquipmentRequestStatus(str, enum.Enum):
    """Статусы заявок на оборудование"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EquipmentRequestStatusType(TypeDecorator):
    """TypeDecorator для правильной конвертации EquipmentRequestStatus в строку.
    
    ВАЖНО: Используем String вместо PG_ENUM, чтобы process_bind_param вызывался
    для всех операций, включая .in_(). PostgreSQL автоматически кастит строки
    к типу equipment_request_status при вставке/сравнении.
    """
    impl = String(50)
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку) - lowercase"""
        if value is None:
            return None
        if isinstance(value, EquipmentRequestStatus):
            return value.value  # Возвращает 'approved', 'active' и т.д.
        # Если передана строка, конвертируем в lowercase
        if isinstance(value, str):
            return value.lower()
        return str(value).lower() if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return EquipmentRequestStatus(value.lower())
            except ValueError:
                return EquipmentRequestStatus.PENDING
        return value


class Equipment(Base):
    """Оборудование"""
    __tablename__ = "equipment"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    category = Column(EquipmentCategoryType(), nullable=False, index=True)  # Категория оборудования
    quantity = Column(Integer, nullable=False, default=1)  # Количество экземпляров (по умолчанию 1)
    specs = Column(JSONB, nullable=True)  # Дополнительные характеристики
    status = Column(Enum(EquipmentStatus), nullable=False, default=EquipmentStatus.AVAILABLE, index=True)
    current_holder_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(name)) > 0", name="equipment_name_not_empty"),
        CheckConstraint("quantity > 0", name="equipment_quantity_positive"),
    )
    
    def __repr__(self):
        return f"<Equipment {self.name} ({self.category.value}, qty: {self.quantity})>"


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
