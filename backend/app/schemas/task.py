"""
Pydantic схемы для задач
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.task import TaskType, TaskPriority, TaskStatus, StageStatus, AssignmentStatus


class TaskBase(BaseModel):
    """Базовая схема задачи"""
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: TaskType
    event_id: Optional[UUID] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None


class TaskCreate(TaskBase):
    """Схема для создания задачи"""
    pass


class TaskUpdate(BaseModel):
    """Схема для обновления задачи"""
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None


class TaskResponse(TaskBase):
    """Схема ответа с задачей"""
    id: UUID
    status: TaskStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TaskStageBase(BaseModel):
    """Базовая схема этапа задачи"""
    stage_name: str
    stage_order: int = Field(..., gt=0)
    due_date: Optional[datetime] = None
    status_color: str = Field(default="green", pattern="^(green|yellow|red|purple|blue)$")


class TaskStageCreate(TaskStageBase):
    """Схема для создания этапа"""
    pass


class TaskStageUpdate(BaseModel):
    """Схема для обновления этапа"""
    status: Optional[StageStatus] = None
    status_color: Optional[str] = Field(None, pattern="^(green|yellow|red|purple|blue)$")
    completed_at: Optional[datetime] = None


class TaskStageResponse(TaskStageBase):
    """Схема ответа с этапом"""
    id: UUID
    task_id: UUID
    status: StageStatus
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TaskAssignmentBase(BaseModel):
    """Базовая схема назначения"""
    role_in_task: str


class TaskAssignmentCreate(TaskAssignmentBase):
    """Схема для создания назначения"""
    user_id: UUID


class TaskAssignmentResponse(TaskAssignmentBase):
    """Схема ответа с назначением"""
    id: UUID
    task_id: UUID
    user_id: UUID
    status: AssignmentStatus
    rating: Optional[int] = Field(None, ge=1, le=5)
    feedback: Optional[str] = None
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    """Детальная схема задачи с этапами и назначениями"""
    stages: List[TaskStageResponse] = []
    assignments: List[TaskAssignmentResponse] = []
