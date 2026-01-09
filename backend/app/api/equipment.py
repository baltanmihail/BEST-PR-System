"""
API endpoints для оборудования
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import timedelta
from uuid import UUID
from datetime import date, timedelta

from app.database import get_db
from app.models.user import User
from app.models.equipment import EquipmentStatus, EquipmentRequestStatus
from app.schemas.equipment import (
    EquipmentResponse, EquipmentCreate, EquipmentUpdate,
    EquipmentRequestResponse, EquipmentRequestCreate, EquipmentRequestUpdate
)
from app.services.equipment_service import EquipmentService
from app.utils.permissions import get_current_user, require_coordinator
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=dict)
async def get_equipment(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    status: Optional[EquipmentStatus] = Query(None, description="Фильтр по статусу"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список оборудования
    
    Доступно всем авторизованным пользователям
    """
    equipment, total = await EquipmentService.get_equipment(
        db=db,
        skip=skip,
        limit=limit,
        category=category,
        status=status
    )
    
    return {
        "items": [EquipmentResponse.model_validate(eq) for eq in equipment],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.get("/{equipment_id}", response_model=EquipmentResponse)
async def get_equipment_by_id(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить оборудование по ID
    
    Доступно всем авторизованным пользователям
    """
    equipment = await EquipmentService.get_equipment_by_id(db, equipment_id)
    
    if not equipment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found"
        )
    
    return EquipmentResponse.model_validate(equipment)


@router.get("/available", response_model=List[EquipmentResponse])
async def get_available_equipment(
    start_date: date = Query(..., description="Дата начала"),
    end_date: date = Query(..., description="Дата окончания"),
    category: Optional[str] = Query(None, description="Фильтр по категории"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить доступное оборудование на указанные даты
    
    Учитывает количество экземпляров: если оборудование имеет quantity > 1,
    показывает его только если есть свободные экземпляры.
    
    Доступно всем авторизованным пользователям
    """
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date"
        )
    
    equipment = await EquipmentService.get_available_equipment(
        db=db,
        start_date=start_date,
        end_date=end_date,
        category=category
    )
    
    return [EquipmentResponse.model_validate(eq) for eq in equipment]


@router.get("/requests", response_model=List[EquipmentRequestResponse])
async def get_my_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить мои заявки на оборудование
    
    Доступно всем авторизованным пользователям
    """
    requests = await EquipmentService.get_user_requests(db, current_user.id)
    return [EquipmentRequestResponse.model_validate(req) for req in requests]


@router.get("/requests/all", response_model=dict)
async def get_all_requests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status: Optional[EquipmentRequestStatus] = Query(None, description="Фильтр по статусу"),
    user_id: Optional[UUID] = Query(None, description="Фильтр по пользователю"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Получить все заявки на оборудование (для координаторов)
    
    Доступно только координаторам и VP4PR
    """
    requests, total = await EquipmentService.get_all_requests(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        user_id=user_id
    )
    
    return {
        "items": [EquipmentRequestResponse.model_validate(req) for req in requests],
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.post("/requests", response_model=EquipmentRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_equipment_request(
    request_data: EquipmentRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создать заявку на оборудование
    
    Доступно всем авторизованным пользователям
    """
    if request_data.end_date < request_data.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date"
        )
    
    try:
        request = await EquipmentService.create_equipment_request(
            db=db,
            equipment_id=request_data.equipment_id,
            user_id=current_user.id,
            start_date=request_data.start_date,
            end_date=request_data.end_date,
            task_id=request_data.task_id
        )
        return EquipmentRequestResponse.model_validate(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.patch("/requests/{request_id}", response_model=EquipmentRequestResponse)
async def update_equipment_request(
    request_id: UUID,
    request_data: EquipmentRequestUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить заявку на оборудование
    
    Доступно создателю заявки или координаторам
    """
    request = await EquipmentService.get_request_by_id(db, request_id)
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found"
        )
    
    # Проверка прав
    from app.models.user import UserRole
    is_coordinator = current_user.role in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]
    
    if request.user_id != current_user.id and not is_coordinator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this request"
        )
    
    # Обновляем поля
    if request_data.start_date:
        request.start_date = request_data.start_date
    if request_data.end_date:
        request.end_date = request_data.end_date
    if request_data.status:
        request.status = request_data.status
    
    await db.commit()
    await db.refresh(request)
    
    return EquipmentRequestResponse.model_validate(request)


@router.post("/requests/{request_id}/approve", response_model=EquipmentRequestResponse)
async def approve_equipment_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Одобрить заявку на оборудование
    
    Доступно только координаторам
    """
    try:
        request = await EquipmentService.approve_request(db, request_id)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found"
            )
        return EquipmentRequestResponse.model_validate(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/requests/{request_id}/reject", response_model=EquipmentRequestResponse)
async def reject_equipment_request(
    request_id: UUID,
    reason: str = Query(..., description="Причина отклонения"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Отклонить заявку на оборудование
    
    Доступно только координаторам
    """
    try:
        request = await EquipmentService.reject_request(db, request_id, reason)
        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Request not found"
            )
        return EquipmentRequestResponse.model_validate(request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/sync/from-sheets")
async def sync_equipment_from_sheets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Синхронизировать оборудование из Google Sheets в БД
    
    Читает список оборудования из листа "Вся оборудка" и создаёт/обновляет записи в БД.
    
    Доступно только координаторам и VP4PR
    """
    try:
        from app.services.google_service import GoogleService
        from app.services.equipment_sheets_sync import EquipmentSheetsSync
        
        google_service = GoogleService()
        sync_service = EquipmentSheetsSync(google_service)
        
        # Запускаем синхронизацию в фоне
        async def sync_async():
            try:
                result = await sync_service.sync_equipment_from_sheets(db)
                logger.info(f"✅ Синхронизация оборудования из Sheets завершена: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка синхронизации оборудования из Sheets: {e}", exc_info=True)
                raise
        
        import asyncio
        asyncio.create_task(sync_async())
        
        return {
            "status": "sync_started",
            "message": "Синхронизация оборудования из Google Sheets запущена",
            "note": "Синхронизация выполняется в фоне. Проверьте результаты через несколько секунд."
        }
        
    except Exception as e:
        logger.error(f"Failed to sync equipment from sheets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации оборудования из Google Sheets: {str(e)}"
        )


@router.post("/calendar/sync")
async def sync_equipment_calendar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Синхронизировать календарь занятости оборудования с Google Sheets
    
    Обновляет календарь с логикой цветов (красный/жёлтый).
    
    Доступно только координаторам и VP4PR
    """
    try:
        from app.services.google_service import GoogleService
        from app.services.equipment_calendar_sync import EquipmentCalendarSync
        
        google_service = GoogleService()
        calendar_sync = EquipmentCalendarSync(google_service)
        
        # Запускаем синхронизацию в фоне
        async def sync_async():
            try:
                result = await calendar_sync.create_or_update_calendar_sheet(db)
                logger.info(f"✅ Синхронизация календаря завершена: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка синхронизации календаря: {e}", exc_info=True)
                raise
        
        import asyncio
        asyncio.create_task(sync_async())
        
        return {
            "status": "sync_started",
            "message": "Синхронизация календаря занятости запущена",
            "note": "Синхронизация выполняется в фоне. Проверьте результаты через несколько секунд."
        }
        
    except Exception as e:
        logger.error(f"Failed to sync equipment calendar: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации календаря занятости: {str(e)}"
        )


@router.post("/statuses/sync")
async def sync_equipment_statuses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Обновить статусы оборудования по датам
    
    Автоматически обновляет статусы: На складе → Занят, съёмка предстоит → Занят, съёмка окончена → На складе
    
    Доступно только координаторам и VP4PR
    """
    try:
        from app.services.google_service import GoogleService
        from app.services.equipment_status_sync import EquipmentStatusSync
        
        google_service = GoogleService()
        status_sync = EquipmentStatusSync(google_service)
        
        result = await status_sync.update_equipment_statuses_by_date(db)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync equipment statuses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении статусов оборудования: {str(e)}"
        )


@router.post("/sync/bidirectional")
async def sync_bidirectional(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Двусторонняя синхронизация: изменения из Google Sheets → БД
    
    Отслеживает изменения статусов заявок в таблице и обновляет БД.
    
    Доступно только координаторам и VP4PR
    """
    try:
        from app.services.google_service import GoogleService
        from app.services.equipment_sync_bidirectional import EquipmentBidirectionalSync
        
        google_service = GoogleService()
        sync_service = EquipmentBidirectionalSync(google_service)
        
        result = await sync_service.sync_from_sheets(db)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync bidirectionally: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при двусторонней синхронизации: {str(e)}"
        )


