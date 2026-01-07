"""
Pydantic схемы для оборудования
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import date
from uuid import UUID
from app.models.equipment import EquipmentStatus, EquipmentRequestStatus


class EquipmentBase(BaseModel):
    """Базовая схема оборудования"""
    name: str = Field(..., min_length=1)
    category: str
    specs: Optional[Dict[str, Any]] = None


class EquipmentCreate(EquipmentBase):
    """Схема для создания оборудования"""
    pass


class EquipmentUpdate(BaseModel):
    """Схема для обновления оборудования"""
    name: Optional[str] = Field(None, min_length=1)
    category: Optional[str] = None
    specs: Optional[Dict[str, Any]] = None
    status: Optional[EquipmentStatus] = None


class EquipmentResponse(EquipmentBase):
    """Схема ответа с оборудованием"""
    id: UUID
    status: EquipmentStatus
    current_holder_id: Optional[UUID] = None
    created_at: str
    updated_at: str
    
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
