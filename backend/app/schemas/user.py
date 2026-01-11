"""
Pydantic схемы для пользователей
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
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
    last_activity_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    """Схема для обновления профиля пользователя"""
    full_name: Optional[str] = Field(None, min_length=1)
    bio: Optional[str] = Field(None, description="Описание/био пользователя")
    contacts: Optional[Dict[str, str]] = Field(None, description="Контакты: {'email': '...', 'phone': '...', 'telegram': '...', 'vk': '...', 'instagram': '...'}")
    skills: Optional[List[str]] = Field(None, description="Навыки/теги: ['SMM', 'Design', 'Video', ...]")
    portfolio: Optional[List[Dict]] = Field(None, description="Портфолио: [{'title': '...', 'description': '...', 'url': '...', 'type': 'photo|video|link', 'gallery_item_id': '...'}, ...]")


class UserProfileResponse(UserResponse):
    """Схема ответа с полным профилем пользователя"""
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    contacts: Optional[Dict[str, str]] = None
    skills: Optional[List[str]] = None
    portfolio: Optional[List[Dict]] = None
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Схема ответа со списком пользователей"""
    items: List[UserProfileResponse]
    total: int
    skip: int
    limit: int


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
