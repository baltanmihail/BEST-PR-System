"""
Модель загрузки файлов с модерацией

Процесс:
1. Пользователь загружает файл → статус PENDING
2. Файл сохраняется во временную папку на Google Drive
3. VP4PR/Координатор видит файл в очереди модерации
4. При одобрении → файл перемещается в постоянную папку
5. При отклонении → файл удаляется
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class FileUploadStatus(str, enum.Enum):
    """Статусы загрузки файла"""
    PENDING = "pending"      # Ожидает модерации
    APPROVED = "approved"    # Одобрен
    REJECTED = "rejected"    # Отклонён


class FileUploadCategory(str, enum.Enum):
    """Категории загружаемых файлов"""
    TASK_MATERIAL = "task_material"    # Материалы для задачи
    GALLERY = "gallery"                 # Галерея работ
    TEMPLATE = "template"               # Шаблон
    EQUIPMENT_PHOTO = "equipment_photo" # Фото оборудования
    OTHER = "other"                     # Прочее


class FileUpload(Base):
    """Загрузка файла с модерацией"""
    __tablename__ = "file_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Кто загрузил
    uploaded_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Информация о файле
    original_filename = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)  # Размер в байтах
    
    # Google Drive
    temp_drive_id = Column(String(100), nullable=True)  # ID файла во временной папке
    final_drive_id = Column(String(100), nullable=True)  # ID файла в постоянной папке (после одобрения)
    drive_url = Column(String(500), nullable=True)       # Ссылка на файл
    
    # Категория и связи
    category = Column(
        PG_ENUM(FileUploadCategory, name='file_upload_category', create_type=False),
        nullable=False,
        default=FileUploadCategory.OTHER
    )
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("task_stages.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Описание от загрузившего
    description = Column(Text, nullable=True)
    
    # Статус модерации
    status = Column(
        PG_ENUM(FileUploadStatus, name='file_upload_status', create_type=False),
        nullable=False,
        default=FileUploadStatus.PENDING,
        index=True
    )
    
    # Модерация
    moderated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)  # Причина отклонения
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id], backref="uploaded_files")
    moderated_by = relationship("User", foreign_keys=[moderated_by_id])
    task = relationship("Task", foreign_keys=[task_id], back_populates="files")
    stage = relationship("TaskStage", foreign_keys=[stage_id], back_populates="files")
    
    def __repr__(self):
        return f"<FileUpload {self.original_filename} ({self.status.value})>"
    
    @property
    def file_size_mb(self) -> float:
        """Размер файла в МБ"""
        return round(self.file_size / 1024 / 1024, 2)
    
    @property
    def is_pending(self) -> bool:
        return self.status == FileUploadStatus.PENDING
    
    @property
    def is_approved(self) -> bool:
        return self.status == FileUploadStatus.APPROVED
    
    @property
    def is_rejected(self) -> bool:
        return self.status == FileUploadStatus.REJECTED
