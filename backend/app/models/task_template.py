"""
Модель шаблона задачи
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
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


class TaskTemplate(Base):
    """Шаблон задачи"""
    __tablename__ = "task_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)  # Название шаблона
    description = Column(Text, nullable=True)  # Описание шаблона
    category = Column(Enum(TemplateCategory), nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Данные задачи из шаблона
    task_type = Column(Enum(TaskType), nullable=False)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM)
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
