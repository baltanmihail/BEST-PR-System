"""
Модель шаблона задачи
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base
from app.models.task import TaskType, TaskPriority


class TemplateCategory(str, enum.Enum):
    """Категории шаблонов"""
    COORDINATOR_SMM = "coordinator_smm"
    COORDINATOR_DESIGN = "coordinator_design"
    COORDINATOR_CHANNEL = "coordinator_channel"
    COORDINATOR_PRFR = "coordinator_prfr"
    VP4PR = "vp4pr"
    CUSTOM = "custom"  # Пользовательские шаблоны


class TemplateCategoryType(TypeDecorator):
    """TypeDecorator для правильной конвертации TemplateCategory в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_ENUM(
                TemplateCategory, 
                name='templatecategory', 
                create_type=False, 
                values_callable=lambda x: [e.value for e in TemplateCategory]
            ))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, TemplateCategory):
            return value.value
        return value
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum"""
        if value is None:
            return None
        if isinstance(value, TemplateCategory):
            return value
        try:
            return TemplateCategory(value)
        except ValueError:
            return value


class TaskTemplate(Base):
    """Шаблон задачи"""
    __tablename__ = "task_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # Название шаблона
    description = Column(Text, nullable=True)  # Описание шаблона
    category = Column(TemplateCategoryType(), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Данные задачи из шаблона
    task_type = Column(Enum(TaskType, name='task_type', create_type=False), nullable=False)
    priority = Column(Enum(TaskPriority, name='task_priority', create_type=False), nullable=False, default=TaskPriority.MEDIUM)
    default_description = Column(Text, nullable=True)
    equipment_available = Column(Boolean, nullable=False, default=False)
    
    # ТЗ по ролям, вопросы, примеры
    role_specific_requirements = Column(JSON, nullable=True)
    questions = Column(JSON, nullable=True)
    example_project_ids = Column(JSON, nullable=True)
    
    # Этапы задачи (JSON массив этапов)
    stages_template = Column(JSON, nullable=True)  # [{"stage_name": "...", "stage_order": 1, "due_date_offset": 7, "status_color": "green"}, ...]
    
    # Google Drive
    drive_file_id = Column(String, nullable=True, index=True)  # ID файла шаблона на Drive
    
    # Метаданные
    is_system = Column(Boolean, nullable=False, default=False)  # Системный шаблон (нельзя удалить)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<TaskTemplate {self.id} ({self.name})>"
