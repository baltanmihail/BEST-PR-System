"""
API endpoints для онбординга новых пользователей
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import logging

from app.database import get_db
from app.models.onboarding import OnboardingResponse, OnboardingReminder
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingResponseRequest(BaseModel):
    """Запрос на сохранение ответов онбординга"""
    telegram_id: str
    experience: Optional[str] = None
    goals: Optional[str] = None
    motivation: Optional[str] = None
    from_website: bool = False
    from_qr: bool = False
    website_url: Optional[str] = None


@router.post("/response", response_model=dict)
async def save_onboarding_response(
    request: OnboardingResponseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Сохранить ответы пользователя на вопросы онбординга
    """
    # Проверяем, есть ли уже ответы от этого пользователя
    result = await db.execute(
        select(OnboardingResponse).where(
            OnboardingResponse.telegram_id == request.telegram_id
        )
    )
    existing_response = result.scalar_one_or_none()
    
    if existing_response:
        # Обновляем существующий ответ
        if request.experience:
            existing_response.experience = request.experience
        if request.goals:
            existing_response.goals = request.goals
        if request.motivation:
            existing_response.motivation = request.motivation
        if request.from_website:
            existing_response.from_website = request.from_website
        if request.from_qr:
            existing_response.from_qr = request.from_qr
        if request.website_url:
            existing_response.website_url = request.website_url
        
        await db.commit()
        await db.refresh(existing_response)
        
        logger.info(f"Updated onboarding response for telegram_id={request.telegram_id}")
        
        return {
            "success": True,
            "message": "Ответы обновлены",
            "response_id": str(existing_response.id)
        }
    else:
        # Создаём новый ответ
        new_response = OnboardingResponse(
            telegram_id=request.telegram_id,
            experience=request.experience,
            goals=request.goals,
            motivation=request.motivation,
            from_website=request.from_website,
            from_qr=request.from_qr,
            website_url=request.website_url
        )
        
        db.add(new_response)
        await db.commit()
        await db.refresh(new_response)
        
        logger.info(f"Created onboarding response for telegram_id={request.telegram_id}")
        
        return {
            "success": True,
            "message": "Ответы сохранены",
            "response_id": str(new_response.id)
        }


