"""
Pydantic схемы для задач
"""
from pydantic import BaseModel, Field
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime
from uuid import UUID
from app.models.task import TaskType, TaskPriority, TaskStatus, StageStatus, AssignmentStatus

if TYPE_CHECKING:
    from typing import ForwardRef


class TaskBase(BaseModel):
    """Базовая схема задачи"""
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: TaskType
    event_id: Optional[UUID] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None
    equipment_available: bool = Field(default=False, description="Можно ли получить оборудование для этой задачи (для Channel задач)")
    thumbnail_image_url: Optional[str] = Field(None, description="URL превью изображения для карточки задачи")
    role_specific_requirements: Optional[dict] = Field(None, description="ТЗ по ролям: {'smm': '...', 'design': '...', 'channel': '...', 'prfr': '...'}")
    questions: Optional[List[str]] = Field(None, description="Список вопросов по задаче")
    example_project_ids: Optional[List[UUID]] = Field(None, description="ID примеров прошлых работ")


class TaskCreate(TaskBase):
    """Схема для создания задачи"""
    stages: Optional[List["TaskStageCreate"]] = Field(default=None, description="Этапы задачи (для всех типов задач)")
    equipment_available: Optional[bool] = Field(default=False, description="Можно ли получить оборудование для этой задачи (для Channel задач, устанавливается координатором/VP4PR)")
    script_ready: Optional[bool] = Field(default=True, description="Готов ли сценарий (если False, добавляется этап 'Сценарий')")
    thumbnail_image_url: Optional[str] = Field(None, description="URL превью изображения для карточки задачи")
    role_specific_requirements: Optional[dict] = Field(None, description="ТЗ по ролям: {'smm': '...', 'design': '...', 'channel': '...', 'prfr': '...'}")
    questions: Optional[List[str]] = Field(None, description="Список вопросов по задаче")
    example_project_ids: Optional[List[UUID]] = Field(None, description="ID примеров прошлых работ")


class TaskUpdate(BaseModel):
    """Схема для обновления задачи"""
    title: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    equipment_available: Optional[bool] = Field(None, description="Можно ли получить оборудование для этой задачи (для Channel задач, только координаторы/VP4PR)")
    thumbnail_image_url: Optional[str] = Field(None, description="URL превью изображения для карточки задачи")
    role_specific_requirements: Optional[dict] = Field(None, description="ТЗ по ролям: {'smm': '...', 'design': '...', 'channel': '...', 'prfr': '...'}")
    questions: Optional[List[str]] = Field(None, description="Список вопросов по задаче")
    example_project_ids: Optional[List[UUID]] = Field(None, description="ID примеров прошлых работ")
    sort_order: Optional[int] = Field(None, description="Ручной порядок задачи (меньше = выше, только для VP4PR)")


class TaskResponse(TaskBase):
    """Схема ответа с задачей"""
    id: UUID
    status: TaskStatus
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    drive_folder_id: Optional[str] = None
    drive_file_id: Optional[str] = None
    
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


class TaskFileResponse(BaseModel):
    """Схема ответа с файлом задачи"""
    id: UUID
    drive_id: str
    file_name: str
    file_type: str
    drive_url: Optional[str] = None  # Ссылка на файл в Google Drive
    created_at: datetime
    
    class Config:
        from_attributes = True


class TaskDetailResponse(TaskResponse):
    """Детальная схема задачи (карточка задачи) с этапами, назначениями и материалами"""
    stages: List[TaskStageResponse] = []
    assignments: List[TaskAssignmentResponse] = []
    files: List[TaskFileResponse] = []  # Файлы (материалы задачи) из Google Drive
    thumbnail_image_url: Optional[str] = None
    role_specific_requirements: Optional[dict] = Field(None, description="ТЗ по ролям: {'smm': '...', 'design': '...', 'channel': '...', 'prfr': '...'}")
    questions: Optional[List[str]] = Field(None, description="Список вопросов по задаче")
    example_project_ids: Optional[List[UUID]] = Field(None, description="ID примеров прошлых работ")
    
    class Config:
        from_attributes = True


# ========== Task Templates ==========

class TaskTemplateBase(BaseModel):
    """Базовая схема шаблона задачи"""
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    task_type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    default_description: Optional[str] = None
    equipment_available: bool = False
    role_specific_requirements: Optional[dict] = None
    questions: Optional[List[str]] = None
    example_project_ids: Optional[List[UUID]] = None
    stages_template: Optional[List[dict]] = Field(None, description="Шаблон этапов: [{'stage_name': '...', 'stage_order': 1, 'due_date_offset': 7, 'status_color': 'green'}, ...]")


class TaskTemplateCreate(TaskTemplateBase):
    """Схема для создания шаблона"""
    pass


class TaskTemplateUpdate(BaseModel):
    """Схема для обновления шаблона"""
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    default_description: Optional[str] = None
    equipment_available: Optional[bool] = None
    role_specific_requirements: Optional[dict] = None
    questions: Optional[List[str]] = None
    example_project_ids: Optional[List[UUID]] = None
    stages_template: Optional[List[dict]] = None
    is_active: Optional[bool] = None


class TaskTemplateResponse(TaskTemplateBase):
    """Схема ответа с шаблоном"""
    id: UUID
    category: str
    created_by: UUID
    drive_file_id: Optional[str] = None
    is_system: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Обновляем модель для корректной работы forward references
TaskCreate.model_rebuild()
