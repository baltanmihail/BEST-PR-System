"""
Модель галереи проектов
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, Enum, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from enum import Enum as PyEnum

from app.database import Base


class GalleryCategory(PyEnum):
    """Категории работ в галерее"""
    PHOTO = "photo"  # Фото
    VIDEO = "video"  # Видео
    FINAL = "final"  # Финальные работы
    WIP = "wip"  # Work in Progress (черновики/в процессе)


class GalleryItem(Base):
    """Элемент галереи проектов"""
    __tablename__ = "gallery_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)  # Название проекта/работы
    description = Column(Text, nullable=True)  # Описание проекта
    
    # Категория и теги
    category = Column(Enum(GalleryCategory, name="gallery_category"), nullable=False, default=GalleryCategory.FINAL, index=True)
    tags = Column(ARRAY(String), nullable=True)  # Дополнительные теги
    
    # Связи
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)  # Связанная задача (если есть)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Файлы (хранятся как JSON массив с информацией о файлах в Google Drive)
    # Формат: [{"drive_id": "...", "file_name": "...", "file_type": "...", "thumbnail_url": "..."}, ...]
    files = Column(JSON, nullable=False, default=list)  # Массив файлов в Google Drive
    
    # Превью (миниатюра для отображения)
    thumbnail_url = Column(String, nullable=True)  # URL превью (первого файла или загруженного вручную)
    
    # Ручной порядок (только для VP4PR)
    sort_order = Column(Integer, nullable=True, index=True)  # NULL = автоматическая сортировка, число = ручной порядок
    
    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    task = relationship("Task", foreign_keys=[task_id])
    creator = relationship("User", foreign_keys=[created_by])
    
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(title)) > 0", name="gallery_items_title_not_empty"),
    )
    
    def __repr__(self):
        return f"<GalleryItem {self.title} (category: {self.category.value})>"
