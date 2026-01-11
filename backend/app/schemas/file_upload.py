"""Схемы для загрузки файлов с модерацией"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from app.models.file_upload import FileUploadStatus, FileUploadCategory


class FileUploadUserInfo(BaseModel):
    """Краткая информация о пользователе"""
    id: UUID
    full_name: str
    telegram_username: Optional[str] = None
    
    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    """Ответ с информацией о загрузке"""
    id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    file_size_mb: float
    category: FileUploadCategory
    description: Optional[str] = None
    status: FileUploadStatus
    drive_url: Optional[str] = None
    task_id: Optional[UUID] = None
    
    uploaded_by: Optional[FileUploadUserInfo] = None
    moderated_by: Optional[FileUploadUserInfo] = None
    moderated_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FileUploadListResponse(BaseModel):
    """Список загрузок"""
    items: List[FileUploadResponse]
    total: int
    skip: int
    limit: int


class ModerationAction(BaseModel):
    """Действие модерации"""
    reason: Optional[str] = None  # Причина отклонения


class FileUploadStats(BaseModel):
    """Статистика загрузок"""
    pending_count: int
    approved_count: int
    rejected_count: int
    total_approved_size_mb: float
