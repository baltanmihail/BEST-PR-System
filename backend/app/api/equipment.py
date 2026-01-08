"""
API endpoints для оборудования
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from datetime import date

from app.database import get_db
from app.models.user import User
from app.models.equipment import EquipmentStatus, EquipmentRequestStatus
from app.schemas.equipment import (
    EquipmentResponse, EquipmentCreate, EquipmentUpdate,
    EquipmentRequestResponse, EquipmentRequestCreate, EquipmentRequestUpdate
)
from app.services.equipment_service import EquipmentService
from app.utils.permissions import get_current_user, require_coordinator

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
