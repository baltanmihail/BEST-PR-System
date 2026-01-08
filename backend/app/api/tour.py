"""
API endpoints для интерактивного гайда
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.user import User
from app.utils.permissions import get_current_user
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tour", tags=["tour"])


class TourCompleteRequest(BaseModel):
    """Запрос на завершение гайда"""
    pass


@router.get("/status", response_model=dict)
async def get_tour_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить статус прохождения гайда
    
    Возвращает информацию о том, прошел ли пользователь гайд
    """
    return {
        "tour_completed": current_user.tour_completed or False,
        "tour_completed_at": current_user.tour_completed_at.isoformat() if current_user.tour_completed_at else None
    }


@router.post("/complete", response_model=dict)
async def complete_tour(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Отметить гайд как пройденный
    
    Устанавливает флаг tour_completed в True и сохраняет время завершения
    """
    if current_user.tour_completed:
        return {
            "message": "Tour already completed",
            "tour_completed": True,
            "tour_completed_at": current_user.tour_completed_at.isoformat() if current_user.tour_completed_at else None
        }
    
    current_user.tour_completed = True
    current_user.tour_completed_at = datetime.now(timezone.utc)
    
    try:
        await db.commit()
        await db.refresh(current_user)
        
        logger.info(f"User {current_user.id} completed the tour")
        
        return {
            "message": "Tour marked as completed",
            "tour_completed": True,
            "tour_completed_at": current_user.tour_completed_at.isoformat()
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error completing tour for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete tour"
        )


@router.post("/reset", response_model=dict)
async def reset_tour(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Сбросить статус прохождения гайда
    
    Позволяет пользователю пройти гайд заново
    """
    current_user.tour_completed = False
    current_user.tour_completed_at = None
    
    try:
        await db.commit()
        await db.refresh(current_user)
        
        logger.info(f"User {current_user.id} reset the tour")
        
        return {
            "message": "Tour status reset",
            "tour_completed": False
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error resetting tour for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset tour"
        )