@router.post("/timeline/sync")
async def sync_equipment_timeline(
    month: int = Query(..., ge=1, le=12, description="Месяц (1-12)"),
    year: int = Query(..., ge=2020, description="Год"),
    statuses: Optional[List[str]] = Query(None, description="Фильтр по статусам заявок"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Синхронизировать таймлайн занятости оборудования с Google Sheets
    
    Доступно всем авторизованным пользователям
    """
    try:
        from app.services.google_service import GoogleService
        from app.services.equipment_timeline_sync import EquipmentTimelineSyncService
        
        google_service = GoogleService()
        timeline_service = EquipmentTimelineSyncService(google_service)
        
        result = await timeline_service.sync_equipment_timeline_to_sheets_async(
            month=month,
            year=year,
            db=db,
            statuses=statuses
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to sync equipment timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации таймлайна занятости: {str(e)}"
        )


@router.get("/timeline")
async def get_equipment_timeline(
    month: int = Query(..., ge=1, le=12, description="Месяц (1-12)"),
    year: int = Query(..., ge=2020, description="Год"),
    statuses: Optional[List[str]] = Query(None, description="Фильтр по статусам заявок"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить таймлайн занятости оборудования
    
    Возвращает данные для отображения календаря занятости.
    
    Доступно всем авторизованным пользователям
    """
    try:
        from sqlalchemy import select, and_, or_
        from datetime import date, datetime
        import calendar as cal_lib
        from app.models.equipment import EquipmentRequest, EquipmentRequestStatus
        
        # Получаем данные из БД
        first_day = date(year, month, 1)
        last_day = date(year, month, cal_lib.monthrange(year, month)[1])
        
        # Получаем все заявки на оборудование в диапазоне дат
        requests_query = select(EquipmentRequest).where(
            and_(
                or_(
                    EquipmentRequest.start_date <= last_day,
                    EquipmentRequest.end_date >= first_day
                )
            )
        )
        
        # Фильтр по статусам (если указан)
        if statuses:
            try:
                status_enums = [EquipmentRequestStatus(s) for s in statuses if s in [st.value for st in EquipmentRequestStatus]]
                if status_enums:
                    requests_query = requests_query.where(EquipmentRequest.status.in_(status_enums))
            except ValueError:
                pass
        
        result = await db.execute(requests_query)
        requests = result.scalars().all()
        
        # Загружаем связанные данные
        for req in requests:
            equipment_result = await db.execute(
                select(Equipment).where(Equipment.id == req.equipment_id)
            )
            req.equipment = equipment_result.scalar_one_or_none()
            
            from app.models.user import User
            user_result = await db.execute(
                select(User).where(User.id == req.user_id)
            )
            req.user = user_result.scalar_one_or_none()
        
        # Формируем данные для календаря
        timeline_data = []
        current_date = first_day
        
        while current_date <= last_day:
            day_requests = []
            for req in requests:
                if req.start_date <= current_date <= req.end_date:
                    day_requests.append({
                        "request_id": str(req.id),
                        "equipment_name": req.equipment.name if req.equipment else "Неизвестно",
                        "equipment_id": str(req.equipment_id),
                        "user_name": req.user.full_name if req.user else "Неизвестно",
                        "status": req.status.value,
                        "is_overdue": req.end_date < date.today() and req.status not in [EquipmentRequestStatus.COMPLETED, EquipmentRequestStatus.CANCELLED]
                    })
            
            timeline_data.append({
                "date": current_date.isoformat(),
                "requests": day_requests
            })
            
            current_date += timedelta(days=1)
        
        return {
            "month": month,
            "year": year,
            "timeline": timeline_data,
            "total_requests": len(requests)
        }
        
    except Exception as e:
        logger.error(f"Failed to get equipment timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении таймлайна занятости: {str(e)}"
        )


@router.get("/{equipment_id}/booked-dates")
async def get_equipment_booked_dates(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить забронированные даты для оборудования
    
    Возвращает даты из БД и из календаря Google Sheets.
    
    Доступно всем авторизованным пользователям
    """
    try:
        # Получаем оборудование
        equipment = await EquipmentService.get_equipment_by_id(db, equipment_id)
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        # Получаем номер оборудования
        equipment_number = equipment.specs.get("number") if equipment.specs else None
        if not equipment_number:
            # Используем название как fallback
            equipment_number = equipment.name
        
        # Получаем забронированные даты из БД
        from sqlalchemy import select, and_, or_
        from app.models.equipment import EquipmentRequestStatus
        
        booked_requests_query = select(EquipmentRequest).where(
            and_(
                EquipmentRequest.equipment_id == equipment_id,
                EquipmentRequest.status.in_([
                    EquipmentRequestStatus.PENDING,
                    EquipmentRequestStatus.APPROVED,
                    EquipmentRequestStatus.ACTIVE
                ])
            )
        )
        booked_requests_result = await db.execute(booked_requests_query)
        booked_requests = booked_requests_result.scalars().all()
        
        booked_dates_from_db = set()
        for req in booked_requests:
            current_date = req.start_date
            while current_date <= req.end_date:
                booked_dates_from_db.add(current_date)
                current_date += timedelta(days=1)
        
        # Получаем забронированные даты из календаря Google Sheets
        booked_dates_from_sheets = set()
        try:
            from app.services.google_service import GoogleService
            from app.services.equipment_sheets_sync import EquipmentSheetsSync
            
            google_service = GoogleService()
            sync_service = EquipmentSheetsSync(google_service)
            booked_dates_from_sheets = await sync_service.get_booked_dates_from_calendar(
                str(equipment_number),
                use_cache=True
            )
        except Exception as e:
            logger.warning(f"Не удалось получить занятые даты из календаря: {e}")
        
        # Объединяем даты из БД и календаря
        all_booked_dates = booked_dates_from_db | booked_dates_from_sheets
        
        return {
            "equipment_id": str(equipment_id),
            "equipment_name": equipment.name,
            "booked_dates": sorted(list(all_booked_dates)),
            "booked_dates_count": len(all_booked_dates),
            "sources": {
                "database": len(booked_dates_from_db),
                "calendar": len(booked_dates_from_sheets)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get booked dates: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении занятых дат: {str(e)}"
        )


@router.post("", response_model=EquipmentResponse, status_code=status.HTTP_201_CREATED)
async def create_equipment(
    equipment_data: EquipmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать новое оборудование
    
    Доступно только координаторам и VP4PR
    """
    from app.models.equipment import EquipmentCategory
    
    # Конвертируем строку категории в enum, если нужно
    category = equipment_data.category
    if isinstance(category, str):
        try:
            category = EquipmentCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Allowed values: {[c.value for c in EquipmentCategory]}"
            )
    
    try:
        equipment = await EquipmentService.create_equipment(
            db=db,
            name=equipment_data.name,
            category=category,
            quantity=equipment_data.quantity,
            specs=equipment_data.specs
        )
        return EquipmentResponse.model_validate(equipment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{equipment_id}", response_model=EquipmentResponse)
async def update_equipment(
    equipment_id: UUID,
    equipment_data: EquipmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Обновить оборудование
    
    Доступно только координаторам и VP4PR
    """
    from app.models.equipment import EquipmentCategory
    
    update_kwargs = {}
    
    if equipment_data.name is not None:
        update_kwargs['name'] = equipment_data.name
    
    if equipment_data.category is not None:
        category = equipment_data.category
        if isinstance(category, str):
            try:
                category = EquipmentCategory(category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid category. Allowed values: {[c.value for c in EquipmentCategory]}"
                )
        update_kwargs['category'] = category
    
    if equipment_data.quantity is not None:
        update_kwargs['quantity'] = equipment_data.quantity
    
    if equipment_data.specs is not None:
        update_kwargs['specs'] = equipment_data.specs
    
    if equipment_data.status is not None:
        update_kwargs['status'] = equipment_data.status
    
    try:
        equipment = await EquipmentService.update_equipment(
            db=db,
            equipment_id=equipment_id,
            **update_kwargs
        )
        
        if not equipment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
        
        return EquipmentResponse.model_validate(equipment)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_equipment(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Удалить оборудование
    
    Доступно только координаторам и VP4PR
    Удаление возможно только если нет активных заявок
    """
    try:
        success = await EquipmentService.delete_equipment(db, equipment_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Equipment not found"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
