"""
API endpoints для ИИ-помощника координаторов
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.task_suggestion import TaskSuggestion
from app.services.ai_service import AIService
from app.utils.permissions import require_coordinator

router = APIRouter(prefix="/ai", tags=["ai"])


class AnalyzeRequest(BaseModel):
    """Запрос на анализ"""
    content: str
    type: str  # concept, idea, script, text
    title: Optional[str] = None


@router.post("/analyze", response_model=dict)
async def analyze_content(
    request: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Анализировать контент (концепт, идею, сценарий, текст)
    
    Доступно только координаторам и VP4PR
    """
    analysis = await AIService.analyze_suggestion(
        suggestion_type=request.type,
        content=request.content,
        title=request.title
    )
    
    return {
        "analysis": analysis,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/suggestions/{suggestion_id}/analyze", response_model=dict)
async def analyze_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Анализировать предложение по ID и сохранить результат
    
    Доступно только координаторам и VP4PR
    """
    query = select(TaskSuggestion).where(TaskSuggestion.id == suggestion_id)
    result = await db.execute(query)
    suggestion = result.scalar_one_or_none()
    
    if not suggestion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found"
        )
    
    # Анализируем предложение
    analysis = await AIService.analyze_suggestion(
        suggestion_type=suggestion.type.value,
        content=suggestion.content,
        title=suggestion.title
    )
    
    # Сохраняем анализ в предложение
    suggestion.ai_analysis = analysis
    await db.commit()
    await db.refresh(suggestion)
    
    return {
        "suggestion_id": str(suggestion_id),
        "analysis": analysis,
        "message": "Анализ сохранён в предложение"
    }


@router.post("/analyze-post", response_model=dict)
async def analyze_post_text(
    text: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Анализировать текст поста для SMM
    
    Доступно только координаторам и VP4PR
    """
    analysis = await AIService.analyze_post_text(text)
    
    return {
        "analysis": analysis,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/structure", response_model=dict)
async def structure_content(
    content: str,
    content_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Структурировать контент (разбить на части, выделить ключевые моменты)
    
    Доступно только координаторам и VP4PR
    """
    structure = await AIService.structure_content(content, content_type)
    
    return {
        "structure": structure,
        "structured_at": datetime.now(timezone.utc).isoformat()
    }
