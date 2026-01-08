"""
API endpoints для работы с Telegram чатами
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
import logging

from app.database import get_db
from app.models.user import User
from app.utils.permissions import get_current_user
from app.services.telegram_chat_service import TelegramChatService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram-chats", tags=["telegram-chats"])


@router.get("/general", response_model=dict)
async def get_general_chat(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию об общем чате
    
    Доступно только зарегистрированным пользователям
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active users can access the general chat"
        )
    
    # Получаем или создаём общий чат
    general_chat = await TelegramChatService.get_or_create_general_chat(db)
    
    if not general_chat:
        return {
            "exists": False,
            "message": "General chat not configured. Please contact administrator."
        }
    
    # Получаем ссылку-приглашение
    invite_link = await TelegramChatService.get_chat_invite_link(db, general_chat.chat_id)
    
    return {
        "exists": True,
        "chat_id": str(general_chat.chat_id),
        "chat_name": general_chat.chat_name or "BEST PR System - Общий чат",
        "chat_type": general_chat.chat_type,
        "invite_link": invite_link,
        "is_active": general_chat.is_active
    }


@router.get("/task/{task_id}", response_model=dict)
async def get_task_chat(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о теме для задачи
    
    Доступно только участникам задачи, координаторам и VP4PR
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active users can access task topics"
        )
    
    # Проверяем, является ли пользователь участником задачи
    # TODO: Добавить проверку участия в задаче
    # Пока что разрешаем всем активным пользователям
    
    # Получаем тему для задачи
    task_topic = await TelegramChatService.get_task_topic(db, task_id)
    
    if not task_topic:
        return {
            "exists": False,
            "message": "Topic for this task not created yet",
            "is_topic": True
        }
    
    # Получаем ссылку-приглашение на общий чат (темы находятся в общем чате)
    invite_link = await TelegramChatService.get_chat_invite_link(db, task_topic.chat_id)
    
    return {
        "exists": True,
        "is_topic": True,
        "chat_id": str(task_topic.chat_id),  # ID общего чата
        "topic_id": str(task_topic.topic_id) if task_topic.topic_id else None,
        "topic_name": task_topic.topic_name or f"Task {task_id}",
        "is_open_topic": task_topic.is_open_topic,
        "invite_link": invite_link,  # Ссылка на общий чат
        "is_active": task_topic.is_active
    }


@router.post("/task/{task_id}/create-topic", response_model=dict)
async def create_task_topic(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать тему для задачи в общем чате
    
    Доступно только координаторам и VP4PR
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active users can create task topics"
        )
    
    # Проверяем права (только координаторы)
    from app.models.user import UserRole
    is_coordinator = current_user.role in [
        UserRole.COORDINATOR_SMM,
        UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL,
        UserRole.COORDINATOR_PRFR,
        UserRole.VP4PR
    ]
    
    if not is_coordinator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators can create task topics"
        )
    
    # Получаем задачу
    from app.services.task_service import TaskService
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Создаём тему для задачи
    task_topic = await TelegramChatService.create_task_topic(
        db=db,
        task_id=task_id,
        task_title=task.title
    )
    
    if not task_topic:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create task topic"
        )
    
    # Получаем ссылку-приглашение
    invite_link = await TelegramChatService.get_chat_invite_link(db, task_topic.chat_id)
    
    return {
        "exists": True,
        "is_topic": True,
        "chat_id": str(task_topic.chat_id),
        "topic_id": str(task_topic.topic_id),
        "topic_name": task_topic.topic_name,
        "is_open_topic": task_topic.is_open_topic,
        "invite_link": invite_link,
        "is_active": task_topic.is_active
    }
