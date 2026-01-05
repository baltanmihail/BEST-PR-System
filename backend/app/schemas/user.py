"""
Pydantic схемы для пользователей
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.user import UserRole


class UserBase(BaseModel):
    """Базовая схема пользователя"""
    telegram_id: int
    username: Optional[str] = None
    full_name: str
    role: UserRole = UserRole.NOVICE


class UserCreate(UserBase):
    """Схема для создания пользователя"""
    pass


class UserUpdate(BaseModel):
    """Схема для обновления пользователя"""
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Схема ответа с пользователем"""
    id: UUID
    level: int
    points: int
    streak_days: int
    last_activity: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class UserStats(BaseModel):
    """Статистика пользователя"""
    id: UUID
    telegram_id: int
    full_name: str
    role: UserRole
    level: int
    points: int
    streak_days: int
    completed_tasks: int
    active_tasks: int
    achievements_count: int
    
    class Config:
        from_attributes = True
