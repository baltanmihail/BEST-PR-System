"""
Pydantic схемы
"""
from app.schemas.user import UserBase, UserCreate, UserUpdate, UserResponse, UserStats
from app.schemas.task import (
    TaskBase, TaskCreate, TaskUpdate, TaskResponse, TaskDetailResponse,
    TaskStageBase, TaskStageCreate, TaskStageUpdate, TaskStageResponse,
    TaskAssignmentBase, TaskAssignmentCreate, TaskAssignmentResponse
)

__all__ = [
    "UserBase", "UserCreate", "UserUpdate", "UserResponse", "UserStats",
    "TaskBase", "TaskCreate", "TaskUpdate", "TaskResponse", "TaskDetailResponse",
    "TaskStageBase", "TaskStageCreate", "TaskStageUpdate", "TaskStageResponse",
    "TaskAssignmentBase", "TaskAssignmentCreate", "TaskAssignmentResponse",
]
