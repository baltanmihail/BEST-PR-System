"""
Модели задач
"""
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum, Integer, CheckConstraint, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID, ENUM as PG_ENUM
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class TaskType(str, enum.Enum):
    """Типы задач"""
    SMM = "smm"
    DESIGN = "design"
    CHANNEL = "channel"
    PRFR = "prfr"


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
    COMPLETED = "completed"


class AssignmentStatus(str, enum.Enum):
    """Статусы назначений"""
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(Base):
    """Задача"""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    type = Column(Enum(TaskType), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.MEDIUM, index=True)
    status = Column(TaskStatusType(), nullable=False, default=TaskStatus.DRAFT, server_default='draft', index=True)
    
    @validates('status')
    def validate_status(self, key, value):
        """Валидация статуса перед сохранением"""
        if value is None:
            return None
        if isinstance(value, TaskStatus):
            return value.value
        return str(value) if value else None
    due_date = Column(DateTime(timezone=True), nullable=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    stages = relationship("TaskStage", back_populates="task", cascade="all, delete-orphan")
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")
    
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
    status = Column(Enum(AssignmentStatus), nullable=False, default=AssignmentStatus.ASSIGNED, index=True)
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
