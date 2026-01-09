"""
Сервис синхронизации календаря с Google Sheets
Полная реализация с созданием таблицы, листов и заполнением данными
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from app.models.task import Task, TaskStage, TaskType
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
        scale: str = "days"  # Масштаб: "days", "weeks", "months"
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
            lambda: self._sync_to_sheets_sync(month, year, roles, tasks_list, first_day, last_day, statuses)
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
            
            # Синхронизируем общий календарь
            self._sync_general_calendar(
                spreadsheet_id, first_day, last_day, month, year, tasks, scale
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
        logger.info("Создание новой Google Sheets таблицы 'BEST PR System - Таймлайны'")
        bot_folder_id = self.drive_structure.get_bot_folder_id()
        sheets_doc = self.google_service.create_spreadsheet(
            "BEST PR System - Таймлайны",
            folder_id=bot_folder_id,
            background=True
        )
        
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
    
    def _sync_general_calendar(
        self,
        spreadsheet_id: str,
        first_day: date,
        last_day: date,
        month: int,
        year: int,
        tasks: List[Task],
        scale: str = "days"
    ):
        """Синхронизировать общий календарь
        
        Args:
            scale: Масштаб отображения - "days" (дни), "weeks" (недели), "months" (месяцы)
        """
        logger.info(f"Синхронизация общего календаря для {month}/{year} (масштаб: {scale}): {len(tasks)} задач")
        
        sheet_name = "Общий"
        
        # Генерируем периоды в зависимости от масштаба
        periods = self._generate_periods(first_day, last_day, scale)
        
        # Формируем данные для таблицы
        # Структура: Период | Задача 1 | Этапы задачи 1 | Задача 2 | Этапы задачи 2 | ...
        # Для простоты: каждая задача занимает одну колонку, этапы под ней
        
        # Сортируем задачи по дате создания
        sorted_tasks = sorted(tasks, key=lambda t: t.created_at or datetime.min)
        
        # Формируем заголовки
        period_label = {"days": "Дата", "weeks": "Неделя", "months": "Месяц"}.get(scale, "Период")
        headers = [period_label]
        task_columns = {}  # {task_id: column_index}
        col_idx = 1
        
        for task in sorted_tasks:
            headers.append(task.title[:50])  # Ограничиваем длину названия
            task_columns[str(task.id)] = col_idx
            col_idx += 1
        
        # Формируем данные по периодам
        rows = []
        for period_start, period_end, period_label_str in periods:
            row = [period_label_str]
            
            # Для каждой задачи проверяем, попадает ли она в этот период
            for task in sorted_tasks:
                cell_parts = []
                task_date = task.due_date.date() if task.due_date else None
                created_date = task.created_at.date() if task.created_at else None
                
                # Проверяем дедлайн задачи (попадает в период)
                if task_date and period_start <= task_date <= period_end:
                    cell_parts.append(f"📅 Дедлайн {task_date.strftime('%d.%m')}")
                
                # Проверяем этапы задачи (показываем все этапы в этом периоде)
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date:
                            stage_date = stage.due_date.date()
                            if period_start <= stage_date <= period_end:
                                status_icon = "✅" if stage.status.value == "completed" else "🔄" if stage.status.value == "in_progress" else "⏳"
                                color_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "purple": "🟣", "blue": "🔵"}.get(stage.status_color, "⚪")
                                cell_parts.append(f"{color_emoji} {status_icon} {stage.stage_name} ({stage_date.strftime('%d.%m')})")
                
                # Если задача создана в этот период
                if created_date and period_start <= created_date <= period_end:
                    cell_parts.append(f"🆕 Создана {created_date.strftime('%d.%m')}")
                
                # Объединяем все части через перенос строки для читаемости
                cell_value = "\n".join(cell_parts) if cell_parts else ""
                row.append(cell_value)
            
            rows.append(row)
        
        # Записываем данные в таблицу (используем batch для экономии запросов)
        range_name = f"{sheet_name}!A1"
        
        # Сначала записываем заголовки
        self.google_service.write_sheet(
            f"{sheet_name}!A1:{chr(64 + len(headers))}1",
            [headers],
            sheet_id=spreadsheet_id,
            background=True
        )
        
        # Затем данные
        if rows:
            self.google_service.write_sheet(
                f"{sheet_name}!A2:{chr(64 + len(headers))}{len(rows) + 1}",
                rows,
                sheet_id=spreadsheet_id,
                background=True
            )
        
        # Добавляем форматирование и гиперссылки
        self._format_sheet(
            spreadsheet_id,
            sheet_name,
            sorted_tasks,
            task_columns,
            days_in_month,
            first_day
        )
    
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
                
                # Проверяем дедлайн задачи (попадает в период)
                if task.due_date:
                    task_date = task.due_date.date()
                    if period_start <= task_date <= period_end:
                        # Красный цвет для просроченных дедлайнов
                        deadline_color = OVERDUE_COLOR if task_date < current_date else task_color
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
                                    "userEnteredFormat": {
                                        "backgroundColor": deadline_color,
                                        "textFormat": {
                                            "bold": True,
                                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                                        }
                                    }
                                }]
                            }],
                            "fields": "userEnteredFormat"
                        }
                    })
                
                # Форматируем ячейки с этапами
                if hasattr(task, '_stages_cache') and task._stages_cache:
                    for stage in task._stages_cache:
                        if stage.due_date:
                            stage_date = stage.due_date.date()
                            if period_start <= stage_date <= period_end:
                                # Цвет этапа из status_color
                                stage_color = STAGE_COLORS.get(stage.status_color, STAGE_COLORS["green"])
                                
                                # Если этап просрочен и не завершён - красный
                                if stage_date < current_date and stage.status.value != "completed":
                                    stage_color = OVERDUE_COLOR
                                
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
                                            "userEnteredFormat": {
                                                "backgroundColor": stage_color,
                                                "textFormat": {
                                                    "bold": stage.status.value == "completed",
                                                    "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
                                                }
                                            }
                                        }]
                                    }],
                                    "fields": "userEnteredFormat"
                                }
                            })
                            break  # Один этап на день
        
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
    
    def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        """Получить ID листа по имени"""
        try:
            # Используем GoogleService для получения sheets_service
            # Получаем sheets_service через внутренний метод
            sheets_service = self.google_service._get_sheets_service(background=True)
            
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            return 0
        except Exception as e:
            logger.warning(f"Ошибка получения ID листа {sheet_name}: {e}")
            return 0
    
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
