"""
Сервис синхронизации таймлайна занятости оборудования с Google Sheets
Аналогично таймлайну задач, но для оборудования
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus, EquipmentStatus
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from app.config import settings
import calendar as cal_lib

logger = logging.getLogger(__name__)

# Цвета для статусов заявок
REQUEST_STATUS_COLORS = {
    EquipmentRequestStatus.PENDING: {"red": 1.0, "green": 0.843, "blue": 0.0},  # Жёлтый
    EquipmentRequestStatus.APPROVED: {"red": 0.298, "green": 0.686, "blue": 0.314},  # Зелёный
    EquipmentRequestStatus.ACTIVE: {"red": 0.129, "green": 0.588, "blue": 0.953},  # Синий
    EquipmentRequestStatus.COMPLETED: {"red": 0.5, "green": 0.5, "blue": 0.5},  # Серый
    EquipmentRequestStatus.REJECTED: {"red": 0.956, "green": 0.262, "blue": 0.212},  # Красный
    EquipmentRequestStatus.CANCELLED: {"red": 0.956, "green": 0.262, "blue": 0.212},  # Красный
}

# Цвет для просроченных дедлайнов
OVERDUE_COLOR = {"red": 0.956, "green": 0.262, "blue": 0.212}  # #F44336 красный


class EquipmentTimelineSyncService:
    """Сервис для синхронизации таймлайна занятости оборудования с Google Sheets"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.drive_structure = DriveStructureService()
        self.timeline_sheets_id = None
    
    async def _get_or_create_timeline_sheets(self, db: AsyncSession) -> str:
        """
        Получить или создать таблицу с таймлайнами занятости оборудования
        
        Returns:
            ID таблицы Google Sheets
        """
        if self.timeline_sheets_id:
            return self.timeline_sheets_id
        
        # Ищем таблицу в папке Equipment
        equipment_folder_id = self.drive_structure.get_equipment_folder_id()
        
        # Ищем существующую таблицу
        timeline_name = "BEST PR System - Таймлайн занятости оборудования"
        sheets_id = await self._find_sheets_in_folder(equipment_folder_id, timeline_name)
        
        if sheets_id:
            logger.info(f"✅ Найдена существующая таблица таймлайна занятости: {sheets_id}")
            self.timeline_sheets_id = sheets_id
            return sheets_id
        
        # Создаём новую таблицу
        logger.info("📊 Создание новой таблицы таймлайна занятости оборудования...")
        
        sheets_id = self.google_service.create_spreadsheet(
            title=timeline_name,
            folder_id=equipment_folder_id,
            background=False
        )["spreadsheetId"]
        
        logger.info(f"✅ Создана таблица таймлайна занятости: {sheets_id}")
        logger.info(f"💡 Сохраните GOOGLE_EQUIPMENT_TIMELINE_SHEETS_ID={sheets_id} в переменные окружения")
        
        # Создаём стандартные листы
        await self._create_default_sheets(sheets_id)
        
        self.timeline_sheets_id = sheets_id
        return sheets_id
    
    async def _find_sheets_in_folder(self, folder_id: str, name: str) -> Optional[str]:
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
    
    async def _create_default_sheets(self, spreadsheet_id: str):
        """Создать стандартные листы в таблице"""
        # Создаём лист "Общий" (все заявки)
        self.google_service.create_sheet_tab(
            spreadsheet_id=spreadsheet_id,
            sheet_name="Общий",
            background=False
        )
        
        logger.info("✅ Создан лист 'Общий'")
    
    async def sync_equipment_timeline_to_sheets_async(
        self,
        month: int,
        year: int,
        db: AsyncSession,
        statuses: Optional[List[str]] = None  # Фильтр по статусам заявок
    ) -> dict:
        """
        Синхронизировать таймлайн занятости оборудования с Google Sheets
        
        Args:
            month: Месяц (1-12)
            year: Год
            db: Сессия БД
            statuses: Фильтр по статусам заявок (опционально)
        
        Returns:
            Словарь с результатами синхронизации
        """
        try:
            # Получаем или создаём таблицу
            sheets_id = await self._get_or_create_timeline_sheets(db)
            
            # Получаем данные из БД
            first_day = date(year, month, 1)
            last_day = date(year, month, cal_lib.monthrange(year, month)[1])
            
            # Получаем все заявки на оборудование в диапазоне дат
            requests_query = select(EquipmentRequest).where(
                and_(
                    or_(
                        EquipmentRequest.start_date <= last_day,
                        EquipmentRequest.end_date >= first_day
                    )
                )
            )
            
            # Фильтр по статусам (если указан)
            if statuses:
                try:
                    status_enums = [EquipmentRequestStatus(s) for s in statuses if s in [st.value for st in EquipmentRequestStatus]]
                    if status_enums:
                        requests_query = requests_query.where(EquipmentRequest.status.in_(status_enums))
                except ValueError:
                    logger.warning(f"Некорректные статусы в фильтре: {statuses}")
            
            result = await db.execute(requests_query)
            requests = result.scalars().all()
            
            # Загружаем связанные данные (оборудование, пользователи)
            for req in requests:
                equipment_result = await db.execute(
                    select(Equipment).where(Equipment.id == req.equipment_id)
                )
                req.equipment = equipment_result.scalar_one_or_none()
                
                from app.models.user import User
                user_result = await db.execute(
                    select(User).where(User.id == req.user_id)
                )
                req.user = user_result.scalar_one_or_none()
            
            # Синхронизируем общий календарь
            await self._sync_general_timeline(
                sheets_id=sheets_id,
                month=month,
                year=year,
                requests=requests
            )
            
            logger.info(f"✅ Таймлайн занятости оборудования синхронизирован для {month}/{year}")
            
            return {
                "status": "success",
                "month": month,
                "year": year,
                "requests_count": len(requests),
                "sheets_id": sheets_id
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации таймлайна занятости: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _sync_general_timeline(
        self,
        sheets_id: str,
        month: int,
        year: int,
        requests: List[EquipmentRequest]
    ):
        """Синхронизировать общий календарь занятости"""
        sheet_name = "Общий"
        
        # Получаем ID листа
        sheet_id = self._get_sheet_id(sheets_id, sheet_name)
        if not sheet_id:
            logger.error(f"Лист '{sheet_name}' не найден")
            return
        
        # Подготавливаем данные для календаря
        first_day = date(year, month, 1)
        last_day = date(year, month, cal_lib.monthrange(year, month)[1])
        
        # Создаём заголовки (даты месяца)
        headers = ["Оборудование"]
        current_date = first_day
        while current_date <= last_day:
            headers.append(current_date.strftime("%d.%m"))
            current_date += timedelta(days=1)
        
        # Группируем заявки по оборудованию
        equipment_requests: Dict[str, List[EquipmentRequest]] = {}
        for req in requests:
            if req.equipment:
                eq_name = req.equipment.name
                if eq_name not in equipment_requests:
                    equipment_requests[eq_name] = []
                equipment_requests[eq_name].append(req)
        
        # Сортируем оборудование по имени
        sorted_equipment = sorted(equipment_requests.keys())
        
        # Формируем строки данных
        rows = []
        for eq_name in sorted_equipment:
            reqs = equipment_requests[eq_name]
            row = [eq_name]
            
            # Для каждой даты месяца
            current_date = first_day
            while current_date <= last_day:
                cell_parts = []
                
                # Проверяем заявки на эту дату
                for req in reqs:
                    if req.start_date <= current_date <= req.end_date:
                        # Определяем цвет и иконку по статусу
                        status_icon = {
                            EquipmentRequestStatus.PENDING: "⏳",
                            EquipmentRequestStatus.APPROVED: "✅",
                            EquipmentRequestStatus.ACTIVE: "📦",
                            EquipmentRequestStatus.COMPLETED: "✓",
                            EquipmentRequestStatus.REJECTED: "❌",
                            EquipmentRequestStatus.CANCELLED: "🚫"
                        }.get(req.status, "⏳")
                        
                        # Добавляем информацию о заявке
                        user_name = req.user.full_name if req.user else "Неизвестно"
                        cell_parts.append(f"{status_icon} {user_name[:15]}")
                        
                        # Проверяем просрочку
                        if req.end_date < date.today() and req.status not in [EquipmentRequestStatus.COMPLETED, EquipmentRequestStatus.CANCELLED]:
                            cell_parts.append("⚠️ Просрочено")
                
                # Если есть дедлайн на эту дату
                for req in reqs:
                    if req.end_date == current_date:
                        cell_parts.append("📅 Возврат")
                
                cell_value = "\n".join(cell_parts) if cell_parts else ""
                row.append(cell_value)
                current_date += timedelta(days=1)
            
            rows.append(row)
        
        # Записываем данные в таблицу
        range_name = f"{sheet_name}!A:{chr(65 + len(headers) - 1)}"
        
        # Очищаем старые данные (кроме заголовка, если есть)
        # Записываем заголовки и данные
        all_data = [headers] + rows
        
        # Используем batch update для записи
        self.google_service.batch_update_sheet(
            spreadsheet_id=sheets_id,
            requests=[{
                "updateCells": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": 0,
                        "endRowIndex": len(all_data),
                        "startColumnIndex": 0,
                        "endColumnIndex": len(headers)
                    },
                    "rows": [
                        {
                            "values": [
                                {"userEnteredValue": {"stringValue": str(cell)}}
                                for cell in row
                            ]
                        }
                        for row in all_data
                    ],
                    "fields": "userEnteredValue"
                }
            }],
            background=False
        )
        
        # Применяем форматирование
        await self._format_timeline_sheet(sheets_id, sheet_id, len(headers), len(rows) + 1)
        
        logger.info(f"✅ Обновлён календарь занятости: {len(rows)} единиц оборудования")
    
    async def _format_timeline_sheet(
        self,
        spreadsheet_id: str,
        sheet_id: int,
        num_columns: int,
        num_rows: int
    ):
        """Применить форматирование к листу таймлайна"""
        requests = []
        
        # Форматирование заголовка (строка 1)
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
        
        # Применяем форматирование
        if requests:
            self.google_service.batch_update_sheet(
                spreadsheet_id=spreadsheet_id,
                requests=requests,
                background=False
            )
    
    def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """Получить ID листа по имени"""
        try:
            sheets_service = self.google_service._get_sheets_service(background=False)
            spreadsheet = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id
            ).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']
            
            return None
        except Exception as e:
            logger.warning(f"Ошибка получения ID листа {sheet_name}: {e}")
            return None
