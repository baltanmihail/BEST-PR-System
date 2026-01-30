"""
Сервис синхронизации оборудования с Google Sheets
Полная реализация с учётом структуры таблицы BEST Channel Bot
"""
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Set, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import re
from collections import defaultdict

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus, EquipmentStatus
from app.models.user import User
from app.config import settings
from app.services.google_service import GoogleService
# from app.services.drive_structure import DriveStructureService  # Moved to __init__ to avoid circular imports

logger = logging.getLogger(__name__)


class EquipmentSheetsSync:
    """Синхронизация оборудования с Google Sheets"""
    
    # ID таблицы с оборудованием (будет найден в папке Equipment или из настроек)
    EQUIPMENT_SHEETS_ID = None  # Будет определён при первом использовании
    
    # Названия листов
    EQUIPMENT_SHEET = "Вся оборудка"  # или "Учёт оборудки"
    REQUESTS_SHEET = "Заявки на оборудку"
    HISTORY_SHEET = "История оборудки"
    CALENDAR_SHEET = "Календарь занятости оборудования"
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        # Импортируем здесь, чтобы избежать циклического импорта
        from app.services.drive_structure import DriveStructureService
        self.drive_structure = DriveStructureService()
    
    def _get_equipment_sheets_id(self) -> str:
        """Получить ID таблицы с оборудованием (найти в папке Equipment или использовать из настроек)"""
        if self.EQUIPMENT_SHEETS_ID:
            return self.EQUIPMENT_SHEETS_ID
        
        # Если задан в настройках, используем его
        if settings.GOOGLE_EQUIPMENT_SHEETS_ID:
            self.EQUIPMENT_SHEETS_ID = settings.GOOGLE_EQUIPMENT_SHEETS_ID
            return self.EQUIPMENT_SHEETS_ID
        
        # Ищем таблицу в папке Equipment
        try:
            equipment_folder_id = self.drive_structure.get_equipment_folder_id()
            
            # Ищем таблицу с оборудованием (может быть несколько вариантов названий)
            possible_names = [
                "Учёт оборудки",
                "Учёт оборудования",
                "Вся оборудка",
                "Оборудование"
            ]
            
            for name in possible_names:
                sheets_id = self._find_sheets_in_folder(equipment_folder_id, name)
                if sheets_id:
                    logger.info(f"✅ Найдена таблица оборудования '{name}': {sheets_id}")
                    self.EQUIPMENT_SHEETS_ID = sheets_id
                    return sheets_id
            
            logger.warning("⚠️ Таблица оборудования не найдена в папке Equipment")
            # Fallback на старый ID (если таблица ещё не перенесена)
            self.EQUIPMENT_SHEETS_ID = "1gJ7muzAY00IK82QlMFRu4EaJdrwKw3nizjZ_I0nUe3s"
            return self.EQUIPMENT_SHEETS_ID
            
        except Exception as e:
            logger.error(f"Ошибка поиска таблицы оборудования: {e}")
            # Fallback на старый ID
            self.EQUIPMENT_SHEETS_ID = "1gJ7muzAY00IK82QlMFRu4EaJdrwKw3nizjZ_I0nUe3s"
            return self.EQUIPMENT_SHEETS_ID
    
    def _find_sheets_in_folder(self, folder_id: str, name: str) -> Optional[str]:
        """Найти таблицу по имени в папке"""
        try:
            service = self.google_service._get_drive_service(background=False)
            
            query = f"name='{name}' and mimeType='application/vnd.google-apps.spreadsheet' and '{folder_id}' in parents and trashed=false"
            
            results = service.files().list(
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
    
    async def sync_equipment_from_sheets(
        self,
        db: AsyncSession
    ) -> dict:
        """
        Синхронизировать оборудование из Google Sheets в БД
        
        Читает список оборудования из листа "Вся оборудка" и создаёт/обновляет записи в БД
        
        Returns:
            Словарь с результатами синхронизации
        """
        try:
            # Читаем лист "Вся оборудка"
            values = self.google_service.read_sheet(
                f"{self.EQUIPMENT_SHEET}!A:D",
                sheet_id=self._get_equipment_sheets_id(), # Используем метод для получения ID
                background=True
            )
            
            if not values or len(values) < 2:
                return {
                    "status": "skipped",
                    "reason": "no_data",
                    "synced": 0
                }
            
            synced_count = 0
            updated_count = 0
            created_count = 0
            
            # Обрабатываем строки (пропускаем заголовок)
            for row in values[1:]:
                if len(row) < 2:
                    continue
                
                # Колонки: A=Номер, B=Оборудование, C=Фото (URL), D=Статус
                number = row[0].strip() if len(row) > 0 else ""
                name = row[1].strip() if len(row) > 1 else ""
                photo_url = row[2].strip() if len(row) > 2 else ""
                status_ru = row[3].strip() if len(row) > 3 else "На складе"
                
                if not name:
                    continue
                
                # Конвертируем статус
                status_map = {
                    "На складе": EquipmentStatus.AVAILABLE,
                    "Выдано": EquipmentStatus.RENTED,
                    "В ремонте": EquipmentStatus.MAINTENANCE,
                    "Сломано": EquipmentStatus.BROKEN
                }
                status = status_map.get(status_ru, EquipmentStatus.AVAILABLE)
                
                # Определяем категорию по названию (можно улучшить)
                category = self._detect_category(name)
                # Конвертируем категорию в lowercase для соответствия enum в БД
                category = category.lower() if category else "other"
                
                # Проверяем, есть ли уже в базе (по названию)
                result = await db.execute(
                    select(Equipment).where(Equipment.name == name)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Обновляем статус и номер (если есть поле для номера)
                    existing.status = status
                    if number and not existing.specs:
                        existing.specs = {"number": number}
                    elif number and existing.specs:
                        existing.specs["number"] = number
                    updated_count += 1
                else:
                    # Создаём новое
                    new_equipment = Equipment(
                        name=name,
                        category=category,
                        status=status,
                        quantity=1,  # По умолчанию 1, можно уточнить из таблицы
                        specs={"number": number, "photo_url": photo_url} if number or photo_url else None
                    )
                    db.add(new_equipment)
                    created_count += 1
                
                synced_count += 1
            
            await db.commit()
            logger.info(f"✅ Синхронизировано оборудования из Google Sheets: создано {created_count}, обновлено {updated_count}, всего {synced_count}")
            
            return {
                "status": "success",
                "synced": synced_count,
                "created": created_count,
                "updated": updated_count
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации оборудования из Sheets: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "synced": 0
            }
    
    def _detect_category(self, name: str) -> str:
        """Определить категорию оборудования по названию"""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ["камера", "camera", "видеокамера"]):
            return "camera"
        elif any(word in name_lower for word in ["объектив", "lens", "линза"]):
            return "lens"
        elif any(word in name_lower for word in ["свет", "lighting", "ламп", "софтбокс"]):
            return "lighting"
        elif any(word in name_lower for word in ["микрофон", "audio", "аудио", "рекордер"]):
            return "audio"
        elif any(word in name_lower for word in ["штатив", "tripod", "стойка"]):
            return "tripod"
        elif any(word in name_lower for word in ["накопитель", "storage", "ssd", "карта памяти"]):
            return "storage"
        elif any(word in name_lower for word in ["аксессуар", "accessories", "переходник", "кабель"]):
            return "accessories"
        else:
            return "other"
    
    async def log_equipment_request(
        self,
        db: AsyncSession,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User
    ) -> dict:
        """
        Записать заявку на оборудование в лист "Заявки на оборудку"
        """
        try:
            # Находим номер строки оборудования в листе "Вся оборудка"
            equipment_row = await self._find_equipment_row(equipment.name)
            
            # Формируем формулу для ссылки на оборудование
            equipment_formula = f"='{self.EQUIPMENT_SHEET}'!C{equipment_row}" if equipment_row else equipment.name
            
            # Статус заявки
            status_map = {
                EquipmentRequestStatus.PENDING: "На рассмотрении",
                EquipmentRequestStatus.APPROVED: "Одобрено",
                EquipmentRequestStatus.REJECTED: "Отклонено",
                EquipmentRequestStatus.ACTIVE: "Выдано",
                EquipmentRequestStatus.COMPLETED: "Возвращено",
                EquipmentRequestStatus.CANCELLED: "Отменено"
            }
            status_ru = status_map.get(request.status, "На рассмотрении")
            
            # Формируем строку "Кто берёт"
            username = user.telegram_username or ""
            full_name = user.full_name or f"{user.first_name} {user.last_name}".strip()
            
            if username:
                who_takes = f"https://t.me/{username.lstrip('@')} - {full_name}"
            else:
                who_takes = full_name
            
            # Получаем название мероприятия из задачи (если есть)
            shooting_name = ""
            if request.task_id:
                from app.models.task import Task
                task_result = await db.execute(
                    select(Task).where(Task.id == request.task_id)
                )
                task = task_result.scalar_one_or_none()
                if task:
                    shooting_name = task.title
            
            # Получаем номер заявки (максимальный + 1)
            application_number = await self._get_next_application_number()
            
            # Данные для записи
            current_date = datetime.now().strftime("%d.%m.%Y")
            row_data = [
                [
                    str(application_number),  # Номер заявки
                    current_date,  # Дата запроса
                    "",  # Время обработки (формула, пусто)
                    who_takes,  # Кто берёт
                    equipment_formula,  # Что берёт (формула)
                    shooting_name,  # Название мероприятия
                    request.start_date.strftime("%d.%m.%Y"),  # Дата выдачи
                    request.start_date.strftime("%d.%m.%Y"),  # Дата съёмки (можно уточнить)
                    request.end_date.strftime("%d.%m.%Y"),  # Дата возврата
                    "",  # Комментарий (можно добавить поле purpose)
                    status_ru  # Статус
                ]
            ]
            
            # Получаем ID таблицы
            sheets_id = self._get_equipment_sheets_id()
            
            # Записываем в Google Sheets
            self.google_service.append_to_sheet(
                range_name=f"{self.REQUESTS_SHEET}!A:K",
                values=row_data,
                sheet_id=sheets_id,
                background=True
            )
            
            # Обновляем формулу в ячейке "Что берёт" (если нужно)
            if equipment_row:
                # Находим номер последней строки
                all_values = self.google_service.read_sheet(
                    f"{self.REQUESTS_SHEET}!A:A",
                    sheet_id=self.EQUIPMENT_SHEETS_ID,
                    background=True
                )
                last_row = len(all_values) if all_values else 1
                
                # Записываем формулу через batch update
                self.google_service.batch_update_sheet(
                    self._get_equipment_sheets_id(),
                    [{
                        "updateCells": {
                            "range": {
                                "sheetId": self._get_sheet_id(self.REQUESTS_SHEET),
                                "startRowIndex": last_row - 1,
                                "endRowIndex": last_row,
                                "startColumnIndex": 4,  # Колонка E (5-я)
                                "endColumnIndex": 5
                            },
                            "rows": [{
                                "values": [{
                                    "userEnteredValue": {
                                        "formulaValue": equipment_formula
                                    }
                                }]
                            }],
                            "fields": "userEnteredValue"
                        }
                    }],
                    background=True
                )
            
            logger.info(f"✅ Заявка {request.id} (№{application_number}) записана в Google Sheets")
            
            return {
                "status": "success",
                "request_id": str(request.id),
                "application_number": application_number
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка записи заявки в Google Sheets: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "request_id": str(request.id)
            }
    
    async def update_request_status(
        self,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User,
        new_status: EquipmentRequestStatus
    ) -> dict:
        """
        Обновить статус заявки в листе "Заявки на оборудку"
        И добавить запись в "История оборудки" при одобрении
        """
        try:
            # Обновляем статус заявки
            await self._update_request_status_in_sheets(request.id, new_status)
            
            # Если заявка одобрена или активна, добавляем в историю и обновляем календарь
            if new_status in [EquipmentRequestStatus.APPROVED, EquipmentRequestStatus.ACTIVE]:
                await self._log_to_history(request, equipment, user)
                # Обновляем календарь (нужна сессия БД для получения всех заявок)
                from app.database import get_db
                async for db_session in get_db():
                    try:
                        await self._update_calendar(request, equipment, db_session)
                    finally:
                        pass
                    break
            
            logger.info(f"✅ Статус заявки {request.id} обновлён в Google Sheets: {new_status.value}")
            
            return {
                "status": "success",
                "request_id": str(request.id),
                "new_status": new_status.value
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статуса заявки в Google Sheets: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "request_id": str(request.id)
            }
    
    async def _find_equipment_row(self, equipment_name: str) -> Optional[int]:
        """Найти номер строки оборудования в листе 'Вся оборудка'"""
        try:
            # Читаем лист "Вся оборудка"
            values = self.google_service.read_sheet(
                f"{self.EQUIPMENT_SHEET}!A:D",
                sheet_id=self._get_equipment_sheets_id(), # Используем метод для получения ID
                background=True
            )
            
            if not values or len(values) < 2:
                return None
            
            # Ищем строку с нужным оборудованием (колонка B = название)
            for i, row in enumerate(values[1:], start=2):  # Пропускаем заголовок, начинаем с 2
                if len(row) > 1 and row[1].strip() == equipment_name.strip():
                    return i
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска оборудования '{equipment_name}': {e}")
            return None
    
    async def _get_next_application_number(self) -> int:
        """Получить следующий номер заявки"""
        try:
            # Читаем все заявки
            values = self.google_service.read_sheet(
                f"{self.REQUESTS_SHEET}!A:A",
                sheet_id=self._get_equipment_sheets_id(), # Используем метод для получения ID
                background=True
            )
            
            if not values or len(values) < 2:
                return 1
            
            # Ищем максимальный номер в первой колонке
            max_num = 0
            for row in values[1:]:  # Пропускаем заголовок
                if row and row[0].strip().isdigit():
                    max_num = max(max_num, int(row[0].strip()))
            
            return max_num + 1
            
        except Exception as e:
            logger.warning(f"Ошибка получения номера заявки: {e}")
            return 1
    
    async def _update_request_status_in_sheets(
        self,
        request_id: str,
        new_status: EquipmentRequestStatus
    ):
        """Обновить статус заявки в листе 'Заявки на оборудку'"""
        try:
            # Получаем ID таблицы
            sheets_id = self._get_equipment_sheets_id()
            
            # Читаем все заявки
            values = self.google_service.read_sheet(
                f"{self.REQUESTS_SHEET}!A:K",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return
            
            # Статус заявки
            status_map = {
                EquipmentRequestStatus.PENDING: "На рассмотрении",
                EquipmentRequestStatus.APPROVED: "Одобрено",
                EquipmentRequestStatus.REJECTED: "Отклонено",
                EquipmentRequestStatus.ACTIVE: "Выдано",
                EquipmentRequestStatus.COMPLETED: "Возвращено",
                EquipmentRequestStatus.CANCELLED: "Отменено"
            }
            status_ru = status_map.get(new_status, "На рассмотрении")
            
            # Ищем строку с нужной заявкой
            # (реализацию поиска нужно доработать, пока пропускаем)
            pass
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса заявки: {e}")
    
    async def _log_to_history(
        self,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User
    ):
        """Добавить запись в 'История оборудки'"""
        try:
            # Находим номер оборудования
            equipment_number = equipment.specs.get("number") if equipment.specs else None
            if not equipment_number:
                equipment_row = await self._find_equipment_row(equipment.name)
                equipment_number = equipment_row if equipment_row else "?"
            
            row_data = [
                [
                    str(equipment_number),
                    equipment.name,
                    user.full_name or f"{user.first_name} {user.last_name}".strip(),
                    request.start_date.strftime("%d.%m.%Y"),
                    request.end_date.strftime("%d.%m.%Y"),
                    ""  # Комментарий
                ]
            ]
            
            # Получаем ID таблицы
            sheets_id = self._get_equipment_sheets_id()
            
            self.google_service.append_to_sheet(
                range_name=f"{self.HISTORY_SHEET}!A:F",
                values=row_data,
                sheet_id=sheets_id,
                background=True
            )
            
        except Exception as e:
            logger.error(f"Ошибка записи в историю: {e}")
    
    async def _update_calendar(
        self,
        request: EquipmentRequest,
        equipment: Equipment,
        db: Optional[AsyncSession] = None
    ):
        """
        Обновить календарь занятости оборудования
        """
        try:
            from app.services.equipment_calendar_sync import EquipmentCalendarSync
            
            calendar_sync = EquipmentCalendarSync(self.google_service)
            
            # Если есть сессия БД, используем её, иначе создаём новую
            if db:
                await calendar_sync.create_or_update_calendar_sheet(db)
            else:
                # Создаём новую сессию для обновления календаря
                from app.database import get_db
                async for db_session in get_db():
                    try:
                        await calendar_sync.create_or_update_calendar_sheet(db_session)
                    finally:
                        pass
                    break
            
            logger.info(f"✅ Календарь занятости обновлён для заявки {request.id}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления календаря: {e}", exc_info=True)
            # Упрощенная логика (удалена, чтобы не дублировать код)
            pass
    
    async def get_booked_dates_from_calendar(
        self,
        equipment_number: str,
        use_cache: bool = True
    ) -> Set[date]:
        """
        Получить забронированные даты для оборудования из календаря
        """
        try:
            # Читаем календарь
            calendar_data = self.google_service.read_sheet(
                f"{self.CALENDAR_SHEET}!A:Z",
                sheet_id=self._get_equipment_sheets_id(), # Используем метод для получения ID
                background=not use_cache
            )
            
            if not calendar_data or len(calendar_data) < 5:
                return set()
            
            # Парсим даты из строки 2
            dates_row = calendar_data[1] if len(calendar_data) > 1 else []
            col_to_date = {}
            current_month = datetime.now().month
            current_year = datetime.now().year
            prev_day = 0
            
            for col_idx in range(1, len(dates_row)):
                day_str = dates_row[col_idx].strip()
                if day_str and day_str.isdigit():
                    try:
                        day = int(day_str)
                        if day < prev_day:
                            current_month += 1
                            if current_month > 12:
                                current_month = 1
                                current_year += 1
                        
                        try:
                            cal_date = date(current_year, current_month, day)
                            col_to_date[col_idx] = cal_date
                            prev_day = day
                        except ValueError:
                            continue
                    except ValueError:
                        continue
            
            # Находим строку с оборудованием
            booked_dates = set()
            
            for row in calendar_data[4:]:  # Начиная с 5-й строки
                if row and len(row) > 0 and str(row[0]).strip() == str(equipment_number):
                    # Находим занятые даты (ячейки с номерами заявок)
                    for col_idx in range(1, len(row)):
                        cell_value = str(row[col_idx]).strip()
                        if cell_value and col_idx in col_to_date:
                            booked_dates.add(col_to_date[col_idx])
                    break
            
            return booked_dates
            
        except Exception as e:
            logger.error(f"Ошибка получения занятых дат из календаря: {e}")
            return set()
    
    def _get_sheet_id(self, sheet_name: str) -> int:
        """Получить ID листа по имени"""
        try:
            # Получаем ID таблицы
            sheets_id = self._get_equipment_sheets_id()
            
            sheets_service = self.google_service._get_sheets_service(background=True)
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=sheets_id
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            return 0
        except Exception as e:
            logger.warning(f"Ошибка получения ID листа {sheet_name}: {e}")
            return 0
