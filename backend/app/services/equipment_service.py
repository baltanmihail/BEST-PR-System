"""
Сервис для работы с оборудованием
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.models.equipment import Equipment, EquipmentRequest, EquipmentStatus, EquipmentRequestStatus


class EquipmentService:
    """Сервис для работы с оборудованием"""
    
    @staticmethod
    async def get_equipment(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        category: Optional[str] = None,
        status: Optional[EquipmentStatus] = None
    ) -> tuple[List[Equipment], int]:
        """Получить список оборудования"""
        query = select(Equipment)
        count_query = select(func.count(Equipment.id))
        
        conditions = []
        if category:
            conditions.append(Equipment.category == category)
        if status:
            conditions.append(Equipment.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.order_by(Equipment.name).offset(skip).limit(limit)
        result = await db.execute(query)
        equipment = result.scalars().all()
        
        return list(equipment), total
    
    @staticmethod
    async def get_equipment_by_id(
        db: AsyncSession,
        equipment_id: UUID
    ) -> Optional[Equipment]:
        """Получить оборудование по ID"""
        query = select(Equipment).where(Equipment.id == equipment_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_available_equipment(
        db: AsyncSession,
        start_date: date,
        end_date: date,
        category: Optional[str] = None
    ) -> List[Equipment]:
        """
        Получить доступное оборудование на указанные даты
        
        Исключает оборудование, которое уже забронировано на эти даты
        """
        # Находим оборудование, которое забронировано на эти даты
        booked_query = select(EquipmentRequest.equipment_id).where(
            and_(
                EquipmentRequest.status.in_([
                    EquipmentRequestStatus.PENDING,
                    EquipmentRequestStatus.APPROVED,
                    EquipmentRequestStatus.ACTIVE
                ]),
                or_(
                    # Пересечение дат
                    and_(
                        EquipmentRequest.start_date <= end_date,
                        EquipmentRequest.end_date >= start_date
                    )
                )
            )
        )
        
        booked_result = await db.execute(booked_query)
        booked_ids = [row[0] for row in booked_result.all()]
        
        # Получаем доступное оборудование
        query = select(Equipment).where(
            Equipment.status == EquipmentStatus.AVAILABLE
        )
        
        if booked_ids:
            query = query.where(~Equipment.id.in_(booked_ids))
        
        if category:
            query = query.where(Equipment.category == category)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def create_equipment_request(
        db: AsyncSession,
        equipment_id: UUID,
        user_id: UUID,
        start_date: date,
        end_date: date,
        task_id: Optional[UUID] = None
    ) -> EquipmentRequest:
        """Создать заявку на оборудование"""
        # Проверяем доступность оборудования
        available = await EquipmentService.get_available_equipment(
            db, start_date, end_date
        )
        available_ids = [eq.id for eq in available]
        
        if equipment_id not in available_ids:
            raise ValueError("Equipment is not available for these dates")
        
        request = EquipmentRequest(
            equipment_id=equipment_id,
            user_id=user_id,
            task_id=task_id,
            start_date=start_date,
            end_date=end_date,
            status=EquipmentRequestStatus.PENDING
        )
        
        db.add(request)
        await db.commit()
        await db.refresh(request)
        
        return request
    
    @staticmethod
    async def get_user_requests(
        db: AsyncSession,
        user_id: UUID
    ) -> List[EquipmentRequest]:
        """Получить заявки пользователя"""
        query = select(EquipmentRequest).where(
            EquipmentRequest.user_id == user_id
        ).order_by(EquipmentRequest.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_request_by_id(
        db: AsyncSession,
        request_id: UUID
    ) -> Optional[EquipmentRequest]:
        """Получить заявку по ID"""
        query = select(EquipmentRequest).where(EquipmentRequest.id == request_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def approve_request(
        db: AsyncSession,
        request_id: UUID
    ) -> Optional[EquipmentRequest]:
        """Одобрить заявку на оборудование"""
        request = await EquipmentService.get_request_by_id(db, request_id)
        if not request:
            return None
        
        if request.status != EquipmentRequestStatus.PENDING:
            raise ValueError("Request is not pending")
        
        # Проверяем, что оборудование всё ещё доступно
        available = await EquipmentService.get_available_equipment(
            db, request.start_date, request.end_date
        )
        available_ids = [eq.id for eq in available]
        
        if request.equipment_id not in available_ids:
            raise ValueError("Equipment is no longer available")
        
        request.status = EquipmentRequestStatus.APPROVED
        await db.commit()
        await db.refresh(request)
        
        return request
    
    @staticmethod
    async def reject_request(
        db: AsyncSession,
        request_id: UUID,
        reason: str
    ) -> Optional[EquipmentRequest]:
        """Отклонить заявку на оборудование"""
        request = await EquipmentService.get_request_by_id(db, request_id)
        if not request:
            return None
        
        if request.status != EquipmentRequestStatus.PENDING:
            raise ValueError("Request is not pending")
        
        request.status = EquipmentRequestStatus.REJECTED
        request.rejection_reason = reason
        await db.commit()
        await db.refresh(request)
        
        return request
