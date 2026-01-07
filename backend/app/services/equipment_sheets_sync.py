"""
Сервис синхронизации оборудования с Google Sheets
Автоматически обновляет таблицу "Учёт оборудки" при выдаче/возврате оборудования
"""
from datetime import datetime, date
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models.equipment import EquipmentRequest, Equipment
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)


class EquipmentSheetsSync:
    """Синхронизация оборудования с Google Sheets"""
    
    # ID таблицы "Учёт оборудки"
    EQUIPMENT_SHEETS_ID = "1nNqA_cvUnzPADO3DcwD6ldzHIwnghR7ypKuzec4bk0I"
    
    def __init__(self):
        self.google_service = None  # Type: Optional[GoogleService] (lazy import)
    
    def _get_google_service(self):
        """Ленивая инициализация GoogleService"""
        from app.services.google_service import GoogleService
        if self.google_service is None:
            self.google_service = GoogleService()
        return self.google_service
    
    async def log_equipment_request(
        self,
        db: AsyncSession,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User
    ):
        """
        Записать заявку на оборудование в лист "Заявки на оборудку"
        
        Структура листа (как в таблице):
        - Номер заявки
        - Что берёт (формула ='Вся оборудка'!CX)
        - Кто берёт
        - Дата выдачи
        - Дата возврата
        - Дата съёмки
        - Комментарий/Примечания
        - Статус (Ожидает/Одобрена/Отклонена)
        """
        try:
            # Находим номер строки оборудования в листе "Вся оборудка"
            equipment_row = await self._find_equipment_row(equipment.name)
            
            # Формула для ссылки на оборудование
            equipment_formula = f"='Вся оборудка'!C{equipment_row}" if equipment_row else equipment.name
            
            # Статус заявки
            status_map = {
                "pending": "Ожидает",
                "approved": "Одобрена",
                "rejected": "Отклонена",
                "active": "Выдано",
                "completed": "Возвращено",
                "cancelled": "Отменена"
            }
            status_ru = status_map.get(request.status.value, "Ожидает")
            
            # Данные для записи
            row_data = [
                [
                    str(request.id)[:8],  # Короткий ID заявки
                    equipment_formula,     # Что берёт
                    user.full_name,       # Кто берёт
                    request.start_date.strftime("%d.%m.%Y"),  # Дата выдачи
                    request.end_date.strftime("%d.%m.%Y"),    # Дата возврата
                    request.start_date.strftime("%d.%m.%Y"),  # Дата съёмки (можно уточнить)
                    request.purpose or "",  # Комментарий
                    status_ru,            # Статус
                ]
            ]
            
            # Записываем в Google Sheets
            self._get_google_service().append_sheet(
                range_name="Заявки на оборудку!A:H",
                values=row_data,
                sheet_id=self.EQUIPMENT_SHEETS_ID
            )
            
            logger.info(f"✅ Заявка {request.id} записана в Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Ошибка записи заявки в Google Sheets: {e}")
            # Не прерываем работу системы при ошибке синхронизации
    
    async def update_equipment_status_on_approval(
        self,
        db: AsyncSession,
        request: EquipmentRequest,
        equipment: Equipment,
        user: User
    ):
        """
        Обновить статус заявки в листе "Заявки на оборудку" при одобрении
        И добавить запись в "История оборудки"
        """
        try:
            # 1. Обновляем статус заявки в листе "Заявки на оборудку"
            await self._update_request_status(request.id, "Одобрена")
            
            # 2. Добавляем запись в "История оборудки"
            await self._log_to_history(request, equipment, user)
            
            # 3. Обновляем календарь занятости (лист "Календарь занятости оборудования")
            await self._update_calendar(request, equipment)
            
            logger.info(f"✅ Заявка {request.id} одобрена в Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления заявки в Google Sheets: {e}")
    
    async def _find_equipment_row(self, equipment_name: str) -> Optional[int]:
        """Найти номер строки оборудования в листе 'Вся оборудка'"""
        try:
            # Читаем лист "Вся оборудка"
            values = self._get_google_service().read_sheet(
                range_name="Вся оборудка!A:D",
                sheet_id=self.EQUIPMENT_SHEETS_ID
            )
            
            # Ищем строку с нужным оборудованием (колонка B = название)
            for i, row in enumerate(values[1:], start=2):  # Пропускаем заголовок
                if len(row) > 1 and row[1].strip() == equipment_name.strip():
                    return i
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка поиска оборудования: {e}")
            return None
    
    async def _update_request_status(self, request_id: str, new_status: str):
        """Обновить статус заявки в листе 'Заявки на оборудку'"""
        try:
            # Читаем все заявки
            values = self._get_google_service().read_sheet(
                range_name="Заявки на оборудку!A:H",
                sheet_id=self.EQUIPMENT_SHEETS_ID
            )
            
            # Ищем строку с нужной заявкой (по ID)
            request_id_short = str(request_id)[:8]
            for i, row in enumerate(values[1:], start=2):
                if len(row) > 0 and row[0] == request_id_short:
                    # Обновляем статус (колонка H)
                    self._get_google_service().write_sheet(
                        range_name=f"Заявки на оборудку!H{i}",
                        values=[[new_status]],
                        sheet_id=self.EQUIPMENT_SHEETS_ID
                    )
                    return
            
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
            # Структура "История оборудки":
            # Номер оборудования | Название | Кто брал | Дата выдачи | Дата возврата | Комментарий
            
            # Находим номер оборудования в листе "Вся оборудка"
            equipment_row = await self._find_equipment_row(equipment.name)
            equipment_number = equipment_row if equipment_row else "?"
            
            row_data = [
                [
                    equipment_number,
                    equipment.name,
                    user.full_name,
                    request.start_date.strftime("%d.%m.%Y"),
                    request.end_date.strftime("%d.%m.%Y"),
                    request.purpose or ""
                ]
            ]
            
            self._get_google_service().append_sheet(
                range_name="История оборудки!A:F",
                values=row_data,
                sheet_id=self.EQUIPMENT_SHEETS_ID
            )
            
        except Exception as e:
            logger.error(f"Ошибка записи в историю: {e}")
    
    async def _update_calendar(
        self,
        request: EquipmentRequest,
        equipment: Equipment
    ):
        """Обновить календарь занятости оборудования"""
        try:
            # Структура "Календарь занятости оборудования":
            # Строка 1: Даты (01.01, 02.01, ...)
            # Строка 2+: Номер оборудования | Дата1 | Дата2 | ...
            
            # TODO: Реализовать автоматическое обновление календаря
            # Сложность: нужно найти колонки с нужными датами и вписать номер заявки
            
            logger.info(f"TODO: Обновление календаря для заявки {request.id}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления календаря: {e}")
    
    async def sync_equipment_from_sheets(self, db: AsyncSession):
        """
        Синхронизировать оборудование из Google Sheets в базу данных
        Загружает список оборудования из листа "Вся оборудка"
        """
        try:
            # Читаем лист "Вся оборудка"
            values = self._get_google_service().read_sheet(
                range_name="Вся оборудка!A:D",
                sheet_id=self.EQUIPMENT_SHEETS_ID
            )
            
            synced_count = 0
            
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
                    "На складе": "available",
                    "Выдано": "rented",
                    "В ремонте": "maintenance",
                    "Сломано": "broken"
                }
                status = status_map.get(status_ru, "available")
                
                # Проверяем, есть ли уже в базе
                result = await db.execute(
                    select(Equipment).where(Equipment.name == name)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Обновляем статус
                    existing.status = status
                else:
                    # Создаём новое
                    new_equipment = Equipment(
                        name=name,
                        category="general",  # Можно уточнить по типу
                        status=status,
                        description=f"Номер: {number}",
                        # photo_url можно добавить, если есть поле в модели
                    )
                    db.add(new_equipment)
                    synced_count += 1
            
            await db.commit()
            logger.info(f"✅ Синхронизировано оборудования из Google Sheets: {synced_count}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации оборудования: {e}")


# Singleton instance
equipment_sync = EquipmentSheetsSync()
