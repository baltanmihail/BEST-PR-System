"""
Сервис синхронизации календаря с Google Sheets
Полная реализация с созданием таблицы, листов и заполнением данными
"""
import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.models.task import Task, TaskStage, TaskType, TaskStatus, TaskPriority
from app.models.event import Event
from app.models.equipment import EquipmentRequest
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from app.config import settings
import calendar as cal_lib

logger = logging.getLogger(__name__)

# Цветовая кодировка для типов задач (RGB)
TASK_TYPE_COLORS = {
    TaskType.SMM: {"red": 0.298, "green": 0.686, "blue": 0.314},  # #4CAF50 зелёный
    TaskType.DESIGN: {"red": 0.129, "green": 0.588, "blue": 0.953},  # #2196F3 синий
    TaskType.CHANNEL: {"red": 1.0, "green": 0.596, "blue": 0.0},  # #FF9800 оранжевый
    TaskType.PRFR: {"red": 0.612, "green": 0.153, "blue": 0.690},  # #9C27B0 фиолетовый
}

# Цвета для статусов этапов (из status_color)
STAGE_COLORS = {
    "green": {"red": 0.298, "green": 0.686, "blue": 0.314},  # #4CAF50 зелёный
    "yellow": {"red": 1.0, "green": 0.843, "blue": 0.0},  # #FFD700 жёлтый
    "red": {"red": 0.956, "green": 0.262, "blue": 0.212},  # #F44336 красный
    "purple": {"red": 0.612, "green": 0.153, "blue": 0.690},  # #9C27B0 фиолетовый
    "blue": {"red": 0.129, "green": 0.588, "blue": 0.953},  # #2196F3 синий
}

# Цвета для статусов задач
TASK_STATUS_COLORS = {
    "draft": {"red": 0.9, "green": 0.9, "blue": 0.9},  # Светло-серый
    "open": {"red": 0.298, "green": 0.686, "blue": 0.314},  # Зелёный
    "assigned": {"red": 0.129, "green": 0.588, "blue": 0.953},  # Синий
    "in_progress": {"red": 1.0, "green": 0.843, "blue": 0.0},  # Золотой
    "review": {"red": 0.612, "green": 0.153, "blue": 0.690},  # Фиолетовый
    "completed": {"red": 0.298, "green": 0.686, "blue": 0.314},  # Зелёный
    "cancelled": {"red": 0.956, "green": 0.262, "blue": 0.212},  # Красный
}

# Цвет для просроченных дедлайнов
OVERDUE_COLOR = {"red": 0.956, "green": 0.262, "blue": 0.212}  # #F44336 красный


