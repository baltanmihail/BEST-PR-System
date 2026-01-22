"""
Pydantic схемы для галереи проектов
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from app.models.gallery import GalleryCategory
from app.models.task import TaskStatus


class GalleryTaskInfo(BaseModel):
    """Краткая информация о связанной задаче"""
    id: UUID
    title: str
    description: Optional[str] = None
    status: TaskStatus
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GalleryFileInfo(BaseModel):
    """Информация о файле в галерее"""
    drive_id: str = Field(..., description="ID файла в Google Drive")
    file_name: str = Field(..., description="Название файла")
    file_type: str = Field(..., description="Тип файла (image, video, document, etc.)")
    thumbnail_url: Optional[str] = Field(None, description="URL превью файла")
    drive_url: Optional[str] = Field(None, description="Ссылка для просмотра файла в Google Drive")
    file_size: Optional[int] = Field(None, description="Размер файла в байтах")
    mime_type: Optional[str] = Field(None, description="MIME-тип файла")
    
    class Config:
        from_attributes = True


class GalleryItemBase(BaseModel):
    """Базовая схема элемента галереи"""
    title: str = Field(..., min_length=1, max_length=200, description="Название проекта/работы")
    description: Optional[str] = Field(None, description="Описание проекта")
    category: GalleryCategory = Field(GalleryCategory.FINAL, description="Категория работы")
    tags: Optional[List[str]] = Field(None, description="Дополнительные теги")
    task_id: Optional[UUID] = Field(None, description="ID связанной задачи (если есть)")
    thumbnail_url: Optional[str] = Field(None, description="URL превью (миниатюры)")


class GalleryItemCreate(GalleryItemBase):
    """Схема для создания элемента галереи"""
    files: Optional[List[GalleryFileInfo]] = Field(default_factory=list, description="Файлы для загрузки")


class GalleryItemUpdate(BaseModel):
    """Схема для обновления элемента галереи"""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[GalleryCategory] = None
    tags: Optional[List[str]] = None
    task_id: Optional[UUID] = None
    thumbnail_url: Optional[str] = None
    files: Optional[List[GalleryFileInfo]] = None  # Для добавления новых файлов
    sort_order: Optional[int] = Field(None, description="Ручной порядок (только для VP4PR)")


class GalleryItemResponse(GalleryItemBase):
    """Схема для ответа с элементом галереи"""
    id: UUID
    files: List[GalleryFileInfo] = Field(default_factory=list)
    created_by: UUID
    creator_name: Optional[str] = Field(None, description="Имя создателя")
    task: Optional[GalleryTaskInfo] = Field(None, description="Информация о связанной задаче")
    sort_order: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class GalleryItemListResponse(BaseModel):
    """Схема для списка элементов галереи"""
    items: List[GalleryItemResponse]
    total: int
    skip: int
    limit: int
