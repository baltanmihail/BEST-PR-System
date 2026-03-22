"""
Модель галереи проектов
"""
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, CheckConstraint, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSON, ENUM as PG_ENUM
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy import TypeDecorator
import uuid
from enum import Enum as PyEnum

from app.database import Base


class GalleryCategory(PyEnum):
    """Категории работ в галерее"""
    PHOTO = "photo"
    VIDEO = "video"
    FINAL = "final"
    WIP = "wip"


class GalleryCategoryType(TypeDecorator):
    """TypeDecorator для правильной конвертации GalleryCategory enum → строку"""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(
                PG_ENUM(GalleryCategory, name='gallery_category', create_type=False,
                        values_callable=lambda x: [e.value for e in GalleryCategory])
            )
        return dialect.type_descriptor(String(20))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, GalleryCategory):
            return value.value
        if isinstance(value, str):
            return value.lower()
        return str(value).lower()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return GalleryCategory(value)
        except (ValueError, KeyError):
            return GalleryCategory.FINAL


class GalleryItem(Base):
    """Элемент галереи проектов"""
    __tablename__ = "gallery_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    category = Column(GalleryCategoryType(), nullable=False, default=GalleryCategory.FINAL, index=True)
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
