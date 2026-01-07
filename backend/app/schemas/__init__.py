"""
Pydantic схемы
"""
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse, UserStats
from app.schemas.task import (
    TaskBase, TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse,
    TaskStageBase, TaskStageCreate, TaskStageUpdate, TaskStageResponse,
    TaskAssignmentBase, TaskAssignmentCreate, TaskAssignmentResponse
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
    "EquipmentBase", "EquipmentCreate", "EquipmentUpdate", "EquipmentResponse",
    "EquipmentRequestBase", "EquipmentRequestCreate", "EquipmentRequestUpdate", "EquipmentRequestResponse",
]
