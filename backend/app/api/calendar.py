"""
API endpoints для календаря/таймлайна
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Literal, List
from datetime import datetime, date
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.models.task import Task, TaskStage, TaskType
from app.models.event import Event
from app.models.equipment import EquipmentRequest
from app.utils.permissions import get_current_user, OptionalUser, require_coordinator
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from dateutil.relativedelta import relativedelta
import calendar as cal_lib

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/by-role/{role}")
async def get_calendar_by_role(
    role: Literal["smm", "design", "channel", "prfr"],
    view: Literal["month", "week", "timeline", "gantt", "kanban"] = Query("month", description="Тип представления"),
    start_date: Optional[date] = Query(None, description="Начальная дата"),
    end_date: Optional[date] = Query(None, description="Конечная дата"),
    detail_level: Literal["compact", "normal", "detailed"] = Query("normal", description="Уровень детализации"),
    include_equipment: bool = Query(True, description="Включать бронирование оборудования"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Получить календарь для конкретной роли (SMM, Design, Channel, PR-FR)
    
    Это отдельный календарь, показывающий только задачи данного типа.
    В общем календаре эти задачи отображаются разными цветами.
    """
    # Преобразуем роль в TaskType
    role_to_type = {
        "smm": TaskType.SMM,
        "design": TaskType.DESIGN,
        "channel": TaskType.CHANNEL,
        "prfr": TaskType.PRFR
    }
    
    task_type = role_to_type.get(role.lower())
    if not task_type:
        return {"error": f"Invalid role: {role}. Allowed: smm, design, channel, prfr"}
    
    # Перенаправляем на основной endpoint с фильтром по типу
    return await get_calendar(
        view=view,
        start_date=start_date,
        end_date=end_date,
        task_type=task_type,
        detail_level=detail_level,
        include_equipment=include_equipment,
        db=db,
        current_user=current_user
    )


@router.post("/sync/sheets")
async def sync_calendar_to_sheets(
    month: Optional[int] = Query(None, description="Месяц для синхронизации (1-12)"),
    year: Optional[int] = Query(None, description="Год для синхронизации"),
    role: Optional[Literal["smm", "design", "channel", "prfr", "all"]] = Query("all", description="Роль для синхронизации"),
    statuses: Optional[List[str]] = Query(None, description="Фильтр по статусам задач (draft, open, assigned, in_progress, review, completed, cancelled)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Синхронизировать календарь с Google Sheets
    
    Создаёт/обновляет Google Sheets с таймлайнами:
    - Общий календарь
    - Отдельные листы для SMM, Design, Channel, PR-FR
    
    Формат: таблица по месяцам, где ячейки окрашиваются в цвета задач,
    этапов и оборудования с дедлайнами и датами.
    При клике на ячейку открывается карточка задачи.
    
    Доступно только координаторам и VP4PR
    """
    from app.models.user import UserRole
    from fastapi import HTTPException, status
    
    # Проверка прав
    if current_user.role not in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators and VP4PR can sync calendar to Google Sheets"
        )
    
    # Если месяц/год не указаны, используем текущие
    if not month:
        month = datetime.now().month
    if not year:
        year = datetime.now().year
    
    try:
        from app.services.google_service import GoogleService
        from app.services.sheets_sync import SheetsSyncService
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        
        google_service = GoogleService()
        sheets_sync = SheetsSyncService(google_service)
        executor = ThreadPoolExecutor(max_workers=5)
        
        # Определяем, какие роли синхронизировать
        roles_to_sync = ["smm", "design", "channel", "prfr"] if role == "all" else [role]
        
        # Запускаем синхронизацию асинхронно (не блокируем ответ)
        async def sync_async():
            try:
                # Используем асинхронную версию синхронизации
                result = await sheets_sync.sync_calendar_to_sheets_async(
                    month, year, roles_to_sync, db, statuses
                )
                logger.info(f"✅ Синхронизация завершена: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка синхронизации: {e}", exc_info=True)
                raise
        
        # Запускаем в фоне (не ждём завершения)
        asyncio.create_task(sync_async())
        
        return {
            "status": "sync_started",
            "message": f"Синхронизация календаря с Google Sheets запущена для {month}/{year}",
            "roles": roles_to_sync,
            "statuses": statuses,
            "month": month,
            "year": year,
            "note": "Синхронизация выполняется в фоне. Проверьте Google Sheets через несколько секунд."
        }
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync calendar to sheets: {e}", exc_info=True)
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации с Google Sheets: {str(e)}"
        )


@router.post("/sync/sheets-from-db")
async def sync_sheets_changes_from_db(
    sheet_name: Optional[str] = Query("Общий", description="Имя листа для синхронизации"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Синхронизировать изменения из Google Sheets обратно в БД
    
    Отслеживает изменения дедлайнов, статусов и этапов в таблице
    и обновляет БД при обнаружении расхождений.
    
    Доступно только координаторам и VP4PR
    """
    from app.models.user import UserRole
    from fastapi import HTTPException, status
    from app.config import settings
    
    # Проверка прав
    if current_user.role not in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators and VP4PR can sync changes from Google Sheets"
        )
    
    if not settings.GOOGLE_TIMELINE_SHEETS_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google Sheets ID not configured. Please sync calendar first."
        )
    
    try:
        from app.services.google_service import GoogleService
        from app.services.sheets_sync import SheetsSyncService
        
        google_service = GoogleService()
        sheets_sync = SheetsSyncService(google_service)
        
        # Запускаем синхронизацию в фоне
        async def sync_async():
            try:
                result = await sheets_sync.sync_sheets_changes_to_db(
                    settings.GOOGLE_TIMELINE_SHEETS_ID,
                    db,
                    sheet_name
                )
                logger.info(f"✅ Синхронизация изменений из Sheets завершена: {result}")
                return result
            except Exception as e:
                logger.error(f"❌ Ошибка синхронизации изменений из Sheets: {e}", exc_info=True)
                raise
        
        import asyncio
        asyncio.create_task(sync_async())
        
        return {
            "status": "sync_started",
            "message": f"Синхронизация изменений из Google Sheets запущена для листа '{sheet_name}'",
            "sheet": sheet_name,
            "note": "Синхронизация выполняется в фоне. Изменения будут применены через несколько секунд."
        }
        
    except Exception as e:
        logger.error(f"Failed to sync changes from sheets: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации изменений из Google Sheets: {str(e)}"
        )