class SheetsSyncService:
    """Сервис для синхронизации календаря с Google Sheets"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.drive_structure = DriveStructureService()
        self.timeline_sheets_id = None
    
    async def sync_calendar_to_sheets_async(
        self,
        month: int,
        year: int,
        roles: List[str],
        db: AsyncSession,
        statuses: Optional[List[str]] = None,  # Фильтр по статусам задач
        scale: str = "days",  # Масштаб: "days", "weeks", "months"
        pull_from_sheets: bool = True  # Читать правки из Sheets -> система перед выгрузкой
    ) -> dict:
        """
        Асинхронная версия синхронизации календаря с Google Sheets
        
        Используется для вызова из async context
        """
        # Получаем данные из БД асинхронно
        # Синхронизируем несколько месяцев: январь-май текущего года
        first_day = date(year, 1, 1)  # Начало января
        last_day = date(year, 5, cal_lib.monthrange(year, 5)[1])  # Конец мая
        
        start_dt = datetime.combine(first_day, datetime.min.time())
        end_dt = datetime.combine(last_day, datetime.max.time())
        
        # Получаем задачи в диапазоне дат
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
        
        # Фильтр по статусам (если указан)
        if statuses:
            from app.models.task import TaskStatus
            try:
                # Преобразуем строки в TaskStatus enum
                status_enums = [TaskStatus(s) for s in statuses if s in [st.value for st in TaskStatus]]
                if status_enums:
                    tasks_query = tasks_query.where(Task.status.in_(status_enums))
            except ValueError:
                # Если есть неверные статусы, игнорируем фильтр
                logger.warning(f"Некорректные статусы в фильтре: {statuses}")
        tasks_result = await db.execute(tasks_query)
        tasks = tasks_result.scalars().all()
        
        # Если нужно, сначала применяем правки из Sheets -> систему
        if pull_from_sheets:
            try:
                await self._pull_tasks_updates(db=db)
                # После обновления перечитываем задачи
                tasks_result = await db.execute(tasks_query)
                tasks = tasks_result.scalars().all()
            except Exception as e:
                logger.warning(f"Не удалось применить правки из Sheets: {e}")
        
        # Загружаем этапы для всех задач одним запросом
        task_ids = [str(task.id) for task in tasks]
        if task_ids:
            stages_query = select(TaskStage).where(TaskStage.task_id.in_(task_ids))
            stages_result = await db.execute(stages_query)
            stages = stages_result.scalars().all()
            
            # Группируем этапы по задачам
            stages_by_task = {}
            for stage in stages:
                task_id_str = str(stage.task_id)
                if task_id_str not in stages_by_task:
                    stages_by_task[task_id_str] = []
                stages_by_task[task_id_str].append(stage)
            
            # Присваиваем этапы задачам
            for task in tasks:
                task_id_str = str(task.id)
                if task_id_str in stages_by_task:
                    # Сортируем этапы по порядку
                    task._stages_cache = sorted(
                        stages_by_task[task_id_str],
                        key=lambda s: s.stage_order
                    )
                else:
                    task._stages_cache = []
        else:
            for task in tasks:
                task._stages_cache = []
        
        # Преобразуем в список для передачи в синхронную функцию
        tasks_list = list(tasks)
        
        # Затем вызываем синхронную синхронизацию с Google Sheets через executor
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_event_loop()
        
        return await loop.run_in_executor(
            executor,
            lambda: self._sync_to_sheets_sync(month, year, roles, tasks_list, first_day, last_day, statuses, scale)
        )
    
    def _sync_to_sheets_sync(
        self,
        month: int,
        year: int,
        roles: List[str],
        tasks: List[Task],
        first_day: date,
        last_day: date,
        statuses: Optional[List[str]] = None,
        scale: str = "days"
    ) -> dict:
        """
        Синхронная часть синхронизации с Google Sheets
        
        Работает с уже загруженными данными из БД
        """
        try:
            # Получаем или создаём Google Sheets документ
            sheets_doc = self._get_or_create_timeline_sheets()
            spreadsheet_id = sheets_doc["id"]
            
            # Синхронизируем общий календарь (январь-май)
            self._sync_general_calendar(
                spreadsheet_id, first_day, last_day, None, year, tasks, scale
            )
            
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
                        spreadsheet_id,
                        first_day,
                        last_day,
                        month,
                        year,
                        role,
                        task_type,
                        role_tasks,
                        scale
                    )
            
            # Табличное представление задач (двусторонняя синхронизация)
            try:
                self._write_tasks_sheet(spreadsheet_id, tasks)
            except Exception as e:
                logger.warning(f"Не удалось обновить лист TasksData: {e}")
            
            logger.info(f"✅ Календарь синхронизирован с Google Sheets для {month}/{year}")
            
            return {
                "status": "success",
                "sheets_id": spreadsheet_id,
                "sheets_url": sheets_doc.get("url"),
                "month": month,
                "year": year,
                "roles": roles
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации календаря с Google Sheets: {e}", exc_info=True)
            raise
    
    def _get_or_create_timeline_sheets(self) -> dict:
        """Получить или создать Google Sheets документ с таймлайнами"""
        # Проверяем, задан ли ID в настройках
        if settings.GOOGLE_TIMELINE_SHEETS_ID:
            try:
                # Проверяем, существует ли таблица
                metadata = self.google_service.get_file_metadata(
                    settings.GOOGLE_TIMELINE_SHEETS_ID,
                    background=True
                )
                if metadata:
                    self.timeline_sheets_id = settings.GOOGLE_TIMELINE_SHEETS_ID
                    return {
                        "id": settings.GOOGLE_TIMELINE_SHEETS_ID,
                        "url": metadata.get("webViewLink", f"https://docs.google.com/spreadsheets/d/{settings.GOOGLE_TIMELINE_SHEETS_ID}")
                    }
            except Exception as e:
                logger.warning(f"Таблица с ID {settings.GOOGLE_TIMELINE_SHEETS_ID} не найдена, создаём новую: {e}")
        
        # Ищем существующую таблицу в корневой папке
        try:
            bot_folder_id = self.drive_structure.get_bot_folder_id()
            files = self.google_service.list_files(folder_id=bot_folder_id, background=True)
            
            for file in files:
                if (file.get('name') == 'BEST PR System - Таймлайны' and
                    file.get('mimeType') == 'application/vnd.google-apps.spreadsheet'):
                    self.timeline_sheets_id = file['id']
                    return {
                        "id": file['id'],
                        "url": f"https://docs.google.com/spreadsheets/d/{file['id']}"
                    }
        except Exception as e:
            logger.warning(f"Ошибка поиска существующей таблицы: {e}")
        
        # Создаём новую таблицу
        logger.info("📊 Создание новой Google Sheets таблицы 'BEST PR System - Таймлайны'")
        try:
            bot_folder_id = self.drive_structure.get_bot_folder_id()
            logger.info(f"✅ ID папки бота: {bot_folder_id}")
        except Exception as e:
            logger.error(f"❌ Не удалось получить ID папки бота: {e}", exc_info=True)
            logger.info("📁 Пытаемся инициализировать структуру папок...")
            # Пытаемся инициализировать структуру папок
            try:
                structure = self.drive_structure.initialize_structure()
                bot_folder_id = structure.get("bot_folder_id")
                if not bot_folder_id:
                    raise ValueError("Не удалось получить ID папки бота после инициализации")
                logger.info(f"✅ Структура инициализирована, ID папки бота: {bot_folder_id}")
            except Exception as init_error:
                logger.error(f"❌ Не удалось инициализировать структуру папок: {init_error}", exc_info=True)
                raise
        
        try:
            logger.info(f"📝 Создание таблицы в папке {bot_folder_id}...")
            sheets_doc = self.google_service.create_spreadsheet(
                "BEST PR System - Таймлайны",
                folder_id=bot_folder_id,
                background=False  # Используем синхронный режим для лучшей обработки ошибок
            )
            logger.info(f"✅ Таблица создана: {sheets_doc.get('id')}")
        except Exception as e:
            logger.error(f"❌ Ошибка создания таблицы таймлайна: {e}", exc_info=True)
            logger.error(f"Тип ошибки: {type(e).__name__}")
            raise
        
        self.timeline_sheets_id = sheets_doc["id"]
        
        # Создаём листы
        sheet_names = ["Общий", "SMM", "Design", "Channel", "PR-FR"]
        for sheet_name in sheet_names:
            try:
                self.google_service.create_sheet_tab(
                    sheets_doc["id"],
                    sheet_name,
                    background=True
                )
            except Exception as e:
                logger.warning(f"Ошибка создания листа '{sheet_name}': {e}")
        
        logger.info(f"✅ Создана таблица таймлайнов: {sheets_doc['id']}")
        logger.info(f"💡 Сохраните GOOGLE_TIMELINE_SHEETS_ID={sheets_doc['id']} в переменные окружения")
        
        return sheets_doc
    
    def _ensure_tasks_sheet(self, spreadsheet_id: str) -> bool:
        """Убедиться, что существует лист TasksData для двусторонней синхронизации"""
        sheet_id = self._get_sheet_id(spreadsheet_id, "TasksData")
        if sheet_id != 0:
            return True
        try:
            self.google_service.create_sheet_tab(
                spreadsheet_id,
                "TasksData",
                background=True
            )
            return True
        except Exception as e:
            logger.warning(f"Не удалось создать лист TasksData: {e}")
            return False

    def _write_tasks_sheet(self, spreadsheet_id: str, tasks: List[Task]) -> None:
        """Записать актуальные данные задач в лист TasksData"""
        if not self._ensure_tasks_sheet(spreadsheet_id):
            return
        
        headers = ["task_id", "title", "status", "priority", "due_date", "updated_at"]
        rows = []
        for task in tasks:
            due = task.due_date.isoformat() if task.due_date else ""
            updated = task.updated_at.isoformat() if task.updated_at else ""
            rows.append([
                str(task.id),
                task.title or "",
                task.status.value if isinstance(task.status, TaskStatus) else str(task.status),
                task.priority.value if isinstance(task.priority, TaskPriority) else str(task.priority),
                due,
                updated
            ])
        
        # Очищаем предыдущие данные, чтобы не оставались "хвосты"
        try:
            self.google_service.clear_sheet_range(
                "TasksData!A1:Z10000",
                spreadsheet_id=spreadsheet_id,
                background=True
            )
        except Exception as e:
            logger.warning(f"Не удалось очистить TasksData перед записью: {e}")
        
        self.google_service.write_sheet(
            "TasksData!A1:F1",
            [headers],
            sheet_id=spreadsheet_id,  # write_sheet использует sheet_id как параметр
            background=True
        )
        if rows:
            self.google_service.write_sheet(
                f"TasksData!A2:F{len(rows)+2}",
                rows,
                sheet_id=spreadsheet_id,  # write_sheet использует sheet_id как параметр
                background=True
            )

    async def _pull_tasks_updates(self, db: AsyncSession) -> None:
        """
        Применить правки из листа TasksData -> задачи в системе.
        Обновляем: статус, приоритет, дедлайн.
        """
        sheets_doc = self._get_or_create_timeline_sheets()
        spreadsheet_id = sheets_doc["id"]
        
        if not self._ensure_tasks_sheet(spreadsheet_id):
            return
        
        try:
            data = self.google_service.read_sheet(
                "TasksData!A2:F",
                sheet_id=spreadsheet_id,  # read_sheet использует sheet_id как параметр
                background=True
            )
        except Exception as e:
            logger.warning(f"Не удалось прочитать TasksData: {e}")
            return
        
        if not data:
            return
        
        task_ids = []
        for row in data:
            if not row or not row[0]:
                continue
            try:
                task_ids.append(uuid.UUID(row[0].strip()))
            except Exception:
                continue
        
        if not task_ids:
            return
        
        tasks_query = select(Task).where(Task.id.in_(task_ids))
        tasks_result = await db.execute(tasks_query)
        tasks = {t.id: t for t in tasks_result.scalars().all()}
        
        changes = 0
        for row in data:
            if not row or not row[0]:
                continue
            try:
                task_id = uuid.UUID(row[0].strip())
            except Exception:
                continue
            
            task = tasks.get(task_id)
            if not task:
                continue
            
            status_str = row[2].strip() if len(row) > 2 and row[2] else ""
            priority_str = row[3].strip() if len(row) > 3 and row[3] else ""
            due_str = row[4].strip() if len(row) > 4 and row[4] else ""
            
            updated = False
            
            if status_str:
                try:
                    new_status = TaskStatus(status_str)
                    if task.status != new_status:
                        task.status = new_status
                        updated = True
                except Exception:
                    pass
            
            if priority_str:
                try:
                    new_priority = TaskPriority(priority_str)
                    if task.priority != new_priority:
                        task.priority = new_priority
                        updated = True
                except Exception:
                    pass
            
            if due_str:
                try:
                    # Парсим ISO формат даты/времени с timezone
                    if 'T' in due_str or '+' in due_str or due_str.endswith('Z'):
                        new_due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                    else:
                        # Если только дата без времени, добавляем время начала дня
                        new_due = datetime.fromisoformat(due_str)
                        if new_due.tzinfo is None:
                            from datetime import timezone
                            new_due = new_due.replace(tzinfo=timezone.utc)
                    if task.due_date is None or task.due_date != new_due:
                        task.due_date = new_due
                        updated = True
                except Exception as e:
                    logger.debug(f"Не удалось распарсить дату '{due_str}' для задачи {task_id}: {e}")
                    pass
            
            if updated:
                changes += 1
        
        if changes:
            await db.commit()
            logger.info(f"✅ Применено правок из TasksData: {changes}")
    
    def _ensure_sheet_exists(self, spreadsheet_id: str, sheet_name: str) -> bool:
        """Убедиться, что лист существует, если нет - создать"""
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name)
        if sheet_id is not None:
            logger.debug(f"✅ Лист '{sheet_name}' существует (ID: {sheet_id})")
            return True
        
        # Лист не найден, пытаемся создать через OAuth (если доступен)
        oauth_sheets = self.google_service._get_oauth_sheets_service()
        if oauth_sheets:
            try:
                request_body = {
                    'requests': [{
                        'addSheet': {
                            'properties': {'title': sheet_name}
                        }
                    }]
                }
                oauth_sheets.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body=request_body
                ).execute()
                logger.info(f"✅ Создан лист '{sheet_name}' через OAuth")
                return True
            except Exception as e:
                error_str = str(e)
                if "already exists" in error_str:
                    logger.info(f"✅ Лист '{sheet_name}' уже существует")
                    return True
                logger.warning(f"⚠️ OAuth не смог создать лист: {e}")
        
        # Fallback: Service Account
        try:
            self.google_service.create_sheet_tab(
                spreadsheet_id,
                sheet_name,
                background=True
            )
            logger.info(f"✅ Создан лист '{sheet_name}'")
            return True
        except Exception as e:
            error_str = str(e)
            if "already exists" in error_str or "уже существует" in error_str.lower():
                logger.info(f"✅ Лист '{sheet_name}' уже существует")
                return True
            logger.warning(f"❌ Не удалось создать лист '{sheet_name}': {e}")
            return False
    
    def _format_task_number(self, task: Task) -> str:
        """Форматировать номер задачи в строку (TASK-001, TASK-002, ...)"""
        if task.task_number:
            return f"TASK-{task.task_number:03d}"
        # Если номера нет, используем последние 8 символов UUID
        return f"TASK-{str(task.id)[-8:].upper()}"
    
    def _sync_general_calendar(
        self,
        spreadsheet_id: str,
        first_day: date,
        last_day: date,
        month: Optional[int],
        year: int,
        tasks: List[Task],
        scale: str = "days"
    ):
        """Синхронизировать общий календарь в формате календарной сетки
        
        Формат: Первая колонка - номера задач (TASK-001, TASK-002, ...), 
        остальные колонки - даты периода (01.01, 02.01, ...)
        
        Args:
            first_day: Первый день периода
            last_day: Последний день периода
            month: Номер месяца (опционально, для логирования)
            year: Год
            tasks: Список задач
            scale: Масштаб отображения - "days" (дни), "weeks" (недели), "months" (месяцы)
        """
        month_str = f"{month}/" if month else ""
        logger.info(f"Синхронизация общего календаря для {month_str}{year} ({first_day.strftime('%d.%m')} - {last_day.strftime('%d.%m')}, масштаб: {scale}): {len(tasks)} задач")
        
        sheet_name = "Общий"
        
        # Убеждаемся, что лист существует
        if not self._ensure_sheet_exists(spreadsheet_id, sheet_name):
            logger.error(f"❌ Не удалось создать или найти лист '{sheet_name}', пропускаем синхронизацию")
            return
        
        # Получаем ID листа для форматирования
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name)
        if sheet_id == 0:
            logger.error(f"❌ Не удалось получить ID листа '{sheet_name}'")
            return
        
        # Создаём заголовки (даты месяца)
        headers = ["Задача"]
        current_date = first_day
        date_columns = {}  # {date: column_index}
        col_idx = 1
        
        while current_date <= last_day:
            date_str = current_date.strftime("%d.%m")
            headers.append(date_str)
            date_columns[current_date] = col_idx
            col_idx += 1
            current_date += timedelta(days=1)
        
        # Сортируем задачи по номеру (если есть) или по дате создания
        sorted_tasks = sorted(
            tasks, 
            key=lambda t: (t.task_number if t.task_number else 999999, t.created_at or datetime.min)
        )
        
        # Формируем строки данных (одна строка на задачу)
        rows = []
        task_rows = {}  # {task_id: row_index} для форматирования
        
        for row_idx, task in enumerate(sorted_tasks):
            # Первая колонка: номер задачи + название
            task_number_str = self._format_task_number(task)
            task_label = f"{task_number_str} {task.title[:40]}"  # Ограничиваем длину
            row = [task_label]
            task_rows[str(task.id)] = row_idx + 1  # +1 потому что первая строка - заголовок
            
            # Для каждой даты месяца проверяем события
            current_date = first_day
            while current_date <= last_day:
                cell_parts = []
                
                # Проверяем дедлайн задачи
                if task.due_date:
                    task_date = task.due_date.date()
                    if task_date == current_date:
                        cell_parts.append("📅 Дедлайн")
                
                # Проверяем этапы задачи
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date:
                            stage_date = stage.due_date.date()
                            if stage_date == current_date:
                                status_icon = "✅" if stage.status.value == "completed" else "🔄" if stage.status.value == "in_progress" else "⏳"
                                color_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "purple": "🟣", "blue": "🔵"}.get(stage.status_color, "⚪")
                                cell_parts.append(f"{color_emoji} {status_icon} {stage.stage_name}")
                
                # Если задача создана в эту дату
                if task.created_at:
                    created_date = task.created_at.date()
                    if created_date == current_date:
                        cell_parts.append("🆕 Создана")
                
                # Объединяем все части через перенос строки
                cell_text = "\n".join(cell_parts) if cell_parts else ""
                row.append(cell_text)
                current_date += timedelta(days=1)
            
            rows.append(row)
        
        # Записываем данные в таблицу через batch_update
        headers_len = len(headers)
        
        # Google Sheets имеет ограничение на количество колонок (максимум 256, но обычно используется меньше)
        # Ограничиваем количество колонок до разумного максимума (например, 100 для календаря)
        MAX_COLUMNS = 100
        if headers_len > MAX_COLUMNS:
            logger.warning(f"⚠️ Заголовков {headers_len}, обрезаем до {MAX_COLUMNS}")
            headers = headers[:MAX_COLUMNS]
            headers_len = MAX_COLUMNS
            # Обрезаем date_columns тоже
            date_columns = {k: v for k, v in date_columns.items() if v < MAX_COLUMNS}
        
        # Обрезаем/дополняем все строки до длины headers (гарантируем одинаковую длину)
        all_data = [headers]
        for row in rows:
            if len(row) > headers_len:
                # Обрезаем лишние колонки
                all_data.append(row[:headers_len])
                logger.warning(f"⚠️ Строка с задачей имела {len(row)} колонок, обрезано до {headers_len}")
            elif len(row) < headers_len:
                # Дополняем пустыми значениями
                all_data.append(row + [""] * (headers_len - len(row)))
                logger.warning(f"⚠️ Строка с задачей имела {len(row)} колонок, дополнено до {headers_len}")
            else:
                all_data.append(row)
        
        # Убеждаемся что endColumnIndex не превышает headers_len
        end_col_idx = min(headers_len, MAX_COLUMNS)
        
        # Финальная проверка: убеждаемся, что все строки имеют одинаковую длину (end_col_idx)
        # и обрезаем/дополняем их при необходимости
        normalized_data = []
        for row in all_data:
            if len(row) > end_col_idx:
                normalized_data.append(row[:end_col_idx])
            elif len(row) < end_col_idx:
                normalized_data.append(row + [""] * (end_col_idx - len(row)))
            else:
                normalized_data.append(row)
        
        # Используем batch_update для записи данных
        requests = [{
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": len(normalized_data),
                    "startColumnIndex": 0,
                    "endColumnIndex": end_col_idx
                },
                "rows": [
                    {
                        "values": [
                            {"userEnteredValue": {"stringValue": str(cell)}}
                            for cell in row
                        ]
                    }
                    for row in normalized_data
                ],
                "fields": "userEnteredValue"
            }
        }]
        
        # Сначала записываем данные
        if requests:
            self.google_service.batch_update_sheet(
                spreadsheet_id=spreadsheet_id,
                requests=requests,
                background=False
            )
        
        # Затем применяем форматирование
        format_requests = self._format_calendar_grid_sheet(
            spreadsheet_id,
            sheet_id,
            sorted_tasks,
            task_rows,
            date_columns,
            end_col_idx,  # Используем ограниченное количество колонок
            len(rows) + 1,
            first_day,
            last_day
        )
        
        if format_requests:
            self.google_service.batch_update_sheet(
                spreadsheet_id=spreadsheet_id,
                requests=format_requests,
                background=False
            )
        
        logger.info(f"✅ Обновлён календарь задач: {len(rows)} задач")
    
    def _sync_role_calendar(
        self,
        spreadsheet_id: str,
        first_day: date,
        last_day: date,
        month: int,
        year: int,
        role: str,
        task_type: TaskType,
        tasks: List[Task],
        scale: str = "days"
    ):
        """Синхронизировать календарь конкретной роли"""
        logger.info(f"Синхронизация календаря {role} для {month}/{year} (масштаб: {scale}): {len(tasks)} задач")
        
        sheet_name = role.capitalize() if role != "prfr" else "PR-FR"
        
        # Убеждаемся, что лист существует
        if not self._ensure_sheet_exists(spreadsheet_id, sheet_name):
            logger.error(f"❌ Не удалось создать или найти лист '{sheet_name}', пропускаем синхронизацию")
            return
        
        # Генерируем периоды в зависимости от масштаба
        periods = self._generate_periods(first_day, last_day, scale)
        
        # Сортируем задачи
        sorted_tasks = sorted(tasks, key=lambda t: t.created_at or datetime.min)
        
        # Формируем заголовки
        period_label = {"days": "Дата", "weeks": "Неделя", "months": "Месяц"}.get(scale, "Период")
        headers = [period_label]
        task_columns = {}
        col_idx = 1
        
        for task in sorted_tasks:
            headers.append(task.title[:50])
            task_columns[str(task.id)] = col_idx
            col_idx += 1
        
        # Формируем данные по периодам
        rows = []
        for period_start, period_end, period_label_str in periods:
            row = [period_label_str]
            
            for task in sorted_tasks:
                cell_parts = []
                task_date = task.due_date.date() if task.due_date else None
                created_date = task.created_at.date() if task.created_at else None
                
                if task_date and period_start <= task_date <= period_end:
                    cell_parts.append(f"📅 Дедлайн {task_date.strftime('%d.%m')}")
                
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date:
                            stage_date = stage.due_date.date()
                            if period_start <= stage_date <= period_end:
                                status_icon = "✅" if stage.status.value == "completed" else "🔄" if stage.status.value == "in_progress" else "⏳"
                                color_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "purple": "🟣", "blue": "🔵"}.get(stage.status_color, "⚪")
                                cell_parts.append(f"{color_emoji} {status_icon} {stage.stage_name} ({stage_date.strftime('%d.%m')})")
                
                if created_date and period_start <= created_date <= period_end:
                    cell_parts.append(f"🆕 Создана {created_date.strftime('%d.%m')}")
                
                cell_value = "\n".join(cell_parts) if cell_parts else ""
                row.append(cell_value)
            
            rows.append(row)
        
        # Записываем данные
        self.google_service.write_sheet(
            f"{sheet_name}!A1:{chr(64 + len(headers))}1",
            [headers],
            sheet_id=spreadsheet_id,
            background=True
        )
        
        if rows:
            self.google_service.write_sheet(
                f"{sheet_name}!A2:{chr(64 + len(headers))}{len(rows) + 1}",
                rows,
                sheet_id=spreadsheet_id,
                background=True
            )
        
        # Форматирование
        periods_count = len(periods)
        self._format_sheet(
            spreadsheet_id,
            sheet_name,
            sorted_tasks,
            task_columns,
            periods_count,
            first_day,
            task_type=task_type,
            periods=periods,
            scale=scale
        )
    
    def _generate_periods(self, first_day: date, last_day: date, scale: str) -> List[tuple]:
        """
        Генерирует список периодов в зависимости от масштаба
        
        Returns:
            Список кортежей (start_date, end_date, label)
        """
        periods = []
        
        if scale == "days":
            # По дням
            current = first_day
            while current <= last_day:
                periods.append((current, current, current.strftime("%d.%m")))
                current += timedelta(days=1)
        
        elif scale == "weeks":
            # По неделям (понедельник - воскресенье)
            current = first_day
            # Находим понедельник недели, в которую попадает first_day
            days_since_monday = current.weekday()
            week_start = current - timedelta(days=days_since_monday)
            
            while week_start <= last_day:
                week_end = week_start + timedelta(days=6)
                if week_end > last_day:
                    week_end = last_day
                
                # Формат: "01.01 - 07.01"
                label = f"{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m')}"
                periods.append((week_start, week_end, label))
                week_start += timedelta(days=7)
        
        elif scale == "months":
            # По месяцам
            current = first_day
            while current <= last_day:
                # Первый день месяца
                month_start = date(current.year, current.month, 1)
                # Последний день месяца
                if current.month == 12:
                    month_end = date(current.year + 1, 1, 1) - timedelta(days=1)
                else:
                    month_end = date(current.year, current.month + 1, 1) - timedelta(days=1)
                
                # Ограничиваем последний месяц
                if month_end > last_day:
                    month_end = last_day
                
                # Формат: "Январь 2025"
                month_names_ru = {
                    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
                    5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
                    9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
                }
                label = f"{month_names_ru.get(month_start.month, month_start.strftime('%B'))} {month_start.year}"
                periods.append((month_start, month_end, label))
                
                # Переходим к следующему месяцу
                if month_start.month == 12:
                    current = date(month_start.year + 1, 1, 1)
                else:
                    current = date(month_start.year, month_start.month + 1, 1)
        
        return periods
    
    def _format_sheet(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        tasks: List[Task],
        task_columns: Dict[str, int],
        periods_count: int,
        first_day: date,
        task_type: Optional[TaskType] = None,
        periods: Optional[List[tuple]] = None,
        scale: str = "days"
    ):
        """Форматировать лист: цвета, гиперссылки, дедлайны, этапы"""
        from app.config import settings
        from datetime import datetime, timezone
        
        requests = []
        sheet_id = self._get_sheet_id(spreadsheet_id, sheet_name)
        if sheet_id == 0:
            logger.warning(f"Не удалось получить ID листа {sheet_name}")
            return
        
        # Цвет для типа задач (если указан) или общий цвет
        if task_type and task_type in TASK_TYPE_COLORS:
            color = TASK_TYPE_COLORS[task_type]
        else:
            color = {"red": 0.9, "green": 0.9, "blue": 0.9}  # Серый по умолчанию
        
        current_date = datetime.now(timezone.utc).date()
        
        # Форматируем заголовки задач и ячейки с данными
        for task_id, col_idx in task_columns.items():
            task = next((t for t in tasks if str(t.id) == task_id), None)
            if not task:
                continue
            
            # Цвет заголовка по типу задачи и статусу
            task_color = TASK_TYPE_COLORS.get(task.type, color)
            status_color = TASK_STATUS_COLORS.get(task.status.value, task_color)
            
            # Гиперссылка на карточку задачи
            task_url = f"{settings.FRONTEND_URL}/tasks/{task_id}"
            hyperlink_formula = f'=HYPERLINK("{task_url}"; "{task.title[:50]}")'
            
            # Обновляем заголовок с гиперссылкой
            requests.append({
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": col_idx,
                        "endColumnIndex": col_idx + 1
                    },
                    "rows": [{
                        "values": [{
                            "userEnteredValue": {
                                "formulaValue": hyperlink_formula
                            },
                            "userEnteredFormat": {
                                "backgroundColor": status_color,
                                "textFormat": {
                                    "bold": True,
                                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                                }
                            }
                        }]
                    }],
                    "fields": "userEnteredValue,userEnteredFormat"
                }
            })
            
            # Форматируем ячейки с дедлайнами и этапами
            for period_idx, period_info in enumerate(periods if periods else [(first_day + timedelta(days=i), first_day + timedelta(days=i), "") for i in range(periods_count)]):
                period_start, period_end, _ = period_info
                row_idx = period_idx + 1  # +1 потому что первая строка - заголовок
                
                # Проверяем, есть ли данные задачи в этом периоде
                has_task_data = False
                cell_text = ""
                cell_color = task_color  # Цвет по умолчанию
                
                # Проверяем дедлайн задачи (попадает в период)
                if task.due_date:
                    task_date = task.due_date.date()
                    if period_start <= task_date <= period_end:
                        has_task_data = True
                        cell_text += f"📅 Дедлайн {task_date.strftime('%d.%m')}\n"
                        # Красный цвет для просроченных дедлайнов
                        cell_color = OVERDUE_COLOR if task_date < current_date else task_color
                        
                # Проверяем этапы задачи
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date:
                            stage_date = stage.due_date.date()
                            if period_start <= stage_date <= period_end:
                                has_task_data = True
                                status_icon = "✅" if stage.status.value == "completed" else "🔄" if stage.status.value == "in_progress" else "⏳"
                                color_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "purple": "🟣", "blue": "🔵"}.get(stage.status_color, "⚪")
                                cell_text += f"{color_emoji} {status_icon} {stage.stage_name} ({stage_date.strftime('%d.%m')})\n"
                                # Цвет этапа из status_color
                                stage_color = STAGE_COLORS.get(stage.status_color, STAGE_COLORS["green"])
                                
                                # Если этап просрочен и не завершён - красный
                                if stage_date < current_date and stage.status.value != "completed":
                                    stage_color = OVERDUE_COLOR
                                
                                cell_color = stage_color
                                break  # Один этап на день
                
                # Если задача создана в этот период
                if task.created_at:
                    created_date = task.created_at.date()
                    if period_start <= created_date <= period_end:
                        has_task_data = True
                        cell_text += f"🆕 Создана {created_date.strftime('%d.%m')}\n"
                
                # Если есть данные задачи, обновляем ячейку с гиперссылкой и форматированием
                if has_task_data:
                    cell_text = cell_text.strip()
                    task_url = f"{settings.FRONTEND_URL}/tasks/{task.id}"
                    # Экранируем кавычки в тексте для формулы
                    cell_text_escaped = cell_text.replace('"', '""')[:100]  # Ограничиваем длину и экранируем
                    hyperlink_formula = f'=HYPERLINK("{task_url}"; "{cell_text_escaped}")'
                    
                    requests.append({
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_idx,
                                "endRowIndex": row_idx + 1,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            },
                            "rows": [{
                                "values": [{
                                    "userEnteredValue": {
                                        "formulaValue": hyperlink_formula
                                    },
                                    "userEnteredFormat": {
                                        "backgroundColor": cell_color,
                                        "textFormat": {
                                            "bold": True,
                                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                                        }
                                    }
                                }]
                            }],
                            "fields": "userEnteredValue,userEnteredFormat"
                        }
                    })
        
        # Выполняем batch update (разбиваем на батчи по 50 запросов для избежания ошибок)
        batch_size = 50
        for i in range(0, len(requests), batch_size):
            batch = requests[i:i + batch_size]
            try:
                self.google_service.batch_update_sheet(
                    spreadsheet_id,
                    batch,
                    background=True
                )
            except Exception as e:
                logger.warning(f"Ошибка форматирования листа {sheet_name} (батч {i//batch_size + 1}): {e}")
    
    def _format_calendar_grid_sheet(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        tasks: List[Task],
        task_rows: Dict[str, int],
        date_columns: Dict[date, int],
        num_columns: int,
        num_rows: int,
        first_day: date,
        last_day: date
    ) -> List[Dict]:
        """Применить форматирование к календарной сетке"""
        from app.config import settings
        from datetime import datetime, timezone
        
        requests = []
        
        # Форматирование заголовка (первая строка)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_columns
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.2},
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "bold": True,
                            "fontSize": 11
                        },
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)"
            }
        })
        
        # Фиксируем первую строку и первый столбец
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 1,
                        "frozenColumnCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
            }
        })
        
        # Форматируем первую колонку (названия задач)
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": num_rows,
                    "startColumnIndex": 0,
                    "endColumnIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {
                            "bold": True
                        }
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)"
            }
        })
        
        # Форматируем ячейки с событиями (цвет по типу задачи)
        current_date = datetime.now(timezone.utc).date()
        
        for task_id, row_idx in task_rows.items():
            task = next((t for t in tasks if str(t.id) == task_id), None)
            if not task:
                continue
            
            # Цвет по типу задачи
            task_color = TASK_TYPE_COLORS.get(task.type, {"red": 0.9, "green": 0.9, "blue": 0.9})
            
            # Форматируем ячейки с дедлайнами и этапами
            for task_date, col_idx in date_columns.items():
                cell_requests = []
                
                # Проверяем дедлайн
                if task.due_date and task.due_date.date() == task_date:
                    cell_color = OVERDUE_COLOR if task_date < current_date else task_color
                    cell_requests.append({
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_idx,
                                "endRowIndex": row_idx + 1,
                                "startColumnIndex": col_idx,
                                "endColumnIndex": col_idx + 1
                            },
                            "rows": [{
                                "values": [{
                                    "userEnteredFormat": {
                                        "backgroundColor": cell_color
                                    }
                                }]
                            }],
                            "fields": "userEnteredFormat.backgroundColor"
                        }
                    })
                
                # Проверяем этапы
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date and stage.due_date.date() == task_date:
                            stage_color = STAGE_COLORS.get(stage.status_color, STAGE_COLORS["green"])
                            cell_requests.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id,
                                        "startRowIndex": row_idx,
                                        "endRowIndex": row_idx + 1,
                                        "startColumnIndex": col_idx,
                                        "endColumnIndex": col_idx + 1
                                    },
                                    "rows": [{
                                        "values": [{
                                            "userEnteredFormat": {
                                                "backgroundColor": stage_color
                                            }
                                        }]
                                    }],
                                    "fields": "userEnteredFormat.backgroundColor"
                                }
                            })
                            break  # Используем цвет последнего этапа
                
                requests.extend(cell_requests)
        
        return requests
    
    def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """
        Получить ID листа по имени
        
        Приоритет: OAuth (если доступен) → Service Account
        
        Returns:
            ID листа или None если не найден
        """
        # Сначала пробуем OAuth (т.к. таблица могла быть создана пользователем)
        oauth_service = self.google_service._get_oauth_sheets_service()
        if oauth_service:
            try:
                spreadsheet = oauth_service.spreadsheets().get(
                    spreadsheetId=spreadsheet_id,
                    fields='sheets.properties'
                ).execute()
                
                sheets_list = spreadsheet.get('sheets', [])
                logger.debug(f"📋 [OAuth] Листы в таблице: {[s['properties']['title'] for s in sheets_list]}")
                
                for sheet in sheets_list:
                    if sheet['properties']['title'] == sheet_name:
                        sheet_id = sheet['properties']['sheetId']
                        logger.debug(f"✅ [OAuth] Найден лист '{sheet_name}' с ID {sheet_id}")
                        return sheet_id
                
                logger.debug(f"⚠️ [OAuth] Лист '{sheet_name}' не найден")
            except Exception as oauth_e:
                logger.debug(f"⚠️ OAuth не смог получить листы: {oauth_e}")
        
        # Fallback: Service Account
        try:
            sheets_service = self.google_service._get_sheets_service(background=True)
            
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                fields='sheets.properties'
            ).execute()
            
            sheets_list = spreadsheet.get('sheets', [])
            logger.debug(f"📋 [SA] Листы в таблице: {[s['properties']['title'] for s in sheets_list]}")
            
            for sheet in sheets_list:
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    logger.debug(f"✅ [SA] Найден лист '{sheet_name}' с ID {sheet_id}")
                    return sheet_id
            
            logger.warning(f"⚠️ Лист '{sheet_name}' не найден")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения ID листа '{sheet_name}': {e}")
            return None
    
    async def sync_sheets_changes_to_db(
        self,
        spreadsheet_id: str,
        db: AsyncSession,
        sheet_name: str = "Общий"
    ) -> dict:
        """
        Синхронизировать изменения из Google Sheets обратно в БД
        
        Отслеживает изменения дедлайнов, статусов и этапов в таблице
        и обновляет БД при обнаружении расхождений
        
        Args:
            spreadsheet_id: ID таблицы
            db: Сессия БД
            sheet_name: Имя листа для синхронизации
        
        Returns:
            Словарь с результатами синхронизации
        """
        try:
            # Читаем данные из таблицы
            # Формат: первая строка - заголовки (дата + задачи)
            # Остальные строки - данные по дням
            
            sheet_data = self.google_service.read_sheet(
                f"{sheet_name}!A1:Z1000",
                sheet_id=spreadsheet_id,
                background=True
            )
            
            if not sheet_data or len(sheet_data) < 2:
                return {
                    "status": "skipped",
                    "reason": "no_data",
                    "sheet": sheet_name
                }
            
            headers = sheet_data[0]
            rows = sheet_data[1:]
            
            # Извлекаем ID задач из гиперссылок в заголовках
            task_ids = []
            task_columns = {}  # {task_id: column_index}
            
            for col_idx, header in enumerate(headers):
                if col_idx == 0:  # Пропускаем колонку с датами
                    continue
                
                # Пытаемся извлечь task_id из гиперссылки или текста
                # Формат гиперссылки: =HYPERLINK("https://best-pr-system.up.railway.app/tasks/{task_id}"; "...")
                import re
                if isinstance(header, str) and "tasks/" in header:
                    match = re.search(r'/tasks/([a-f0-9-]{36})', header)
                    if match:
                        task_id = match.group(1)
                        task_ids.append(task_id)
                        task_columns[task_id] = col_idx
            
            if not task_ids:
                return {
                    "status": "skipped",
                    "reason": "no_tasks_found",
                    "sheet": sheet_name
                }
            
            # Загружаем задачи из БД
            from app.models.task import Task
            from sqlalchemy import select, in_
            from uuid import UUID
            
            tasks_query = select(Task).where(Task.id.in_([UUID(tid) for tid in task_ids]))
            tasks_result = await db.execute(tasks_query)
            tasks = {str(task.id): task for task in tasks_result.scalars().all()}
            
            # Анализируем изменения
            changes = []
            
            for row in rows:
                if not row or len(row) < 2:
                    continue
                
                # Первая колонка - дата
                date_str = row[0] if row else None
                if not date_str:
                    continue
                
                # Парсим дату (формат: DD.MM или DD.MM.YYYY)
                try:
                    from datetime import datetime
                    if len(date_str.split('.')) == 2:
                        # Только день и месяц, используем текущий год
                        day, month = map(int, date_str.split('.'))
                        cell_date = date(datetime.now().year, month, day)
                    else:
                        day, month, year = map(int, date_str.split('.'))
                        cell_date = date(year, month, day)
                except (ValueError, IndexError):
                    continue
                
                # Проверяем каждую задачу в строке
                for task_id, col_idx in task_columns.items():
                    if col_idx >= len(row):
                        continue
                    
                    task = tasks.get(task_id)
                    if not task:
                        continue
                    
                    cell_value = row[col_idx] if col_idx < len(row) else ""
                    
                    # Проверяем дедлайн задачи
                    if task.due_date and task.due_date.date() != cell_date:
                        # Если в ячейке указан дедлайн, но дата не совпадает
                        if "Дедлайн" in str(cell_value):
                            # Обновляем дедлайн задачи
                            from datetime import datetime, timezone
                            new_due_date = datetime.combine(cell_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                            task.due_date = new_due_date
                            changes.append({
                                "type": "deadline",
                                "task_id": task_id,
                                "old_date": task.due_date.isoformat() if task.due_date else None,
                                "new_date": new_due_date.isoformat()
                            })
            
            # Сохраняем изменения в БД
            if changes:
                await db.commit()
                logger.info(f"✅ Синхронизировано {len(changes)} изменений из Sheets в БД")
            
            return {
                "status": "success",
                "sheet": sheet_name,
                "tasks_checked": len(task_ids),
                "changes": changes,
                "changes_count": len(changes)
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации изменений из Sheets: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "sheet": sheet_name
            }
