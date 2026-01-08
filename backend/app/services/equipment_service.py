"""
Сервис для работы с оборудованием
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.models.equipment import Equipment, EquipmentRequest, EquipmentStatus, EquipmentRequestStatus, EquipmentCategory


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
        
        Учитывает количество экземпляров: если оборудование имеет quantity > 1,
        проверяет, сколько экземпляров уже забронировано на эти даты
        """
        from app.models.equipment import EquipmentCategory
        
        # Получаем всё оборудование с нужным статусом и категорией
        query = select(Equipment).where(
            Equipment.status == EquipmentStatus.AVAILABLE
        )
        
        if category:
            # Поддерживаем как строку, так и enum
            try:
                category_enum = EquipmentCategory(category)
                query = query.where(Equipment.category == category_enum)
            except ValueError:
                # Если не удалось распарсить как enum, используем строку
                query = query.where(Equipment.category == category)
        
        all_equipment_result = await db.execute(query)
        all_equipment = list(all_equipment_result.scalars().all())
        
        # Для каждого оборудования считаем, сколько экземпляров забронировано на эти даты
        available_equipment = []
        
        for equipment in all_equipment:
            # Находим количество забронированных экземпляров на эти даты
            booked_count_query = select(func.count(EquipmentRequest.id)).where(
                and_(
                    EquipmentRequest.equipment_id == equipment.id,
                    EquipmentRequest.status.in_([
                        EquipmentRequestStatus.PENDING,
                        EquipmentRequestStatus.APPROVED,
                        EquipmentRequestStatus.ACTIVE
                    ]),
                    # Пересечение дат
                    EquipmentRequest.start_date <= end_date,
                    EquipmentRequest.end_date >= start_date
                )
            )
            
            booked_count_result = await db.execute(booked_count_query)
            booked_count = booked_count_result.scalar_one() or 0
            
            # Если есть свободные экземпляры, добавляем оборудование в список
            if booked_count < equipment.quantity:
                available_equipment.append(equipment)
        
        return available_equipment
    
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
    async def get_all_requests(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[EquipmentRequestStatus] = None,
        user_id: Optional[UUID] = None
    ) -> tuple[List[EquipmentRequest], int]:
        """Получить все заявки на оборудование (для координаторов)"""
        query = select(EquipmentRequest)
        count_query = select(func.count(EquipmentRequest.id))
        
        conditions = []
        if status:
            conditions.append(EquipmentRequest.status == status)
        if user_id:
            conditions.append(EquipmentRequest.user_id == user_id)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        query = query.order_by(EquipmentRequest.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        requests = result.scalars().all()
        
        return list(requests), total
    
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
    
    @staticmethod
    async def create_equipment(
        db: AsyncSession,
        name: str,
        category: EquipmentCategory,
        quantity: int = 1,
        specs: Optional[dict] = None,
        status: EquipmentStatus = EquipmentStatus.AVAILABLE
    ) -> Equipment:
        """Создать новое оборудование"""
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        
        equipment = Equipment(
            name=name,
            category=category,
            quantity=quantity,
            specs=specs,
            status=status
        )
        
        db.add(equipment)
        await db.commit()
        await db.refresh(equipment)
        
        return equipment
    
    @staticmethod
    async def update_equipment(
        db: AsyncSession,
        equipment_id: UUID,
        name: Optional[str] = None,
        category: Optional[EquipmentCategory] = None,
        quantity: Optional[int] = None,
        specs: Optional[dict] = None,
        status: Optional[EquipmentStatus] = None
    ) -> Optional[Equipment]:
        """Обновить оборудование"""
        equipment = await EquipmentService.get_equipment_by_id(db, equipment_id)
        if not equipment:
            return None
        
        if name is not None:
            equipment.name = name
        if category is not None:
            equipment.category = category
        if quantity is not None:
            if quantity < 1:
                raise ValueError("Quantity must be at least 1")
            equipment.quantity = quantity
        if specs is not None:
            equipment.specs = specs
        if status is not None:
            equipment.status = status
        
        await db.commit()
        await db.refresh(equipment)
        
        return equipment
    
    @staticmethod
    async def delete_equipment(
        db: AsyncSession,
        equipment_id: UUID
    ) -> bool:
        """Удалить оборудование (только если нет активных заявок)"""
        equipment = await EquipmentService.get_equipment_by_id(db, equipment_id)
        if not equipment:
            return False
        
        # Проверяем, есть ли активные заявки
        active_requests_query = select(func.count(EquipmentRequest.id)).where(
            and_(
                EquipmentRequest.equipment_id == equipment_id,
                EquipmentRequest.status.in_([
                    EquipmentRequestStatus.PENDING,
                    EquipmentRequestStatus.APPROVED,
                    EquipmentRequestStatus.ACTIVE
                ])
            )
        )
        
        active_requests_result = await db.execute(active_requests_query)
        active_requests_count = active_requests_result.scalar_one() or 0
        
        if active_requests_count > 0:
            raise ValueError(f"Cannot delete equipment with {active_requests_count} active request(s)")
        
        await db.delete(equipment)
        await db.commit()
        
        return True
