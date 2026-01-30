"""
Сервис для работы с оборудованием
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, cast, String
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
        """Получить список оборудования с информацией о доступности"""
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
        equipment_list = list(result.scalars().all())
        
        # Подгружаем информацию о занятости
        if equipment_list:
            equipment_ids = [eq.id for eq in equipment_list]
            today = date.today()
            
            # Запрос активных бронирований
            requests_query = select(EquipmentRequest).where(
                and_(
                    EquipmentRequest.equipment_id.in_(equipment_ids),
                    cast(EquipmentRequest.status, String).in_([
                        EquipmentRequestStatus.APPROVED.value,
                        EquipmentRequestStatus.ACTIVE.value
                    ]),
                    EquipmentRequest.end_date >= today
                )
            ).order_by(EquipmentRequest.end_date)
            
            requests_result = await db.execute(requests_query)
            active_requests = requests_result.scalars().all()
            
            # Группируем по оборудованию
            requests_by_eq = {}
            for req in active_requests:
                if req.equipment_id not in requests_by_eq:
                    requests_by_eq[req.equipment_id] = []
                requests_by_eq[req.equipment_id].append(req)
            
            # Вычисляем доступность для каждого элемента
            for eq in equipment_list:
                eq_requests = requests_by_eq.get(eq.id, [])
                booked_count = 0
                
                # Считаем сколько экземпляров занято ПРЯМО СЕЙЧАС (или в будущем пересекаются? 
                # Для простоты считаем активные заявки, которые перекрывают "сегодня" и будущее.
                # Но правильно считать пересечения. Если заявка на след. неделю, то сейчас свободно.
                # Пока упростим: считаем "занятыми" те, что активны сейчас.
                
                # Точнее: нас интересует next_available_date если ВСЕ заняты.
                # Если хоть один свободен сейчас - дата не нужна.
                
                # Проверяем занятость на СЕГОДНЯ
                currently_booked = [
                    r for r in eq_requests 
                    if r.start_date <= today <= r.end_date
                ]
                booked_count = len(currently_booked)
                
                # Динамически добавляем атрибуты к объекту (Pydantic схема их подхватит)
                setattr(eq, 'booked_count', booked_count)
                setattr(eq, 'available_count', max(0, eq.quantity - booked_count))
                
                if booked_count >= eq.quantity:
                    # Всё занято. Ищем, когда освободится ближайший слот.
                    # Сортируем текущие брони по дате окончания
                    currently_booked.sort(key=lambda r: r.end_date)
                    # Ближайшая дата освобождения = end_date самой ранней брони + 1 день
                    # (предполагаем, что следующая бронь не начинается сразу же... это сложно)
                    # Для MVP берем просто минимальную дату окончания текущих броней
                    if currently_booked:
                        setattr(eq, 'next_available_date', currently_booked[0].end_date)
                else:
                    setattr(eq, 'next_available_date', None)

        return equipment_list, total
    
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
                    cast(EquipmentRequest.status, String).in_([
                        EquipmentRequestStatus.PENDING.value,
                        EquipmentRequestStatus.APPROVED.value,
                        EquipmentRequestStatus.ACTIVE.value
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
            status=EquipmentRequestStatus.PENDING.value  # .value для PostgreSQL ENUM
        )
        
        db.add(request)
        await db.commit()
        await db.refresh(request)
        
        # Синхронизируем заявку с Google Sheets (в фоне)
        try:
            from app.services.google_service import GoogleService
            from app.services.equipment_sheets_sync import EquipmentSheetsSync
            from app.models.user import User
            
            # Загружаем пользователя и оборудование
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one()
            
            equipment_result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
            equipment = equipment_result.scalar_one()
            
            # Синхронизируем в фоне
            async def sync_request():
                try:
                    google_service = GoogleService()
                    sync_service = EquipmentSheetsSync(google_service)
                    await sync_service.log_equipment_request(db, request, equipment, user)
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Не удалось синхронизировать заявку с Sheets: {e}")
            
            import asyncio
            asyncio.create_task(sync_request())
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Ошибка запуска синхронизации заявки: {e}")
        
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
        
        if request.status != EquipmentRequestStatus.PENDING.value:
            raise ValueError("Request is not pending")
        
        # Проверяем, что оборудование всё ещё доступно
        available = await EquipmentService.get_available_equipment(
            db, request.start_date, request.end_date
        )
        available_ids = [eq.id for eq in available]
        
        if request.equipment_id not in available_ids:
            raise ValueError("Equipment is no longer available")
        
        old_status = request.status
        request.status = EquipmentRequestStatus.APPROVED.value
        await db.commit()
        await db.refresh(request)
        
        # Загружаем связанные данные для синхронизации и уведомлений
        from app.models.user import User
        from app.models.equipment import Equipment
        
        user_result = await db.execute(select(User).where(User.id == request.user_id))
        user = user_result.scalar_one()
        
        equipment_result = await db.execute(select(Equipment).where(Equipment.id == request.equipment_id))
        equipment = equipment_result.scalar_one()
        
        # Синхронизируем статус с Google Sheets и отправляем уведомления (в фоне)
        async def sync_and_notify():
            try:
                from app.services.google_service import GoogleService
                from app.services.equipment_sheets_sync import EquipmentSheetsSync
                from app.services.equipment_notifications import EquipmentNotifications
                
                google_service = GoogleService()
                sync_service = EquipmentSheetsSync(google_service)
                
                # Синхронизируем статус с Sheets
                await sync_service.update_request_status(
                    db, request, old_status, EquipmentRequestStatus.APPROVED, equipment, user
                )
                
                # Отправляем уведомление об одобрении
                notifications = EquipmentNotifications()
                await notifications.send_status_change_notifications(
                    db=db,
                    status_changes=[{
                        'request_id': request.id,
                        'old_status': old_status.value if old_status else EquipmentRequestStatus.PENDING.value,
                        'new_status': EquipmentRequestStatus.APPROVED.value,
                        'user_id': user.id
                    }],
                    bot=None  # TODO: Передать bot instance если доступен
                )
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Не удалось синхронизировать статус заявки или отправить уведомление: {e}")
        
        import asyncio
        asyncio.create_task(sync_and_notify())
        
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
        
        if request.status != EquipmentRequestStatus.PENDING.value:
            raise ValueError("Request is not pending")
        
        old_status = request.status
        request.status = EquipmentRequestStatus.REJECTED.value
        request.rejection_reason = reason
        await db.commit()
        await db.refresh(request)
        
        # Загружаем связанные данные для синхронизации и уведомлений
        from app.models.user import User
        from app.models.equipment import Equipment
        
        user_result = await db.execute(select(User).where(User.id == request.user_id))
        user = user_result.scalar_one()
        
        equipment_result = await db.execute(select(Equipment).where(Equipment.id == request.equipment_id))
        equipment = equipment_result.scalar_one()
        
        # Синхронизируем статус с Google Sheets и отправляем уведомления (в фоне)
        async def sync_and_notify():
            try:
                from app.services.google_service import GoogleService
                from app.services.equipment_sheets_sync import EquipmentSheetsSync
                from app.services.equipment_notifications import EquipmentNotifications
                
                google_service = GoogleService()
                sync_service = EquipmentSheetsSync(google_service)
                
                # Синхронизируем статус с Sheets
                await sync_service.update_request_status(
                    request, equipment, user, EquipmentRequestStatus.REJECTED
                )
                
                # Отправляем уведомление об отклонении
                notifications = EquipmentNotifications()
                await notifications.send_status_change_notifications(
                    db=db,
                    status_changes=[{
                        'request_id': request.id,
                        'old_status': old_status.value if old_status else EquipmentRequestStatus.PENDING.value,
                        'new_status': EquipmentRequestStatus.REJECTED.value,
                        'user_id': user.id,
                        'rejection_reason': reason
                    }],
                    bot=None  # TODO: Передать bot instance если доступен
                )
                
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Не удалось синхронизировать статус заявки или отправить уведомление: {e}")
        
        import asyncio
        asyncio.create_task(sync_and_notify())
        
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
                cast(EquipmentRequest.status, String).in_([
                    EquipmentRequestStatus.PENDING.value,
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value
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
