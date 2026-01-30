"""
Pydantic схемы для оборудования
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date
from uuid import UUID
from app.models.equipment import EquipmentStatus, EquipmentRequestStatus, EquipmentCategory


class EquipmentBase(BaseModel):
    """Базовая схема оборудования"""
    name: str = Field(..., min_length=1, description="Название оборудования")
    category: EquipmentCategory = Field(..., description="Категория оборудования")
    quantity: int = Field(1, ge=1, description="Количество экземпляров")
    specs: Optional[Dict[str, Any]] = Field(None, description="Дополнительные характеристики (JSON)")


class EquipmentCreate(EquipmentBase):
    """Схема для создания оборудования"""
    pass


class EquipmentUpdate(BaseModel):
    """Схема для обновления оборудования"""
    name: Optional[str] = Field(None, min_length=1, description="Название оборудования")
    category: Optional[EquipmentCategory] = Field(None, description="Категория оборудования")
    quantity: Optional[int] = Field(None, ge=1, description="Количество экземпляров")
    specs: Optional[Dict[str, Any]] = Field(None, description="Дополнительные характеристики (JSON)")
    status: Optional[EquipmentStatus] = Field(None, description="Статус оборудования")


class EquipmentResponse(EquipmentBase):
    """Схема ответа с оборудованием"""
    id: UUID
    status: EquipmentStatus
    current_holder_id: Optional[UUID] = None
    next_available_date: Optional[date] = Field(None, description="Дата, когда оборудование освободится")
    available_count: Optional[int] = Field(None, description="Количество доступных экземпляров")
    booked_count: Optional[int] = Field(None, description="Количество забронированных экземпляров")
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class EquipmentWithAvailability(EquipmentResponse):
    """Схема оборудования с информацией о доступности"""
    available_quantity: int = Field(..., description="Количество доступных экземпляров на указанные даты")
    
    class Config:
        from_attributes = True


class EquipmentRequestBase(BaseModel):
    """Базовая схема заявки на оборудование"""
    equipment_id: UUID
    start_date: date
    end_date: date
    task_id: Optional[UUID] = None


class EquipmentRequestCreate(EquipmentRequestBase):
    """Схема для создания заявки"""
    pass


class EquipmentRequestUpdate(BaseModel):
    """Схема для обновления заявки"""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[EquipmentRequestStatus] = None


class EquipmentRequestResponse(EquipmentRequestBase):
    """Схема ответа с заявкой"""
    id: UUID
    user_id: UUID
    status: EquipmentRequestStatus
    rejection_reason: Optional[str] = None
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
