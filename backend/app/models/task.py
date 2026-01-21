"""
Модели задач
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Integer, Boolean, CheckConstraint, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM, JSON
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableDict, MutableList
import uuid
import enum
import json

from app.database import Base


class TaskType(str, enum.Enum):
    """Типы задач"""
    SMM = "smm"
    DESIGN = "design"
    CHANNEL = "channel"
    PRFR = "prfr"
    MULTITASK = "multitask"  # Многозадачная - для задач, которые требуют работы нескольких ролей


class TaskPriority(str, enum.Enum):
    """Приоритеты задач"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, enum.Enum):
    """Статусы задач"""
    DRAFT = "draft"
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriorityType(TypeDecorator):
    """TypeDecorator для правильной конвертации TaskPriority в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            # Используем правильное имя типа из базы данных: task_priority (с подчеркиванием)
            return dialect.type_descriptor(PG_ENUM(
                TaskPriority, 
                name='task_priority', 
                create_type=False, 
                values_callable=lambda x: [e.value for e in TaskPriority]
            ))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, TaskPriority):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return TaskPriority(value)
            except ValueError:
                return TaskPriority.MEDIUM
        return value


class TaskStatusType(TypeDecorator):
    """TypeDecorator для правильной конвертации TaskStatus в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            # Используем правильное имя типа из базы данных
            return dialect.type_descriptor(PG_ENUM(
                TaskStatus, 
                name='task_status', 
                create_type=False, 
                values_callable=lambda x: [e.value for e in TaskStatus]
            ))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, TaskStatus):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return TaskStatus(value)
            except ValueError:
                return TaskStatus.DRAFT
        return value


class StageStatus(str, enum.Enum):
    """Статусы этапов"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"


class AssignmentStatus(str, enum.Enum):
    """Статусы назначений"""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentStatusType(TypeDecorator):
    """TypeDecorator для правильной конвертации AssignmentStatus в строку"""
    impl = String
    cache_ok = True
    
    def __init__(self):
        super().__init__(length=50)
    
    def load_dialect_impl(self, dialect):
        """Используем PostgreSQL ENUM для PostgreSQL"""
        if dialect.name == 'postgresql':
            # Используем правильное имя типа из базы данных: assignment_status (с подчеркиванием)
            return dialect.type_descriptor(PG_ENUM(
                AssignmentStatus, 
                name='assignment_status', 
                create_type=False, 
                values_callable=lambda x: [e.value for e in AssignmentStatus]
            ))
        else:
            return dialect.type_descriptor(String(50))
    
    def process_bind_param(self, value, dialect):
        """Конвертируем enum в его значение (строку)"""
        if value is None:
            return None
        if isinstance(value, AssignmentStatus):
            return value.value
        return str(value) if value else None
    
    def process_result_value(self, value, dialect):
        """Конвертируем строку обратно в enum при чтении из БД"""
        if value is None:
            return None
        if isinstance(value, str):
            try:
                return AssignmentStatus(value)
            except ValueError:
                return AssignmentStatus.ASSIGNED
        return value


class Task(Base):
    """Задача"""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_number = Column(Integer, nullable=True, unique=True, index=True)  # Автоинкремент: TASK-001, TASK-002, ...
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(Enum(TaskType), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(TaskPriorityType(), nullable=False, default=TaskPriority.MEDIUM, server_default='medium', index=True)
    status = Column(TaskStatusType(), nullable=False, default=TaskStatus.DRAFT, server_default='draft', index=True)
    
    @validates('status')
    def validate_status(self, key, value):
        """Валидация статуса перед сохранением.

        ВАЖНО: возвращаем TaskStatus (enum), чтобы сравнения в коде работали:
        `task.status == TaskStatus.ASSIGNED` и т.п.
        Конвертацию в строку делает TaskStatusType.process_bind_param().
        """
        if value is None:
            return None
        if isinstance(value, TaskStatus):
            return value
        if isinstance(value, str):
            try:
                return TaskStatus(value)
            except ValueError:
                return TaskStatus.DRAFT
        return value
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для ручного управления порядком задач (только для VP4PR)
    sort_order = Column(Integer, nullable=True, index=True)  # NULL = автоматическая сортировка, число = ручной порядок (меньше = выше)
    
    # Поле для отметки возможности получения оборудования (для Channel задач)
    equipment_available = Column(Boolean, nullable=False, default=False, index=True)  # True = можно получить оборудование для этой задачи
    
    # Поля для карточки задачи
    thumbnail_image_url = Column(String, nullable=True)  # URL превью изображения (из Google Drive)
    role_specific_requirements = Column(JSON, nullable=True)  # JSON с ТЗ для каждой роли: {"smm": "...", "design": "...", "channel": "...", "prfr": "..."}
    # ПРИМЕЧАНИЕ: questions теперь через relationship к TaskQuestion, старое JSON поле удалено
    example_project_ids = Column(JSON, nullable=True)  # JSON список ID примеров прошлых работ (как строки UUID): ["task_id1", "task_id2", ...]
    
    # Google Drive интеграция
    drive_folder_id = Column(String, nullable=True, index=True)  # ID папки задачи в Google Drive
    drive_file_id = Column(String, nullable=True)  # ID Google Doc файла с описанием задачи
    drive_last_sync = Column(DateTime(timezone=True), nullable=True)  # Время последней синхронизации с Drive
    
    # Relationships
    stages = relationship("TaskStage", back_populates="task", cascade="all, delete-orphan", order_by="TaskStage.stage_order")
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    questions = relationship("TaskQuestion", back_populates="task", cascade="all, delete-orphan", order_by="TaskQuestion.asked_at.desc()")
    # Файлы (материалы задачи)
    files = relationship("FileUpload", back_populates="task", cascade="all, delete-orphan")
    
    
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(title)) > 0", name="tasks_title_not_empty"),
    )
    
    def __repr__(self):
        return f"<Task {self.id} ({self.title})>"


class TaskStage(Base):
    """Этап задачи"""
    __tablename__ = "task_stages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_name = Column(String, nullable=False)  # 'script', 'shooting', 'editing', 'review', 'publication'
    stage_order = Column(Integer, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(Enum(StageStatus), nullable=False, default=StageStatus.PENDING, index=True)
    status_color = Column(String, nullable=False, default="green")  # 'green', 'yellow', 'red', 'purple', 'blue'
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    task = relationship("Task", back_populates="stages")
    files = relationship("FileUpload", back_populates="stage", cascade="all, delete-orphan")
    
    __table_args__ = (
        CheckConstraint("stage_order > 0", name="task_stages_order_check"),
        CheckConstraint("status_color IN ('green', 'yellow', 'red', 'purple', 'blue')", name="task_stages_color_check"),
    )
    
    def __repr__(self):
        return f"<TaskStage {self.stage_name} (order: {self.stage_order})>"


class TaskAssignment(Base):
    """Назначение задачи"""
    __tablename__ = "task_assignments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_in_task = Column(String, nullable=False)  # 'executor', 'designer', 'videographer', 'reviewer'
    # Используем существующий в БД ENUM assignment_status (создан в миграции 001)
    status = Column(AssignmentStatusType(), nullable=False, default=AssignmentStatus.ASSIGNED, server_default='assigned', index=True)
    rating = Column(Integer, nullable=True)  # 1-5
    feedback = Column(Text, nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    task = relationship("Task", back_populates="assignments")
    user = relationship("User", foreign_keys=[user_id])
    
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="task_assignments_rating_check"),
    )
    
    def __repr__(self):
        return f"<TaskAssignment {self.role_in_task} (status: {self.status})>"
