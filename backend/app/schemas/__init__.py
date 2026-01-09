"""
Pydantic схемы
"""
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse, UserStats
from app.schemas.task import (
    TaskBase, TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse,
    TaskStageBase, TaskStageCreate, TaskStageUpdate, TaskStageResponse,
    TaskAssignmentBase, TaskAssignmentCreate, TaskAssignmentResponse,
    TaskTemplateBase, TaskTemplateCreate, TaskTemplateUpdate, TaskTemplateResponse
)
from app.schemas.equipment import (
    EquipmentBase, EquipmentCreate, EquipmentUpdate, EquipmentResponse,
    EquipmentRequestBase, EquipmentRequestCreate, EquipmentRequestUpdate, EquipmentRequestResponse
)

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse", "UserStats",
    "TaskBase", "TaskCreate", "TaskUpdate", "TaskResponse", "TaskDetailResponse",
    "TaskStageBase", "TaskStageCreate", "TaskStageUpdate", "TaskStageResponse",
    "TaskAssignmentBase", "TaskAssignmentCreate", "TaskAssignmentResponse",
    "TaskTemplateBase", "TaskTemplateCreate", "TaskTemplateUpdate", "TaskTemplateResponse",
    "EquipmentBase", "EquipmentCreate", "EquipmentUpdate", "EquipmentResponse",
    "EquipmentRequestBase", "EquipmentRequestCreate", "EquipmentRequestUpdate", "EquipmentRequestResponse",
]