@router.get("/response/{telegram_id}", response_model=dict)
async def get_onboarding_response(
    telegram_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить ответы пользователя на вопросы онбординга
    """
    result = await db.execute(
        select(OnboardingResponse).where(
            OnboardingResponse.telegram_id == telegram_id
        )
    )
    response = result.scalar_one_or_none()
    
    if not response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Onboarding response not found"
        )
    
    return {
        "telegram_id": response.telegram_id,
        "experience": response.experience,
        "goals": response.goals,
        "motivation": response.motivation,
        "from_website": response.from_website,
        "from_qr": response.from_qr,
        "created_at": response.created_at.isoformat() if response.created_at else None
    }


class TrackTimeRequest(BaseModel):
    """Запрос на отслеживание времени на сайте"""
    telegram_id: str
    time_seconds: int  # Время в секундах, проведённое на сайте


@router.post("/track-time", response_model=dict)
async def track_time_on_site(
    request: TrackTimeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Отслеживание времени, проведённого пользователем на сайте
    """
    # Находим или создаём запись о напоминаниях
    result = await db.execute(
        select(OnboardingReminder).where(
            OnboardingReminder.telegram_id == request.telegram_id
        )
    )
    reminder = result.scalar_one_or_none()
    
    now = datetime.now(timezone.utc)
    
    if not reminder:
        # Создаём новую запись
        reminder = OnboardingReminder(
            telegram_id=request.telegram_id,
            first_visit_at=now,
            last_visit_at=now,
            time_on_site=str(request.time_seconds)
        )
        db.add(reminder)
    else:
        # Обновляем существующую запись
        current_time = int(reminder.time_on_site or "0")
        reminder.time_on_site = str(current_time + request.time_seconds)
        reminder.last_visit_at = now  # Обновляем время последнего визита
    
    await db.commit()
    await db.refresh(reminder)
    
    # Проверяем, нужно ли отправить напоминание
    # Если пользователь провёл достаточно времени на сайте (например, 2-3 минуты)
    total_time = int(reminder.time_on_site or "0")
    should_send_reminder = total_time >= 120 and not reminder.registered  # 2 минуты
    
    return {
        "success": True,
        "total_time_seconds": total_time,
        "should_send_reminder": should_send_reminder,
        "reminder_id": str(reminder.id)
    }


@router.get("/reminder/{telegram_id}", response_model=dict)
async def get_reminder_info(
    telegram_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о напоминаниях для пользователя
    """
    result = await db.execute(
        select(OnboardingReminder).where(
            OnboardingReminder.telegram_id == telegram_id
        )
    )
    reminder = result.scalar_one_or_none()
    
    if not reminder:
        return {
            "telegram_id": telegram_id,
            "exists": False
        }
    
    return {
        "telegram_id": reminder.telegram_id,
        "exists": True,
        "first_visit_at": reminder.first_visit_at.isoformat() if reminder.first_visit_at else None,
        "last_visit_at": reminder.last_visit_at.isoformat() if reminder.last_visit_at else None,
        "time_on_site": int(reminder.time_on_site or "0"),
        "reminder_count": int(reminder.reminder_count or "0"),
        "responded": reminder.responded,
        "registered": reminder.registered
    }


@router.post("/reminder/{telegram_id}/mark-sent", response_model=dict)
async def mark_reminder_sent(
    telegram_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Отметить, что напоминание было отправлено
    """
    result = await db.execute(
        select(OnboardingReminder).where(
            OnboardingReminder.telegram_id == telegram_id
        )
    )
    reminder = result.scalar_one_or_none()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Увеличиваем счётчик напоминаний
    current_count = int(reminder.reminder_count or "0")
    reminder.reminder_count = str(current_count + 1)
    reminder.last_reminder_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(reminder)
    
    return {
        "success": True,
        "reminder_count": int(reminder.reminder_count)
    }


@router.get("/reminders/pending", response_model=dict)
async def get_pending_reminders(
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список пользователей, которым нужно отправить напоминание
    Алгоритм Duolingo-style:
    - Первое напоминание: через 2-3 минуты после первого визита
    - Второе напоминание: через 1 день
    - Третье напоминание: через 3 дня
    - И так далее с увеличивающимися интервалами
    """
    now = datetime.now(timezone.utc)
    
    # Получаем всех незарегистрированных пользователей
    result = await db.execute(
        select(OnboardingReminder).where(
            OnboardingReminder.registered == False
        )
    )
    reminders = result.scalars().all()
    
    pending = []
    
    for reminder in reminders:
        if not reminder.first_visit_at:
            continue
        
        time_since_first_visit = now - reminder.first_visit_at
        reminder_count = int(reminder.reminder_count or "0")
        time_on_site = int(reminder.time_on_site or "0")
        
        # Определяем интервалы для напоминаний (максимум 2-3)
        intervals = [
            timedelta(minutes=3),  # Первое напоминание через 3 минуты
            timedelta(days=1),     # Второе через 1 день
            timedelta(days=3),     # Третье через 3 дня (только если пользователь заходил на сайт несколько раз)
        ]
        
        # Максимум 2-3 напоминания
        max_reminders = 2
        # Третье напоминание только если пользователь заходил на сайт несколько раз
        if reminder.last_visit_at and reminder.last_visit_at != reminder.first_visit_at:
            max_reminders = 3  # Пользователь заходил не один раз
        
        # Проверяем, нужно ли отправить напоминание
        should_send = False
        
        if reminder_count < max_reminders and reminder_count < len(intervals):
            # Проверяем, прошло ли достаточно времени с последнего напоминания или первого визита
            if reminder_count == 0:
                # Первое напоминание - через 3 минуты после первого визита, если провёл достаточно времени на сайте
                if time_since_first_visit >= intervals[0] and time_on_site >= 120:
                    should_send = True
            else:
                # Последующие напоминания - через определённые интервалы
                if reminder.last_reminder_at:
                    time_since_last_reminder = now - reminder.last_reminder_at
                    if time_since_last_reminder >= intervals[reminder_count]:
                        should_send = True
        
        if should_send:
            # Получаем ответы онбординга для персонализации
            response_result = await db.execute(
                select(OnboardingResponse).where(
                    OnboardingResponse.telegram_id == reminder.telegram_id
                )
            )
            onboarding_response = response_result.scalar_one_or_none()
            
            pending.append({
                "telegram_id": reminder.telegram_id,
                "reminder_count": reminder_count,
                "time_on_site": time_on_site,
                "first_visit_at": reminder.first_visit_at.isoformat(),
                "onboarding_data": {
                    "experience": onboarding_response.experience if onboarding_response else None,
                    "goals": onboarding_response.goals if onboarding_response else None,
                    "motivation": onboarding_response.motivation if onboarding_response else None,
                } if onboarding_response else None
            })
    
    return {
        "pending_count": len(pending),
        "pending": pending
    }


@router.post("/reminders/process", response_model=dict)
async def process_reminders(
    db: AsyncSession = Depends(get_db)
):
    """
    Обработать все ожидающие напоминания и отправить их
    Этот endpoint можно вызывать периодически (например, через cron или scheduler)
    """
    from app.services.onboarding_service import OnboardingService
    
    sent_count = await OnboardingService.process_pending_reminders(db)
    
    return {
        "success": True,
        "sent_count": sent_count,
        "message": f"Processed {sent_count} reminders"
    }
