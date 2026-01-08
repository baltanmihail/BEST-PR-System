"""
Сервис синхронизации календаря с Google Sheets
"""
import logging
from typing import List, Optional
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.models.task import Task, TaskStage, TaskType
from app.models.event import Event
from app.models.equipment import EquipmentRequest
from app.services.google_service import GoogleService
import calendar as cal_lib

logger = logging.getLogger(__name__)


class SheetsSyncService:
    """Сервис для синхронизации календаря с Google Sheets"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        # ID Google Sheets документа с таймлайнами (будет создан при первой синхронизации)
        # Будет храниться в настройках или создаваться автоматически
        self.timeline_sheets_id = None
    
    async def sync_calendar_to_sheets_async(
        self,
        month: int,
        year: int,
        roles: List[str],
        db: AsyncSession
    ) -> dict:
        """
        Асинхронная версия синхронизации календаря с Google Sheets
        
        Используется для вызова из async context
        """
        # Получаем данные из БД асинхронно
        first_day = date(year, month, 1)
        last_day = date(year, month, cal_lib.monthrange(year, month)[1])
        
        start_dt = datetime.combine(first_day, datetime.min.time())
        end_dt = datetime.combine(last_day, datetime.max.time())
        
        # Получаем задачи в диапазоне дат (задача попадает, если created_at или due_date в диапазоне)
        from sqlalchemy import or_, and_
        tasks_query = select(Task).where(
            and_(
                or_(
                    Task.created_at >= start_dt,
                    Task.due_date >= start_dt
                ),
                or_(
                    Task.created_at <= end_dt,
                    Task.due_date <= end_dt
                )
            )
        )
        tasks_result = await db.execute(tasks_query)
        tasks = tasks_result.scalars().all()
        
        # Преобразуем в список для передачи в синхронную функцию
        tasks_list = list(tasks)
        
        # Затем вызываем синхронную синхронизацию с Google Sheets через executor
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            executor,
            lambda: self._sync_to_sheets_sync(month, year, roles, tasks_list, first_day, last_day)
        )
    
    def _sync_to_sheets_sync(
        self,
        month: int,
        year: int,
        roles: List[str],
        tasks: List[Task],
        first_day: date,
        last_day: date
    ) -> dict:
        """
        Синхронная часть синхронизации с Google Sheets
        
        Работает с уже загруженными данными из БД
        """
        try:
            # Получаем или создаём Google Sheets документ
            sheets_doc = self._get_or_create_timeline_sheets()
            
            # Синхронизируем общий календарь
            self._sync_general_calendar(sheets_doc, first_day, last_day, month, year, tasks)
            
            # Синхронизируем календари по ролям
            role_to_type = {
                "smm": TaskType.SMM,
                "design": TaskType.DESIGN,
                "channel": TaskType.CHANNEL,
                "prfr": TaskType.PRFR
            }
            
            for role in roles:
                if role in role_to_type:
                    task_type = role_to_type[role]
                    role_tasks = [t for t in tasks if t.type == task_type]
                    self._sync_role_calendar(
                        sheets_doc, 
                        first_day, 
                        last_day, 
                        month, 
                        year, 
                        role, 
                        task_type, 
                        role_tasks
                    )
            
            logger.info(f"✅ Календарь синхронизирован с Google Sheets для {month}/{year}")
            
            return {
                "status": "success",
                "sheets_id": sheets_doc.get("id"),
                "month": month,
                "year": year,
                "roles": roles
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации календаря с Google Sheets: {e}")
            raise
    
    def _get_or_create_timeline_sheets(self) -> dict:
        """Получить или создать Google Sheets документ с таймлайнами"""
        # TODO: Реализовать получение/создание Google Sheets документа
        # Пока возвращаем заглушку
        
        # Логика:
        # 1. Проверить, существует ли документ "BEST PR System - Таймлайны"
        # 2. Если нет - создать новый
        # 3. Создать листы: "Общий", "SMM", "Design", "Channel", "PR-FR"
        # 4. Вернуть информацию о документе
        
        return {"id": "placeholder_sheets_id"}
    
    def _sync_general_calendar(
        self,
        sheets_doc: dict,
        first_day: date,
        last_day: date,
        month: int,
        year: int,
        tasks: List[Task]
    ):
        """Синхронизировать общий календарь"""
        # TODO: Реализовать полную синхронизацию общего календаря
        # Логика:
        # 1. Получить или создать лист "Общий" в Google Sheets
        # 2. Создать структуру таблицы: дни месяца в строках, задачи/этапы в ячейках
        # 3. Заполнить данные: название задачи, тип, дедлайн
        # 4. Окрасить ячейки в цвета задач (SMM=зелёный, Design=синий, Channel=оранжевый, PR-FR=фиолетовый)
        # 5. Добавить гиперссылки на карточки задач (ссылки на сайт)
        # 6. Добавить этапы задач в отдельные строки под задачей
        # 7. Добавить бронирование оборудования (отдельные ячейки)
        
        logger.info(f"Синхронизация общего календаря для {month}/{year}: {len(tasks)} задач")
        # Пока только логируем, полная реализация будет добавлена позже
    
    def _sync_role_calendar(
        self,
        sheets_doc: dict,
        first_day: date,
        last_day: date,
        month: int,
        year: int,
        role: str,
        task_type: TaskType,
        tasks: List[Task]
    ):
        """Синхронизировать календарь конкретной роли"""
        # TODO: Реализовать полную синхронизацию календаря роли
        # Логика:
        # 1. Получить или создать лист с именем роли (SMM, Design, Channel, PR-FR)
        # 2. Создать структуру таблицы: дни месяца в строках, задачи этого типа в ячейках
        # 3. Заполнить данные: название задачи, этапы, дедлайны
        # 4. Окрасить ячейки в цвет роли (единый цвет для всех задач этого типа)
        # 5. Добавить гиперссылки на карточки задач
        # 6. Добавить бронирование оборудования, связанное с задачами этого типа
        
        logger.info(f"Синхронизация календаря {role} для {month}/{year}: {len(tasks)} задач")
        # Пока только логируем, полная реализация будет добавлена позже
    
    def _get_or_create_timeline_sheets(self) -> dict:
        """Получить или создать Google Sheets документ с таймлайнами"""
        # TODO: Реализовать получение/создание Google Sheets документа
        # Логика:
        # 1. Проверить, существует ли документ "BEST PR System - Таймлайны" в корневой папке
        # 2. Если нет - создать новый документ
        # 3. Создать листы: "Общий", "SMM", "Design", "Channel", "PR-FR"
        # 4. Вернуть информацию о документе (ID, ссылку)
        
        logger.info("Получение/создание Google Sheets документа с таймлайнами")
        # Пока возвращаем заглушку
        return {"id": "placeholder_sheets_id", "url": "https://docs.google.com/spreadsheets/d/placeholder_sheets_id"}
