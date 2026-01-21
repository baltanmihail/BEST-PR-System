"""
Сервис синхронизации календаря занятости оборудования с Google Sheets
Полная реализация с логикой цветов (красный/жёлтый) как в BEST Channel Bot
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
import calendar as cal_lib
import re

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus
from app.models.user import User
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from typing import Optional

logger = logging.getLogger(__name__)


class EquipmentCalendarSync:
    """Сервис для создания/обновления календаря занятости оборудования"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.drive_structure = DriveStructureService()
    
    def _get_equipment_sheets_id(self) -> str:
        """Получить ID таблицы с оборудованием"""
        from app.services.drive_structure import DriveStructureService
        
        try:
            drive_structure = DriveStructureService()
            equipment_folder_id = drive_structure.get_equipment_folder_id()
            
            # Ищем таблицу в папке Equipment
            possible_names = ["Учёт оборудки", "Учёт оборудования", "Вся оборудка", "Оборудование"]
            for name in possible_names:
                sheets_id = self._find_sheets_in_folder(equipment_folder_id, name)
                if sheets_id:
                    return sheets_id
            
            # Fallback к настройкам
            from app.config import settings
            if settings.GOOGLE_EQUIPMENT_SHEETS_ID:
                return settings.GOOGLE_EQUIPMENT_SHEETS_ID
            
            # Последний fallback
            return "1gJ7muzAY00IK82QlMFRu4EaJdrwKw3nizjZ_I0nUe3s"
        except Exception as e:
            logger.error(f"Ошибка получения ID таблицы оборудования: {e}")
            from app.config import settings
            return settings.GOOGLE_EQUIPMENT_SHEETS_ID or "1gJ7muzAY00IK82QlMFRu4EaJdrwKw3nizjZ_I0nUe3s"
    
    def _find_sheets_in_folder(self, folder_id: str, name: str) -> Optional[str]:
        """Найти таблицу по имени в папке"""
        try:
            drive_service = self.google_service._get_drive_service(background=False)
            
            query = f"name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and '{folder_id}' in parents and trashed=false"
            
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]['id']
            
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска таблицы '{name}': {e}")
            return None
    
    async def create_or_update_calendar_sheet(
        self,
        db: AsyncSession,
        calendar_sheet_name: str = "Календарь занятости оборудования"
    ) -> bool:
        """
        Создаёт или обновляет лист календаря занятости оборудования
        
        Логика:
        - Красный цвет для одобренных заявок (по датам взятия и возврата)
        - Жёлтый цвет для заявок на рассмотрении
        - Отклонённые заявки не появляются на календаре
        - Номер заявки ставится в начале, конце и дате съёмки
        
        Args:
            db: Сессия БД
            calendar_sheet_name: Название листа календаря
        
        Returns:
            True если успешно, False при ошибке
        """
        try:
            sheets_id = self._get_equipment_sheets_id()
            
            # Получаем все заявки из БД
            requests_query = select(EquipmentRequest).where(
                cast(EquipmentRequest.status, String).in_([
                    EquipmentRequestStatus.PENDING.value,
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value
                ])
            )
            result = await db.execute(requests_query)
            requests = result.scalars().all()
            
            # Загружаем связанные данные
            for req in requests:
                equipment_result = await db.execute(
                    select(Equipment).where(Equipment.id == req.equipment_id)
                )
                req.equipment = equipment_result.scalar_one_or_none()
                
                user_result = await db.execute(
                    select(User).where(User.id == req.user_id)
                )
                req.user = user_result.scalar_one_or_none()
            
            # Получаем все оборудование из таблицы
            all_equipment = await self._get_equipment_list_from_sheets()
            
            if not all_equipment:
                logger.warning("Нет оборудования для календаря")
                return False
            
            # Собираем бронирования: {equipment_number: {date: {'app_num': str, 'status': str}}}
            equipment_bookings = {}
            
            logger.info(f"Обрабатываем {len(requests)} заявок")
            
            for req in requests:
                if not req.equipment:
                    continue
                
                # Получаем номер оборудования
                equipment_number = req.equipment.specs.get("number") if req.equipment.specs else None
                if not equipment_number:
                    # Пытаемся найти номер в таблице
                    equipment_number = await self._find_equipment_number(req.equipment.name)
                
                if not equipment_number:
                    logger.warning(f"Не удалось найти номер оборудования для заявки {req.id}")
                    continue
                
                # Статус заявки для календаря
                status_map = {
                    EquipmentRequestStatus.PENDING: "На рассмотрении",
                    EquipmentRequestStatus.APPROVED: "Одобрено",
                    EquipmentRequestStatus.ACTIVE: "Одобрено",  # Активные тоже одобренные
                }
                status_ru = status_map.get(req.status, "На рассмотрении")
                
                # Получаем номер заявки (используем короткий UUID)
                app_num = str(req.id)[:8]
                
                # Получаем дату съёмки (из задачи, если есть)
                shooting_date = None
                if req.task_id:
                    from app.models.task import Task
                    task_result = await db.execute(
                        select(Task).where(Task.id == req.task_id)
                    )
                    task = task_result.scalar_one_or_none()
                    if task and task.due_date:
                        shooting_date = task.due_date.date()
                
                # Добавляем в календарь
                if equipment_number not in equipment_bookings:
                    equipment_bookings[equipment_number] = {}
                
                # Добавляем все даты периода аренды
                current_date = req.start_date
                dates_added = 0
                shooting_date_added = False
                
                while current_date <= req.end_date:
                    if current_date == req.start_date:
                        # Первая дата периода (дата выдачи) - добавляем номер заявки
                        equipment_bookings[equipment_number][current_date] = {
                            'app_num': app_num,
                            'status': status_ru
                        }
                    elif current_date == req.end_date:
                        # Последняя дата периода (дата возврата) - тоже добавляем номер заявки
                        equipment_bookings[equipment_number][current_date] = {
                            'app_num': app_num,
                            'status': status_ru
                        }
                    elif shooting_date and current_date == shooting_date:
                        # Дата съёмки внутри периода - добавляем номер заявки
                        equipment_bookings[equipment_number][current_date] = {
                            'app_num': app_num,
                            'status': status_ru
                        }
                        shooting_date_added = True
                    else:
                        # Промежуточные даты - без номера заявки
                        if current_date not in equipment_bookings[equipment_number]:
                            equipment_bookings[equipment_number][current_date] = {
                                'app_num': '',
                                'status': status_ru
                            }
                    dates_added += 1
                    current_date += timedelta(days=1)
                
                # Добавляем дату съёмки отдельно, если она вне диапазона
                if shooting_date and not shooting_date_added:
                    equipment_bookings[equipment_number][shooting_date] = {
                        'app_num': app_num,
                        'status': status_ru
                    }
            
            logger.info(f"Собрано бронирований для {len(equipment_bookings)} единиц оборудования")
            
            # Находим минимальную и максимальную даты
            all_dates = []
            for eq_bookings in equipment_bookings.values():
                all_dates.extend(eq_bookings.keys())
            
            # Период: от минимальной даты до +6 месяцев от максимальной
            today = date.today()
            if all_dates:
                min_date = min(all_dates)
                max_date = max(all_dates)
                start_month = min_date.replace(day=1)
                end_base = max_date
            else:
                start_month = today.replace(day=1)
                end_base = today
            
            # Вычисляем конечную дату
            end_month_date = end_base.replace(day=1)
            for _ in range(5):
                if end_month_date.month == 12:
                    end_month_date = end_month_date.replace(year=end_month_date.year + 1, month=1, day=1)
                else:
                    end_month_date = end_month_date.replace(month=end_month_date.month + 1, day=1)
            
            days_in_last_month = cal_lib.monthrange(end_month_date.year, end_month_date.month)[1]
            end_month = end_month_date.replace(day=days_in_last_month)
            
            logger.info(f"Период календаря: {start_month.strftime('%d.%m.%Y')} - {end_month.strftime('%d.%m.%Y')}")
            
            # Генерируем все даты периода
            all_dates_list = []
            current = start_month
            while current <= end_month:
                all_dates_list.append(current)
                current += timedelta(days=1)
            
            # Получаем или создаём лист календаря
            sheet_id = await self._get_or_create_calendar_sheet(sheets_id, calendar_sheet_name)
            
            # Формируем заголовки календаря
            await self._update_calendar_headers(sheets_id, sheet_id, start_month, end_month, all_dates_list)
            
            # Обновляем данные оборудования
            await self._update_calendar_data(
                sheets_id,
                sheet_id,
                all_equipment,
                equipment_bookings,
                all_dates_list
            )
            
            # Применяем форматирование (цвета)
            await self._apply_calendar_formatting(
                sheets_id,
                sheet_id,
                all_equipment,
                equipment_bookings,
                all_dates_list
            )
            
            logger.info("✅ Календарь занятости оборудования обновлён")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания/обновления календаря: {e}", exc_info=True)
            return False
    
    EQUIPMENT_SHEET = "Вся оборудка"  # или "Учёт оборудки"
    
    async def _get_equipment_list_from_sheets(self) -> List[Dict]:
        """Получить список оборудования из таблицы"""
        try:
            sheets_id = self._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                f"{self.EQUIPMENT_SHEET}!A:D",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return []
            
            equipment_list = []
            for row in values[1:]:
                if len(row) < 2:
                    continue
                
                number = row[0].strip() if len(row) > 0 else ""
                name = row[1].strip() if len(row) > 1 else ""
                
                if number and name:
                    equipment_list.append({
                        'number': number,
                        'name': name
                    })
            
            return equipment_list
            
        except Exception as e:
            logger.error(f"Ошибка получения списка оборудования: {e}")
            return []
    
    async def _find_equipment_number(self, equipment_name: str) -> Optional[str]:
        """Найти номер оборудования по названию"""
        equipment_list = await self._get_equipment_list_from_sheets()
        for eq in equipment_list:
            if eq['name'] == equipment_name:
                return eq['number']
        return None
    
    async def _get_or_create_calendar_sheet(self, sheets_id: str, sheet_name: str) -> int:
        """Получить или создать лист календаря"""
        try:
            sheets_service = self.google_service._get_sheets_service(background=False)
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=sheets_id
            ).execute()
            
            # Ищем существующий лист
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            # Создаём новый лист
            result = self.google_service.batch_update_sheet(
                spreadsheet_id=sheets_id,
                requests=[{
                    "addSheet": {
                        "properties": {
                            "title": sheet_name
                        }
                    }
                }],
                background=False
            )
            
            # Получаем ID созданного листа
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=sheets_id
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            return 0
            
        except Exception as e:
            logger.error(f"Ошибка получения/создания листа календаря: {e}")
            return 0
    
    async def _update_calendar_headers(
        self,
        sheets_id: str,
        sheet_id: int,
        start_month: date,
        end_month: date,
        all_dates: List[date]
    ):
        """Обновить заголовки календаря"""
        # Строка 1: Период
        month_names_ru = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        period_str = f"{month_names_ru.get(start_month.month, start_month.strftime('%B'))} {start_month.year} - {month_names_ru.get(end_month.month, end_month.strftime('%B'))} {end_month.year}"
        
        # Строка 2: Числа дней
        dates_row = [""]  # Первая колонка пустая
        for d in all_dates:
            dates_row.append(d.strftime("%d"))
        
        # Строка 3: Дни недели
        weekdays_ru = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        weekdays_row = [""]
        for d in all_dates:
            weekday_idx = d.weekday()  # 0 = Monday
            weekdays_row.append(weekdays_ru[weekday_idx])
        
        # Строка 4: Пустая
        empty_row = [""] * (len(all_dates) + 1)
        
        headers = [[period_str], dates_row, weekdays_row, empty_row]
        
        # Записываем заголовки
        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": 4,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(all_dates) + 1
                    },
                    "rows": [
                        {"values": [{"userEnteredValue": {"stringValue": str(cell)}} for cell in row]}
                        for row in headers
                    ],
                    "fields": "userEnteredValue"
                }
            }],
            background=False
        )
    
    async def _update_calendar_data(
        self,
        sheets_id: str,
        sheet_id: int,
        all_equipment: List[Dict],
        equipment_bookings: Dict[str, Dict[date, Dict]],
        all_dates: List[date]
    ):
        """Обновить данные календаря (номера заявок)"""
        # Сортируем оборудование по номеру
        sorted_equipment = sorted(all_equipment, key=lambda x: int(x['number']) if x['number'].isdigit() else 999)
        
        # Формируем строки данных
        equipment_rows = []
        for eq in sorted_equipment:
            eq_num = eq['number']
            row = [eq_num]
            
            bookings = equipment_bookings.get(eq_num, {})
            
            for d in all_dates:
                if d in bookings:
                    booking_info = bookings[d]
                    app_num = booking_info.get('app_num', '')
                    row.append(app_num)
                else:
                    row.append('')
            
            equipment_rows.append(row)
        
        # Записываем данные (начиная с 5-й строки)
        if equipment_rows:
            start_row = 5
            end_row = start_row + len(equipment_rows) - 1
            
            self.google_service.batch_update_sheet(
                spreadsheet_id=sheets_id,
                requests=[{
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": start_row - 1,
                            "endRowIndex": end_row,
                            "startColumnIndex": 0,
                            "endColumnIndex": len(all_dates) + 1
                        },
                        "rows": [
                            {"values": [{"userEnteredValue": {"stringValue": str(cell)}} for cell in row]}
                            for row in equipment_rows
                        ],
                        "fields": "userEnteredValue"
                    }
                }],
                background=False
            )
    
    async def _apply_calendar_formatting(
        self,
        sheets_id: str,
        sheet_id: int,
        all_equipment: List[Dict],
        equipment_bookings: Dict[str, Dict[date, Dict]],
        all_dates: List[date]
    ):
        """Применить форматирование календаря (цвета)"""
        requests = []
        
        # Сортируем оборудование по номеру
        sorted_equipment = sorted(all_equipment, key=lambda x: int(x['number']) if x['number'].isdigit() else 999)
        
        # Создаём множество ячеек для окрашивания
        cells_to_color = {}  # {(row, col): color}
        
        for eq_idx, eq in enumerate(sorted_equipment):
            eq_num = eq['number']
            equipment_row = 5 + eq_idx  # Начиная с 5-й строки
            
            bookings = equipment_bookings.get(eq_num, {})
            
            for date_idx, d in enumerate(all_dates):
                date_col = date_idx + 2  # Начиная со столбца B
                
                if d in bookings:
                    booking_info = bookings[d]
                    status = booking_info.get('status', '')
                    
                    if status == 'На рассмотрении':
                        color = {'red': 1.0, 'green': 1.0, 'blue': 0.0}  # Жёлтый
                        cells_to_color[(equipment_row, date_col)] = color
                    elif status == 'Одобрено':
                        color = {'red': 1.0, 'green': 0.0, 'blue': 0.0}  # Красный
                        cells_to_color[(equipment_row, date_col)] = color
        
        # Группируем ячейки по цветам для оптимизации
        yellow_cells = []
        red_cells = []
        
        for (row, col), color in cells_to_color.items():
            if color['blue'] == 0.0 and color['green'] == 1.0:  # Жёлтый
                yellow_cells.append((row, col))
            elif color['blue'] == 0.0 and color['green'] == 0.0:  # Красный
                red_cells.append((row, col))
        
        # Создаём запросы на форматирование (группируем по строкам)
        def add_color_requests(cells, color):
            if not cells:
                return
            
            # Группируем по строкам
            rows_dict = {}
            for row, col in cells:
                if row not in rows_dict:
                    rows_dict[row] = []
                rows_dict[row].append(col)
            
            # Создаём запросы для каждой строки
            for row, cols in rows_dict.items():
                sorted_cols = sorted(cols)
                
                # Группируем последовательные столбцы
                start_col = sorted_cols[0]
                end_col = sorted_cols[0]
                
                for col in sorted_cols[1:]:
                    if col == end_col + 1:
                        end_col = col
                    else:
                        # Добавляем запрос для диапазона
                        requests.append({
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": row - 1,
                                    "endRowIndex": row,
                                    "startColumnIndex": start_col - 1,
                                    "endColumnIndex": end_col
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "backgroundColor": color
                                    }
                                },
                                "fields": "userEnteredFormat.backgroundColor"
                            }
                        })
                        start_col = col
                        end_col = col
                
                # Добавляем последний диапазон
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": row - 1,
                            "endRowIndex": row,
                            "startColumnIndex": start_col - 1,
                            "endColumnIndex": end_col
                        },
                        "cell": {
                            "userEnteredFormat": {
                                "backgroundColor": color
                            }
                        },
                        "fields": "userEnteredFormat.backgroundColor"
                    }
                })
        
        # Добавляем запросы для жёлтых и красных ячеек
        add_color_requests(yellow_cells, {'red': 1.0, 'green': 1.0, 'blue': 0.0})
        add_color_requests(red_cells, {'red': 1.0, 'green': 0.0, 'blue': 0.0})
        
        # Фиксируем первую строку и первый столбец
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": 4,
                        "frozenColumnCount": 1
                    }
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
            }
        })
        
        # Применяем форматирование батчами
        if requests:
            batch_size = 100
            for i in range(0, len(requests), batch_size):
                batch = requests[i:i + batch_size]
                self.google_service.batch_update_sheet(
                    spreadsheet_id=sheets_id,
                    requests=batch,
                    background=False
                )
            
            logger.info(f"✅ Применено форматирование: {len(yellow_cells)} жёлтых, {len(red_cells)} красных ячеек")
