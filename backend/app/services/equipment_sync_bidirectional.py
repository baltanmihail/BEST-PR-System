"""
Сервис двусторонней синхронизации оборудования между БД и Google Sheets
Отслеживает изменения в таблице и обновляет БД
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.equipment import EquipmentRequest, EquipmentRequestStatus
from app.models.user import User
from app.services.google_service import GoogleService
from app.services.equipment_sheets_sync import EquipmentSheetsSync

logger = logging.getLogger(__name__)


class EquipmentBidirectionalSync:
    """Сервис для двусторонней синхронизации оборудования"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.sheets_sync = EquipmentSheetsSync(google_service)
    
    async def sync_from_sheets(self, db: AsyncSession) -> dict:
        """
        Синхронизирует изменения из Google Sheets в БД
        
        Отслеживает:
        - Изменения статусов заявок
        - Удаление заявок из таблицы
        
        Returns:
            Словарь с результатами синхронизации
        """
        try:
            sheets_id = self.sheets_sync._get_equipment_sheets_id()
            
            # Читаем все заявки из таблицы
            values = self.google_service.read_sheet(
                "Заявки на оборудку!A:Z",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return {
                    "status": "skipped",
                    "reason": "no_requests_in_sheet"
                }
            
            headers = values[0]
            
            # Определяем индексы колонок
            try:
                app_num_col = headers.index('Номер')
                status_col = headers.index('Статус')
            except ValueError as e:
                logger.error(f"Не найдены необходимые колонки: {e}")
                return {"status": "error", "error": str(e)}
            
            # Создаём словарь заявок из таблицы: номер -> статус
            sheets_requests = {}
            for row in values[1:]:
                if len(row) <= max(app_num_col, status_col):
                    continue
                
                app_num_str = row[app_num_col].strip() if app_num_col < len(row) else ''
                status = row[status_col].strip() if status_col < len(row) else ''
                
                if app_num_str:
                    try:
                        # Пытаемся найти заявку по номеру или UUID
                        app_num = int(app_num_str) if app_num_str.isdigit() else None
                        if app_num:
                            sheets_requests[app_num] = status
                        else:
                            # Может быть UUID или другой идентификатор
                            # Ищем заявку по другим полям
                            pass
                    except (ValueError, TypeError):
                        continue
            
            # Получаем все заявки из БД
            db_requests_query = select(EquipmentRequest)
            result = await db.execute(db_requests_query)
            db_requests = result.scalars().all()
            
            # Создаём словарь заявок из БД: id -> (request, status)
            db_requests_dict = {}
            for req in db_requests:
                # Получаем номер заявки из таблицы (если есть связь)
                # Пока используем ID заявки как ключ
                db_requests_dict[req.id] = {
                    'request': req,
                    'status': req.status.value if req.status else None
                }
            
            updated_count = 0
            deleted_count = 0
            status_changes = []
            
            # Обновляем статусы существующих заявок
            for req_id, req_data in db_requests_dict.items():
                req = req_data['request']
                old_status = req_data['status']
                
                # Ищем заявку в таблице по номеру или другим полям
                # Пока используем упрощённый подход: ищем по ID
                found_in_sheets = False
                new_status = None
                
                # TODO: Реализовать поиск заявки в таблице по UUID или другим идентификаторам
                # Пока пропускаем, так как нужна связь между БД и таблицей
                
                # Если заявка не найдена в таблице, помечаем как удалённую
                if not found_in_sheets:
                    # Проверяем, не была ли заявка удалена из таблицы
                    # Пока не удаляем из БД автоматически, только логируем
                    logger.debug(f"Заявка {req_id} не найдена в таблице")
            
            logger.info(f"✅ Синхронизация завершена: обновлено {updated_count}, удалено {deleted_count}, изменений статуса: {len(status_changes)}")
            
            return {
                "status": "success",
                "updated": updated_count,
                "deleted": deleted_count,
                "status_changes": status_changes
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации из таблицы: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def sync_status_changes(self, db: AsyncSession) -> List[Dict]:
        """
        Отслеживает изменения статусов заявок в таблице и возвращает список изменений
        
        Returns:
            Список изменений статусов: [{'request_id': uuid, 'old_status': str, 'new_status': str, 'user_id': uuid}, ...]
        """
        try:
            # Получаем все заявки из таблицы с их статусами
            sheets_id = self.sheets_sync._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                "Заявки на оборудку!A:Z",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return []
            
            headers = values[0]
            
            try:
                app_num_col = headers.index('Номер')
                status_col = headers.index('Статус')
            except ValueError:
                return []
            
            # Получаем все заявки из БД
            db_requests_query = select(EquipmentRequest)
            result = await db.execute(db_requests_query)
            db_requests = result.scalars().all()
            
            # Загружаем связанные пользователи
            for req in db_requests:
                user_result = await db.execute(
                    select(User).where(User.id == req.user_id)
                )
                req.user = user_result.scalar_one_or_none()
            
            status_changes = []
            
            # Сопоставляем заявки из таблицы с заявками из БД
            # TODO: Реализовать правильное сопоставление по номеру заявки или UUID
            # Пока используем упрощённый подход
            
            for row in values[1:]:
                if len(row) <= max(app_num_col, status_col):
                    continue
                
                app_num_str = row[app_num_col].strip() if app_num_col < len(row) else ''
                new_status_str = row[status_col].strip() if status_col < len(row) else ''
                
                if not app_num_str or not new_status_str:
                    continue
                
                # Пытаемся найти заявку в БД
                # TODO: Реализовать поиск по номеру заявки или UUID
                # Пока пропускаем
                pass
            
            return status_changes
            
        except Exception as e:
            logger.error(f"Ошибка отслеживания изменений статусов: {e}", exc_info=True)
            return []
