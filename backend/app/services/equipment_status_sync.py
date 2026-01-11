"""
Сервис автоматического обновления статусов оборудования по датам
Аналогично BEST Channel Bot: На складе → Занят, съёмка предстоит → Занят, съёмка окончена → На складе
"""
import logging
from typing import List, Optional, Dict
from datetime import datetime, date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import re

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus, EquipmentStatus
from app.models.user import User
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService

logger = logging.getLogger(__name__)


class EquipmentStatusSync:
    """Сервис для автоматического обновления статусов оборудования по датам"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.drive_structure = DriveStructureService()
    
    def _get_equipment_sheets_id(self) -> str:
        """Получить ID таблицы с оборудованием"""
        from app.config import settings
        from app.services.equipment_sheets_sync import EquipmentSheetsSync
        
        sync_service = EquipmentSheetsSync(self.google_service)
        return sync_service._get_equipment_sheets_id()
    
    async def update_equipment_statuses_by_date(self, db: AsyncSession) -> dict:
        """
        Автоматически обновляет статусы оборудования по датам
        
        Логика:
        - На складе → Занят, съёмка предстоит → Занят, съёмка окончена → На складе
        - Обновляет даты выдачи и возврата из ближайших одобренных заявок
        - Обновляет "У кого сейчас?" из заявок
        - Обновляет историю оборудования
        
        Args:
            db: Сессия БД
        
        Returns:
            Словарь с результатами обновления
        """
        try:
            sheets_id = self._get_equipment_sheets_id()
            
            # Получаем все одобренные заявки из БД
            approved_requests_query = select(EquipmentRequest).where(
                EquipmentRequest.status.in_([
                    EquipmentRequestStatus.APPROVED.value,
                    EquipmentRequestStatus.ACTIVE.value
                ])
            )
            result = await db.execute(approved_requests_query)
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
                
                # Получаем дату съёмки из задачи
                if req.task_id:
                    from app.models.task import Task
                    task_result = await db.execute(
                        select(Task).where(Task.id == req.task_id)
                    )
                    req.task = task_result.scalar_one_or_none()
            
            logger.info(f"Получено {len(requests)} одобренных заявок для обновления статусов")
            
            # Группируем заявки по номеру оборудования
            equipment_apps = {}  # {equipment_number: [{'issue': date, 'return': date, 'shooting': date, 'who_takes': str}, ...]}
            
            for req in requests:
                if not req.equipment:
                    continue
                
                # Получаем номер оборудования
                equipment_number = req.equipment.specs.get("number") if req.equipment.specs else None
                if not equipment_number:
                    # Пытаемся найти номер в таблице
                    equipment_number = await self._find_equipment_number(req.equipment.name)
                
                if not equipment_number:
                    continue
                
                # Получаем дату съёмки
                shooting_date = None
                if req.task and req.task.due_date:
                    shooting_date = req.task.due_date.date()
                
                # Формируем строку "Кто берёт"
                who_takes = ""
                if req.user:
                    username = req.user.telegram_username or ""
                    full_name = req.user.full_name or f"{req.user.first_name} {req.user.last_name}".strip()
                    if username:
                        who_takes = f"https://t.me/{username.lstrip('@')} - {full_name}"
                    else:
                        who_takes = full_name
                
                if equipment_number not in equipment_apps:
                    equipment_apps[equipment_number] = []
                
                equipment_apps[equipment_number].append({
                    'issue': req.start_date,
                    'return': req.end_date,
                    'shooting': shooting_date,
                    'who_takes': who_takes
                })
            
            # Сортируем заявки по дате выдачи для каждого оборудования
            for eq_num in equipment_apps:
                equipment_apps[eq_num].sort(key=lambda x: x['issue'])
            
            # Читаем лист с оборудованием
            values = self.google_service.read_sheet(
                "Вся оборудка!A:G",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return {"status": "skipped", "reason": "no_equipment"}
            
            headers = values[0]
            
            # Определяем индексы колонок
            try:
                status_col = headers.index('Статус')
                date_issue_col = headers.index('Дата выдачи') if 'Дата выдачи' in headers else -1
                date_return_col = headers.index('Дата возврата') if 'Дата возврата' in headers else -1
                equipment_num_col = headers.index('Номер') if 'Номер' in headers else 0
                who_now_col = headers.index('У кого сейчас?') if 'У кого сейчас?' in headers else -1
            except ValueError as e:
                logger.error(f"Не найдены необходимые колонки: {e}")
                return {"status": "error", "error": str(e)}
            
            today = date.today()
            updated_count = 0
            dates_updated_count = 0
            who_updated_count = 0
            
            # Получаем ID листа для batch updates
            sheet_id_num = await self._get_sheet_id(sheets_id, "Вся оборудка")
            
            # Обновляем статусы и даты
            batch_updates = []  # Собираем все обновления в батч
            for i, row in enumerate(values[1:], start=2):
                if len(row) <= status_col:
                    continue
                
                # Получаем номер оборудования
                equipment_num = None
                if equipment_num_col >= 0 and equipment_num_col < len(row):
                    equipment_num = row[equipment_num_col].strip()
                
                if not equipment_num:
                    continue
                
                current_status = row[status_col].strip() if status_col < len(row) else ''
                date_issue = row[date_issue_col].strip() if date_issue_col >= 0 and date_issue_col < len(row) else ''
                date_return = row[date_return_col].strip() if date_return_col >= 0 and date_return_col < len(row) else ''
                who_now = row[who_now_col].strip() if who_now_col >= 0 and who_now_col < len(row) else ''
                
                # Если статус "На складе" и даты заполнены - очищаем их
                # Собираем все обновления в батч для оптимизации
                batch_updates = []
                sheet_id_num = await self._get_sheet_id(sheets_id, "Вся оборудка")
                
                if current_status == "На складе":
                    if date_issue_col >= 0 and date_issue:
                        row_batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": date_issue_col,
                                    "endColumnIndex": date_issue_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        date_issue = ''
                        dates_updated_count += 1
                    
                    if date_return_col >= 0 and date_return:
                        batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": date_return_col,
                                    "endColumnIndex": date_return_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        date_return = ''
                        dates_updated_count += 1
                    
                    if who_now_col >= 0 and who_now:
                        batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": who_now_col,
                                    "endColumnIndex": who_now_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        who_now = ''
                        who_updated_count += 1
                    
                    # Применяем батч обновлений для этой строки
                    if row_batch_updates:
                        batch_updates.extend(row_batch_updates)
                        row_batch_updates = []
                    
                    if not date_issue and not date_return:
                        continue
                
                # Обновляем даты из ближайшей одобренной заявки
                if current_status != "На складе" and equipment_num in equipment_apps:
                    nearest_app = None
                    # Находим ближайшую активную заявку
                    for app in equipment_apps[equipment_num]:
                        if app['return'] >= today:
                            if app['issue'] <= today or nearest_app is None:
                                nearest_app = app
                                if app['issue'] <= today:
                                    break
                    
                    # Если нет активной заявки, берём ближайшую будущую
                    if not nearest_app and equipment_apps[equipment_num]:
                        future_apps = [app for app in equipment_apps[equipment_num] if app['issue'] > today]
                        if future_apps:
                            nearest_app = min(future_apps, key=lambda x: x['issue'])
                    
                    if nearest_app:
                        new_issue_date_str = nearest_app['issue'].strftime("%d.%m.%Y")
                        new_return_date_str = nearest_app['return'].strftime("%d.%m.%Y")
                        new_who_takes = nearest_app.get('who_takes', '')
                        
                        # Обновляем даты, если они отличаются (собираем в батч)
                        if date_issue_col >= 0 and date_issue != new_issue_date_str:
                            batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": date_issue_col,
                                        "endColumnIndex": date_issue_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": new_issue_date_str}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                            date_issue = new_issue_date_str
                            dates_updated_count += 1
                        
                        if date_return_col >= 0 and date_return != new_return_date_str:
                            row_batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": date_return_col,
                                        "endColumnIndex": date_return_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": new_return_date_str}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                            date_return = new_return_date_str
                            dates_updated_count += 1
                        
                        if who_now_col >= 0 and new_who_takes and who_now != new_who_takes:
                            row_batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": who_now_col,
                                        "endColumnIndex": who_now_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": new_who_takes}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                            who_updated_count += 1
                elif equipment_num and current_status != "На складе":
                    # Если для оборудования нет заявок, очищаем даты (собираем в батч)
                    if date_issue_col >= 0 and date_issue:
                        row_batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": date_issue_col,
                                    "endColumnIndex": date_issue_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        dates_updated_count += 1
                    
                    if date_return_col >= 0 and date_return:
                        batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": date_return_col,
                                    "endColumnIndex": date_return_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        dates_updated_count += 1
                    
                    if who_now_col >= 0 and who_now:
                        batch_updates.append({
                            "updateCells": {
                                "range": {
                                    "sheetId": sheet_id_num,
                                    "startRowIndex": i - 1,
                                    "endRowIndex": i,
                                    "startColumnIndex": who_now_col,
                                    "endColumnIndex": who_now_col + 1
                                },
                                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                "fields": "userEnteredValue"
                            }
                        })
                        who_updated_count += 1
                
                # Парсим даты для определения статуса
                issue_date = None
                return_date = None
                if date_issue and date_return:
                    try:
                        issue_date = datetime.strptime(date_issue, "%d.%m.%Y").date()
                        return_date = datetime.strptime(date_return, "%d.%m.%Y").date()
                    except ValueError:
                        continue
                else:
                    if current_status == "На складе":
                        continue
                    continue
                
                # Получаем дату съёмки из ближайшей заявки
                shooting_date = None
                if equipment_num in equipment_apps:
                    for app in equipment_apps[equipment_num]:
                        if app['issue'] == issue_date and app['return'] == return_date:
                            shooting_date = app.get('shooting')
                            break
                
                # Определяем правильный статус
                new_status = None
                
                if today > return_date:
                    # Дата возврата прошла - должно быть "На складе"
                    if current_status != "На складе":
                        new_status = "На складе"
                elif today >= issue_date and today < return_date:
                    # Период аренды активен
                    if shooting_date:
                        if today > shooting_date:
                            # Дата съёмки прошла
                            if current_status != "Занят, съёмка окончена":
                                new_status = "Занят, съёмка окончена"
                        else:
                            # Дата съёмки ещё не наступила
                            if current_status != "Занят, съёмка предстоит":
                                new_status = "Занят, съёмка предстоит"
                    else:
                        # Нет даты съёмки - используем дату выдачи + 1 день
                        estimated_shooting_date = issue_date + timedelta(days=1)
                        if today > estimated_shooting_date:
                            if current_status != "Занят, съёмка окончена":
                                new_status = "Занят, съёмка окончена"
                        else:
                            if current_status != "Занят, съёмка предстоит":
                                new_status = "Занят, съёмка предстоит"
                elif today < issue_date:
                    # Дата выдачи ещё не наступила
                    if current_status != "На складе":
                        new_status = "На складе"
                else:
                    if current_status != "На складе":
                        new_status = "На складе"
                
                if new_status and new_status != current_status:
                    # Обновляем статус в таблице (собираем в батч)
                    batch_updates.append({
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id_num,
                                "startRowIndex": i - 1,
                                "endRowIndex": i,
                                "startColumnIndex": status_col,
                                "endColumnIndex": status_col + 1
                            },
                            "rows": [{"values": [{"userEnteredValue": {"stringValue": new_status}}]}],
                            "fields": "userEnteredValue"
                        }
                    })
                    updated_count += 1
                    logger.debug(f"Обновлён статус оборудования #{equipment_num}: {current_status} → {new_status}")
                    
                    # Если статус изменился на "На складе", очищаем даты и "У кого сейчас?"
                    if new_status == "На складе":
                        if date_issue_col >= 0:
                            row_batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": date_issue_col,
                                        "endColumnIndex": date_issue_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                        if date_return_col >= 0:
                            row_batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": date_return_col,
                                        "endColumnIndex": date_return_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                        if who_now_col >= 0:
                            row_batch_updates.append({
                                "updateCells": {
                                    "range": {
                                        "sheetId": sheet_id_num,
                                        "startRowIndex": i - 1,
                                        "endRowIndex": i,
                                        "startColumnIndex": who_now_col,
                                        "endColumnIndex": who_now_col + 1
                                    },
                                    "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                                    "fields": "userEnteredValue"
                                }
                            })
                
                # Добавляем обновления строки в общий батч
                if row_batch_updates:
                    batch_updates.extend(row_batch_updates)
                    row_batch_updates = []
            
            # Применяем все батч обновления в конце (разбиваем на батчи по 50 запросов)
            if batch_updates:
                batch_size = 50
                for batch_start in range(0, len(batch_updates), batch_size):
                    batch = batch_updates[batch_start:batch_start + batch_size]
                    self.google_service.batch_update_sheet(
                        sheets_id,
                        batch,
                        background=True
                    )
            
            logger.info(f"✅ Обновлено статусов оборудования: {updated_count}, дат: {dates_updated_count}, 'У кого сейчас?': {who_updated_count}")
            
            return {
                "status": "success",
                "updated_statuses": updated_count,
                "updated_dates": dates_updated_count,
                "updated_who": who_updated_count
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления статусов оборудования: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _get_sheet_id(self, spreadsheet_id: str, sheet_name: str) -> int:
        """Получить ID листа по имени"""
        try:
            sheets_service = self.google_service._get_sheets_service(background=False)
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
    
    async def _find_equipment_number(self, equipment_name: str) -> Optional[str]:
        """Найти номер оборудования по названию"""
        try:
            sheets_id = self._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                "Вся оборудка!A:D",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return None
            
            for row in values[1:]:
                if len(row) > 1 and row[1].strip() == equipment_name.strip():
                    return row[0].strip() if len(row) > 0 else None
            
            return None
        except Exception as e:
            logger.error(f"Ошибка поиска номера оборудования: {e}")
            return None