@router.get("")
async def get_calendar(
    view: Literal["month", "week", "timeline", "gantt", "kanban"] = Query("month", description="Тип представления"),
    start_date: Optional[date] = Query(None, description="Начальная дата (для month/week/gantt)"),
    end_date: Optional[date] = Query(None, description="Конечная дата (для timeline/gantt)"),
    task_type: Optional[TaskType] = Query(None, description="Фильтр по типу задачи (smm, design, channel, prfr)"),
    detail_level: Literal["compact", "normal", "detailed"] = Query("normal", description="Уровень детализации: compact (только названия), normal (с кратким описанием), detailed (все поля)"),
    include_equipment: bool = Query(True, description="Включать бронирование оборудования"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Получить календарь/таймлайн задач
    
    Поддерживает представления:
    - month: календарь на месяц (с задачами, этапами, событиями, оборудованием)
    - week: недельный вид
    - timeline: горизонтальная шкала (Gantt-подобная)
    - gantt: полноценный Gantt-диаграмма с зависимостями
    - kanban: Kanban-доска по статусам задач
    
    Календари по ролям:
    - Используй task_type для фильтрации (smm, design, channel, prfr)
    - Можно использовать несколько типов одновременно (будут отдельные полоски разного цвета)
    
    Уровни детализации:
    - compact: только фото и название задачи
    - normal: фото, название, краткое описание, дедлайн
    - detailed: все поля задачи, этапы, материалы
    """
    try:
        # Если дата не указана, используем текущую
        if not start_date:
            start_date = date.today()
        
        if view == "month":
            return await _get_month_view(db, start_date, task_type, current_user, detail_level, include_equipment)
        elif view == "week":
            return await _get_week_view(db, start_date, task_type, current_user, detail_level, include_equipment)
        elif view == "timeline":
            if not end_date:
                # По умолчанию показываем 6 месяцев от start_date
                end_date = start_date + relativedelta(months=6)
            return await _get_timeline_view(db, start_date, end_date, task_type, current_user, detail_level, include_equipment)
        elif view == "gantt":
            if not end_date:
                end_date = start_date + relativedelta(months=6)
            return await _get_gantt_view(db, start_date, end_date, task_type, current_user)
        elif view == "kanban":
            return await _get_kanban_view(db, task_type, current_user)
        else:
            return {"error": "Invalid view type", "allowed": ["month", "week", "timeline", "gantt", "kanban"]}
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Calendar error: {e}\n{traceback.format_exc()}")
        return {
            "error": str(e),
            "view": view,
            "message": "Произошла ошибка при получении календаря"
        }


async def _get_month_view(
    db: AsyncSession,
    month_date: date,
    task_type: Optional[TaskType],
    current_user: Optional[User],
    detail_level: str = "normal",
    include_equipment: bool = True
):
    """Получить календарь на месяц"""
    # Вычисляем начало и конец месяца
    first_day = month_date.replace(day=1)
    last_day = month_date.replace(day=cal_lib.monthrange(month_date.year, month_date.month)[1])
    
    # Получаем задачи и этапы в этом диапазоне
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, first_day, last_day, task_type, current_user
    )
    
    # Формируем структуру календаря
    calendar_data = []
    current_date = first_day
    
    while current_date <= last_day:
        day_tasks = []
        day_stages = []
        
        # Находим задачи и этапы на эту дату
        for task in tasks:
            if task.due_date and task.due_date.date() == current_date:
                task_data = {
                    "id": str(task.id),
                    "title": task.title,
                    "type": task.type.value,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "color": _get_task_color_by_type(task.type),  # Цвет по роли
                    "is_event": False
                }
                
                # Добавляем данные в зависимости от уровня детализации
                if detail_level == "compact":
                    # Только минимум: фото, название
                    task_data["thumbnail"] = task.thumbnail_image_url
                elif detail_level == "normal":
                    # Фото, название, краткое описание, дедлайн
                    task_data["thumbnail"] = task.thumbnail_image_url
                    task_data["description"] = (task.description[:100] + "...") if task.description and len(task.description) > 100 else (task.description or "")
                    task_data["due_date"] = task.due_date.isoformat() if task.due_date else None
                elif detail_level == "detailed":
                    # Все поля
                    task_data["thumbnail"] = task.thumbnail_image_url
                    task_data["description"] = task.description
                    task_data["due_date"] = task.due_date.isoformat() if task.due_date else None
                    task_data["created_at"] = task.created_at.isoformat()
                    task_data["assignments_count"] = len(task.assignments) if hasattr(task, 'assignments') else 0
                    task_data["stages_count"] = len(task.stages) if task.stages else 0
                    task_data["role_requirements"] = task.role_specific_requirements
                
                day_tasks.append(task_data)
        
        # Добавляем этапы
        for stage in stages:
            if stage.due_date and stage.due_date.date() == current_date:
                day_stages.append({
                    "id": str(stage.id),
                    "task_id": str(stage.task_id),
                    "stage_name": stage.stage_name,
                    "status_color": stage.status_color,
                    "status": stage.status.value
                })
        
        calendar_data.append({
            "date": current_date.isoformat(),
            "tasks": day_tasks,
            "stages": day_stages
        })
        
        current_date = current_date + relativedelta(days=1)
    
    # Добавляем мероприятия (events)
    # Событие попадает в диапазон, если date_start <= last_day и date_end >= first_day
    events_query = select(Event).where(
        and_(
            Event.date_start <= last_day,
            Event.date_end >= first_day
        )
    )
    events_result = await db.execute(events_query)
    events = events_result.scalars().all()
    
    events_list = [
        {
            "id": str(event.id),
            "name": event.name,
            "date_start": event.date_start.isoformat(),
            "date_end": event.date_end.isoformat(),
            "color": "purple"
        }
        for event in events
    ]
    
    # Добавляем бронирование оборудования (если нужно)
    equipment_bookings = []
    if include_equipment:
        equipment_query = select(EquipmentRequest).where(
            and_(
                EquipmentRequest.start_date <= last_day,
                EquipmentRequest.end_date >= first_day,
                EquipmentRequest.status.in_(["approved", "active"])
            )
        )
        equipment_result = await db.execute(equipment_query)
        equipment_requests = equipment_result.scalars().all()
        
        for eq_request in equipment_requests:
            # Добавляем бронирование в соответствующие дни календаря
            current_eq_date = max(eq_request.start_date, first_day)
            end_eq_date = min(eq_request.end_date, last_day)
            
            while current_eq_date <= end_eq_date:
                # Находим соответствующий день в calendar_data
                for day_data in calendar_data:
                    if day_data["date"] == current_eq_date.isoformat():
                        if "equipment" not in day_data:
                            day_data["equipment"] = []
                        
                        day_data["equipment"].append({
                            "id": str(eq_request.id),
                            "equipment_id": str(eq_request.equipment_id),
                            "task_id": str(eq_request.task_id) if eq_request.task_id else None,
                            "user_id": str(eq_request.user_id),
                            "start_date": eq_request.start_date.isoformat(),
                            "end_date": eq_request.end_date.isoformat(),
                            "color": _get_task_color_by_type(task_type) if task_type else "#FF6B6B"  # Красный для оборудования
                        })
                        break
                
                current_eq_date = current_eq_date + relativedelta(days=1)
    
    return {
        "view": "month",
        "month": month_date.month,
        "year": month_date.year,
        "first_day": first_day.isoformat(),
        "last_day": last_day.isoformat(),
        "days": calendar_data,
        "events": events_list,
        "detail_level": detail_level,
        "task_type_filter": task_type.value if task_type else None,
        "equipment_included": include_equipment
    }


async def _get_week_view(
    db: AsyncSession,
    week_start: date,
    task_type: Optional[TaskType],
    current_user: Optional[User],
    detail_level: str = "normal",
    include_equipment: bool = True
):
    """Получить недельный вид"""
    # Вычисляем начало недели (понедельник)
    days_since_monday = week_start.weekday()
    monday = week_start - relativedelta(days=days_since_monday)
    sunday = monday + relativedelta(days=6)
    
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, monday, sunday, task_type, current_user
    )
    
    week_data = []
    current_date = monday
    
    while current_date <= sunday:
        day_items = []
        
        # Задачи
        for task in tasks:
            if task.due_date and task.due_date.date() == current_date:
                task_item = {
                    "type": "task",
                    "id": str(task.id),
                    "title": task.title,
                    "task_type": task.type.value,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "color": _get_task_color_by_type(task.type)  # Цвет по роли
                }
                
                # Добавляем данные в зависимости от уровня детализации
                if detail_level in ["normal", "detailed"]:
                    task_item["thumbnail"] = task.thumbnail_image_url
                    task_item["description"] = (task.description[:100] + "...") if task.description and len(task.description) > 100 else (task.description or "") if detail_level == "normal" else task.description
                    task_item["due_date"] = task.due_date.isoformat() if task.due_date else None
                
                if detail_level == "detailed":
                    task_item["assignments_count"] = len(task.assignments) if hasattr(task, 'assignments') else 0
                    task_item["stages_count"] = len(task.stages) if task.stages else 0
                
                day_items.append(task_item)
        
        # Этапы
        for stage in stages:
            if stage.due_date and stage.due_date.date() == current_date:
                day_items.append({
                    "type": "stage",
                    "id": str(stage.id),
                    "task_id": str(stage.task_id),
                    "title": f"{stage.task.title} - {stage.stage_name}",
                    "color": stage.status_color,
                    "status": stage.status.value
                })
        
        # Добавляем оборудование на этот день (если нужно)
        if include_equipment:
            equipment_query = select(EquipmentRequest).where(
                and_(
                    EquipmentRequest.start_date <= current_date,
                    EquipmentRequest.end_date >= current_date,
                    EquipmentRequest.status.in_(["approved", "active"])
                )
            )
            equipment_result = await db.execute(equipment_query)
            equipment_requests = equipment_result.scalars().all()
            
            for eq_request in equipment_requests:
                day_items.append({
                    "type": "equipment",
                    "id": str(eq_request.id),
                    "equipment_id": str(eq_request.equipment_id),
                    "task_id": str(eq_request.task_id) if eq_request.task_id else None,
                    "title": f"Бронирование оборудования",
                    "color": "#FF6B6B",
                    "start_date": eq_request.start_date.isoformat(),
                    "end_date": eq_request.end_date.isoformat()
                })
        
        week_data.append({
            "date": current_date.isoformat(),
            "day_name": current_date.strftime("%A"),
            "items": day_items
        })
        
        current_date = current_date + relativedelta(days=1)
    
    return {
        "view": "week",
        "start_date": monday.isoformat(),
        "end_date": sunday.isoformat(),
        "days": week_data,
        "detail_level": detail_level,
        "task_type_filter": task_type.value if task_type else None,
        "equipment_included": include_equipment
    }


async def _get_timeline_view(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    task_type: Optional[TaskType],
    current_user: Optional[User],
    detail_level: str = "normal",
    include_equipment: bool = True
):
    """Получить таймлайн (горизонтальная шкала)"""
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, start_date, end_date, task_type, current_user
    )
    
    timeline_items = []
    
    # Задачи
    for task in tasks:
        task_start = task.created_at.date()
        task_end = task.due_date.date() if task.due_date else task_start
        
        # Задача попадает в таймлайн, если пересекается с диапазоном
        if start_date <= task_end and end_date >= task_start:
            task_item = {
                "type": "task",
                "id": str(task.id),
                "title": task.title,
                "type_task": task.type.value,
                "start_date": task_start.isoformat(),
                "end_date": task_end.isoformat(),
                "color": _get_task_color_by_type(task.type),  # Цвет по роли
                "status": task.status.value,
                "priority": task.priority.value
            }
            
            # Добавляем данные в зависимости от уровня детализации
            if detail_level in ["normal", "detailed"]:
                task_item["thumbnail"] = task.thumbnail_image_url
                task_item["description"] = (task.description[:100] + "...") if task.description and len(task.description) > 100 else (task.description or "") if detail_level == "normal" else task.description
            
            if detail_level == "detailed":
                # Добавляем этапы задачи на таймлайне
                task_stages = []
                if task.stages:
                    for stage in sorted(task.stages, key=lambda s: s.stage_order):
                        if stage.due_date and start_date <= stage.due_date.date() <= end_date:
                            task_stages.append({
                                "id": str(stage.id),
                                "name": stage.stage_name,
                                "date": stage.due_date.date().isoformat(),
                                "color": stage.status_color,
                                "status": stage.status.value
                            })
                task_item["stages"] = task_stages
                task_item["assignments_count"] = len(task.assignments) if hasattr(task, 'assignments') else 0
            
            timeline_items.append(task_item)
    
    # Этапы (только если не включены в detailed задачу)
    if detail_level != "detailed":
        for stage in stages:
            if stage.due_date and start_date <= stage.due_date.date() <= end_date:
                # Проверяем, что этап не был уже добавлен в задачу
                task_already_has_stages = any(
                    item.get("type") == "task" and 
                    item.get("id") == str(stage.task_id) and 
                    "stages" in item
                    for item in timeline_items
                )
                
                if not task_already_has_stages:
                    timeline_items.append({
                        "type": "stage",
                        "id": str(stage.id),
                        "task_id": str(stage.task_id),
                        "task_title": stage.task.title,
                        "stage_name": stage.stage_name,
                        "date": stage.due_date.date().isoformat(),
                        "color": stage.status_color,
                        "status": stage.status.value
                    })
    
    # Мероприятия
    events_query = select(Event).where(
        and_(
            Event.date_start <= end_date,
            Event.date_end >= start_date
        )
    )
    events_result = await db.execute(events_query)
    events = events_result.scalars().all()
    
    for event in events:
        timeline_items.append({
            "type": "event",
            "id": str(event.id),
            "title": event.name,
            "start_date": event.date_start.isoformat(),
            "end_date": event.date_end.isoformat() if event.date_end else None,
            "color": "purple"
        })
    
    # Добавляем бронирование оборудования (если нужно)
    if include_equipment:
        equipment_query = select(EquipmentRequest).where(
            and_(
                EquipmentRequest.start_date <= end_date,
                EquipmentRequest.end_date >= start_date,
                EquipmentRequest.status.in_(["approved", "active"])
            )
        )
        equipment_result = await db.execute(equipment_query)
        equipment_requests = equipment_result.scalars().all()
        
        for eq_request in equipment_requests:
            timeline_items.append({
                "type": "equipment",
                "id": str(eq_request.id),
                "equipment_id": str(eq_request.equipment_id),
                "task_id": str(eq_request.task_id) if eq_request.task_id else None,
                "title": f"Бронирование оборудования",
                "start_date": eq_request.start_date.isoformat(),
                "end_date": eq_request.end_date.isoformat(),
                "color": "#FF6B6B"  # Красный для оборудования
            })
    
    return {
        "view": "timeline",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "items": sorted(timeline_items, key=lambda x: x.get("start_date") or x.get("date", "")),
        "detail_level": detail_level,
        "task_type_filter": task_type.value if task_type else None,
        "equipment_included": include_equipment
    }


async def _get_tasks_and_stages_in_range(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    task_type: Optional[TaskType],
    current_user: Optional[User]
):
    """Получить задачи и этапы в диапазоне дат"""
    # Запрос для задач
    # Задача попадает в диапазон, если:
    # - due_date или created_at >= start_date И
    # - due_date или created_at <= end_date
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    conditions = [
        or_(
            Task.due_date >= start_dt,
            Task.created_at >= start_dt
        ),
        or_(
            Task.due_date <= end_dt,
            Task.created_at <= end_dt
        )
    ]
    
    if task_type:
        conditions.append(Task.type == task_type)
    
    tasks_query = select(Task).where(and_(*conditions))
    tasks_query = tasks_query.options(
        selectinload(Task.stages),
        selectinload(Task.assignments)  # Загружаем назначения для подсчёта
    )
    
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    # Запрос для этапов
    stages_query = select(TaskStage).join(Task).where(
        and_(
            TaskStage.due_date >= datetime.combine(start_date, datetime.min.time()),
            TaskStage.due_date <= datetime.combine(end_date, datetime.max.time())
        )
    )
    
    if task_type:
        stages_query = stages_query.where(Task.type == task_type)
    
    stages_query = stages_query.options(selectinload(TaskStage.task))
    
    stages_result = await db.execute(stages_query)
    stages = stages_result.scalars().all()
    
    return list(tasks), list(stages)


async def _get_gantt_view(
    db: AsyncSession,
    start_date: date,
    end_date: date,
    task_type: Optional[TaskType],
    current_user: Optional[User]
):
    """Получить Gantt-диаграмму с зависимостями"""
    tasks, stages = await _get_tasks_and_stages_in_range(
        db, start_date, end_date, task_type, current_user
    )
    
    gantt_items = []
    
    # Задачи
    for task in tasks:
        task_start = task.created_at.date()
        task_end = task.due_date.date() if task.due_date else task_start
        
        # Задача попадает в Gantt, если пересекается с диапазоном
        if start_date <= task_end and end_date >= task_start:
            # Получаем этапы задачи для визуализации
            task_stages = []
            if task.stages:
                for stage in sorted(task.stages, key=lambda s: s.stage_order):
                    if stage.due_date:
                        stage_end = stage.due_date.date()
                        stage_start = task_start  # Этап начинается с создания задачи или предыдущего этапа
                        
                        # Этап попадает в Gantt, если пересекается с диапазоном
                        if start_date <= stage_end and end_date >= stage_start:
                            task_stages.append({
                                "id": str(stage.id),
                                "name": stage.stage_name,
                                "start": stage_start.isoformat(),
                                "end": stage_end.isoformat(),
                                "color": stage.status_color,
                                "status": stage.status.value,
                                "order": stage.stage_order
                            })
            
            gantt_items.append({
                "id": str(task.id),
                "title": task.title,
                "type": task.type.value,
                "start": task_start.isoformat(),
                "end": task_end.isoformat(),
                "color": _get_task_color_by_type(task.type),  # Цвет по роли
                "status": task.status.value,
                "priority": task.priority.value,
                "stages": task_stages,
                "thumbnail": task.thumbnail_image_url,
                "description": task.description[:200] + "..." if task.description and len(task.description) > 200 else (task.description or ""),
                "assignments_count": len(task.assignments) if hasattr(task, 'assignments') and task.assignments else 0,
                "dependencies": []  # TODO: добавить зависимости между задачами (через event_id или связи)
            })
    
    # Сортируем по дате начала
    gantt_items.sort(key=lambda x: x["start"])
    
    # Добавляем бронирование оборудования в Gantt (как отдельные элементы)
    equipment_query = select(EquipmentRequest).where(
        and_(
            EquipmentRequest.start_date <= end_date,
            EquipmentRequest.end_date >= start_date,
            EquipmentRequest.status.in_(["approved", "active"])
        )
    )
    equipment_result = await db.execute(equipment_query)
    equipment_requests = equipment_result.scalars().all()
    
    equipment_items = []
    for eq_request in equipment_requests:
        equipment_items.append({
            "id": str(eq_request.id),
            "title": "Бронирование оборудования",
            "type": "equipment",
            "equipment_id": str(eq_request.equipment_id),
            "task_id": str(eq_request.task_id) if eq_request.task_id else None,
            "start": eq_request.start_date.isoformat(),
            "end": eq_request.end_date.isoformat(),
            "color": "#FF6B6B",  # Красный для оборудования
            "status": eq_request.status.value
        })
    
    # Объединяем задачи и оборудование, сортируем по дате начала
    all_gantt_items = gantt_items + equipment_items
    all_gantt_items.sort(key=lambda x: x["start"])
    
    return {
        "view": "gantt",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "tasks": gantt_items,
        "equipment": equipment_items,
        "all_items": all_gantt_items,  # Для удобства фронтенда
        "task_type_filter": task_type.value if task_type else None
    }


async def _get_kanban_view(
    db: AsyncSession,
    task_type: Optional[TaskType],
    current_user: Optional[User]
):
    """Получить Kanban-доску по статусам задач"""
    from app.models.task import TaskStatus
    
    # Получаем все задачи (или отфильтрованные по типу)
    conditions = []
    if task_type:
        conditions.append(Task.type == task_type)
    
    tasks_query = select(Task)
    if conditions:
        tasks_query = tasks_query.where(and_(*conditions))
    
    tasks_query = tasks_query.options(selectinload(Task.stages), selectinload(Task.assignments))
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    # Группируем задачи по статусам
    kanban_columns = {
        "draft": {"title": "Черновик", "tasks": []},
        "open": {"title": "Открыта", "tasks": []},
        "assigned": {"title": "Назначена", "tasks": []},
        "in_progress": {"title": "В работе", "tasks": []},
        "review": {"title": "На проверке", "tasks": []},
        "completed": {"title": "Завершена", "tasks": []},
        "cancelled": {"title": "Отменена", "tasks": []}
    }
    
    for task in tasks:
        status_key = task.status.value if task.status.value in kanban_columns else "draft"
        
        task_data = {
            "id": str(task.id),
            "title": task.title,
            "type": task.type.value,
            "priority": task.priority.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "assignments_count": len(task.assignments) if task.assignments else 0,
            "stages_count": len(task.stages) if task.stages else 0,
            "thumbnail": task.thumbnail_image_url
        }
        
        kanban_columns[status_key]["tasks"].append(task_data)
    
    # Сортируем задачи в каждой колонке по приоритету и дедлайну
    for status, data in kanban_columns.items():
        data["tasks"].sort(key=lambda t: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(t["priority"], 0),
            t["due_date"] or "9999-12-31"  # Задачи без дедлайна в конец
        ), reverse=True)
    
    return {
        "view": "kanban",
        "task_type_filter": task_type.value if task_type else None,
        "columns": [
            {
                "status": status,
                "title": data["title"],
                "tasks_count": len(data["tasks"]),
                "tasks": data["tasks"]
            }
            for status, data in kanban_columns.items()
        ]
    }


def _get_task_color(status, priority):
    """Определить цвет задачи на основе статуса и приоритета"""
    if status.value == "completed":
        return "blue"
    elif status.value in ["review"]:
        return "yellow"
    elif priority.value == "critical":
        return "red"
    elif status.value in ["in_progress", "assigned"]:
        return "green"
    else:
        return "gray"


def _get_task_color_by_type(task_type: TaskType) -> str:
    """Определить цвет задачи по типу (для визуализации разных ролей)"""
    color_map = {
        TaskType.SMM: "#4CAF50",      # Зелёный
        TaskType.DESIGN: "#2196F3",    # Синий
        TaskType.CHANNEL: "#FF9800",   # Оранжевый
        TaskType.PRFR: "#9C27B0"       # Фиолетовый
    }
    return color_map.get(task_type, "#757575")  # Серый по умолчанию
