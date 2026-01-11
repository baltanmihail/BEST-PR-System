"""
Схемы для вопросов к задачам
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class TaskQuestionCreate(BaseModel):
    """Схема для создания вопроса"""
    question: str = Field(..., min_length=1, max_length=2000, description="Текст вопроса")


class TaskQuestionAnswer(BaseModel):
    """Схема для ответа на вопрос"""
    answer: str = Field(..., min_length=1, max_length=5000, description="Текст ответа")


class TaskQuestionResponse(BaseModel):
    """Схема ответа с информацией о вопросе"""
    id: UUID
    task_id: UUID
    asked_by_id: UUID
    answered_by_id: Optional[UUID] = None
    question: str
    answer: Optional[str] = None
    is_answered: bool
    asked_at: datetime
    answered_at: Optional[datetime] = None
    asked_by_name: Optional[str] = None  # Имя пользователя, задавшего вопрос
    answered_by_name: Optional[str] = None  # Имя пользователя, ответившего на вопрос
    
    class Config:
        from_attributes = True
