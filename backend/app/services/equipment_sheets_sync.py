"""
Сервис синхронизации оборудования с Google Sheets
Полная реализация с учётом структуры таблицы BEST Channel Bot
"""
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Set, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String, func
import logging
import re
from collections import defaultdict

from app.models.equipment import EquipmentRequest, Equipment, EquipmentRequestStatus
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
    
    def _get_photo_folder_id(self) -> Optional[str]:
        """Получить ID папки с фото оборудования"""
        # Сначала проверяем конфиг (приоритет — явно указанная папка)
        if settings.GOOGLE_EQUIPMENT_PHOTO_FOLDER_ID:
            return settings.GOOGLE_EQUIPMENT_PHOTO_FOLDER_ID
        
        try:
            equipment_folder_id = self.drive_structure.get_equipment_folder_id()
            if not equipment_folder_id:
                return None
            
            service = self.google_service._get_drive_service(background=False)
            
            query = f"name='Photo' and mimeType='application/vnd.google-apps.folder' and '{equipment_folder_id}' in parents and trashed=false"
            
            results = service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            files = results.get('files', [])
            if files:
                logger.info(f"Found Photo folder: {files[0]['id']}")
                return files[0]['id']
            
            return None
        except Exception as e:
            logger.error(f"Error finding Photo folder: {e}")
            return None
    
    _photo_cache: Dict[str, List[Dict]] = {}
    
    def _get_equipment_photo_url(self, equipment_name: str) -> Optional[str]:
        """
        Получить URL фото оборудования из папки с фото на Google Drive.
        Использует многоуровневое сопоставление (точное → частичное → по ключевым словам).
        """
        try:
            photo_folder_id = self._get_photo_folder_id()
            if not photo_folder_id:
                return None
            
            # Кэшируем список файлов, чтобы не делать запрос для каждого оборудования
            if photo_folder_id not in self._photo_cache:
                service = self.google_service._get_drive_service(background=False)
                query = f"'{photo_folder_id}' in parents and trashed=false and (mimeType contains 'image/')"
                results = service.files().list(
                    q=query,
                    fields="files(id, name)",
                    pageSize=100
                ).execute()
                self._photo_cache[photo_folder_id] = results.get('files', [])
            
            files = self._photo_cache[photo_folder_id]
            if not files:
                return None
            
            equipment_name_lower = equipment_name.lower().strip()
            
            def normalize(s: str) -> str:
                """Нормализуем строку для сравнения: убираем лишние пробелы, спецсимволы"""
                s = s.lower().strip()
                for ch in [',', '.', '(', ')', '-', '_', '/', '\\']:
                    s = s.replace(ch, ' ')
                return ' '.join(s.split())
            
            eq_norm = normalize(equipment_name)
            eq_words = set(eq_norm.split())
            
            best_match = None
            best_score = 0
            
            for file in files:
                file_name = file['name']
                file_name_no_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
                fn_norm = normalize(file_name_no_ext)
                fn_words = set(fn_norm.split())
                
                # Точное совпадение нормализованных строк
                if fn_norm == eq_norm:
                    best_match = file
                    break
                
                # Одна строка содержит другую
                if fn_norm in eq_norm or eq_norm in fn_norm:
                    score = len(fn_norm) + len(eq_norm)
                    if score > best_score:
                        best_score = score
                        best_match = file
                        continue
                
                # Пересечение слов (минимум 2 или одно длинное >=5 символов)
                common = eq_words & fn_words
                long_common = [w for w in common if len(w) >= 5]
                if len(common) >= 2 or len(long_common) >= 1:
                    score = sum(len(w) for w in common)
                    if score > best_score:
                        best_score = score
                        best_match = file
            
            if best_match:
                file_id = best_match['id']
                photo_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w600"
                logger.info(f"Photo matched for '{equipment_name}': {best_match['name']}")
                return photo_url
            
            all_names = [f['name'] for f in files]
            logger.warning(f"No photo match for '{equipment_name}'. Available: {all_names}")
            return None
        except Exception as e:
            logger.error(f"Error finding photo for '{equipment_name}': {e}")
            return None
    
    async def _get_next_equipment_number(self) -> str:
        """Получить следующий номер для строки в листе 'Вся оборудка'"""
        try:
            values = self.google_service.read_sheet(
                f"{self.EQUIPMENT_SHEET}!A:A",
                sheet_id=self._get_equipment_sheets_id(),
                background=True
            )
            if not values or len(values) < 2:
                return "1"
            max_num = 0
            for row in values[1:]:
                if row and str(row[0]).strip().replace(".", "").isdigit():
                    try:
                        max_num = max(max_num, int(float(str(row[0]).strip())))
                    except (ValueError, TypeError):
                        pass
            return str(max_num + 1)
        except Exception as e:
            logger.warning(f"Ошибка получения номера оборудования: {e}")
            return "1"
    
    async def append_equipment_to_sheets(self, equipment: Equipment) -> dict:
        """
        Добавить новое оборудование в лист "Вся оборудка" Google Sheets.
        Вызывается при создании оборудования через сайт.
        """
        try:
            number = await self._get_next_equipment_number()
            photo_url = (equipment.specs or {}).get("photo_url", "") or ""
            status_ru = {
                "available": "На складе",
                "rented": "Выдано",
                "maintenance": "В ремонте",
                "broken": "Сломано"
            }.get(
                equipment.status.value if hasattr(equipment.status, "value") else str(equipment.status),
                "На складе"
            )
            row_data = [[number, equipment.name, photo_url, status_ru]]
            self.google_service.append_to_sheet(
                range_name=f"{self.EQUIPMENT_SHEET}!A:D",
                values=row_data,
                sheet_id=self._get_equipment_sheets_id(),
                background=True
            )
            logger.info(f"✅ Оборудование '{equipment.name}' добавлено в Sheets (№{number})")
            return {"status": "success", "number": number}
        except Exception as e:
            logger.error(f"❌ Ошибка добавления оборудования в Sheets: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def sync_equipment_from_sheets(
        self,
        db: AsyncSession
    ) -> dict:
        """
        Синхронизировать оборудование из Google Sheets в БД.
        Sheets — источник истины: оборудование, которого нет в Sheets, удаляется из БД.
        """
        try:
            # Сбрасываем кэш фото, чтобы подхватить новые файлы с Drive
            self._photo_cache.clear()

            values = self.google_service.read_sheet(
                f"{self.EQUIPMENT_SHEET}!A:D",
                sheet_id=self._get_equipment_sheets_id(),
                background=True
            )
            
            if not values or len(values) < 2:
                return {"status": "skipped", "reason": "no_data", "synced": 0}
            
            synced_count = 0
            updated_count = 0
            created_count = 0
            deleted_count = 0
            synced_names = set()
            
            async with db.begin_nested():
                for row in values[1:]:
                    if len(row) < 2:
                        continue
                    
                    number = row[0].strip() if len(row) > 0 else ""
                    raw_name = row[1].strip() if len(row) > 1 else ""
                    photo_url = row[2].strip() if len(row) > 2 else ""
                    status_ru = row[3].strip() if len(row) > 3 else "На складе"
                    
                    # Убираем переносы строк (Google Sheets может вставлять \n)
                    name = " ".join(raw_name.replace("\r", " ").replace("\n", " ").split())
                    
                    if not name:
                        continue
                    
                    skip_keywords = [
                        "позже", "появится", "скоро", "планируется", 
                        "примечание", "комментарий", "итого", "всего",
                        "на учёте", "на учете", "будет", "добавится",
                        "в процессе", "заказано", "ожидается", "todo",
                        "...", "---", "***"
                    ]
                    name_lower = name.lower()
                    if any(kw in name_lower for kw in skip_keywords):
                        logger.info(f"Skipping service row: {name}")
                        continue
                    
                    if re.search(r'оборудовани[ея]\s+[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', name):
                        logger.info(f"Skipping person reference row: {name}")
                        continue
                    
                    if len(name) < 3:
                        continue
                    
                    if number and not number.replace(".", "").isdigit():
                        logger.info(f"Skipping non-numeric row: {number} - {name}")
                        continue
                    
                    status_map = {
                        "На складе": "available",
                        "Выдано": "rented",
                        "В ремонте": "maintenance",
                        "Сломано": "broken"
                    }
                    status = status_map.get(status_ru, "available")
                    quantity = self._parse_quantity_from_name(name)
                    category = self._detect_category(name)
                    
                    if not photo_url:
                        photo_url = self._get_equipment_photo_url(name) or ""
                    
                    logger.info(f"Processing: {name}, qty: {quantity}, category: {category}, status: {status}")
                    
                    synced_names.add(name)
                    
                    # Ищем по точному имени ИЛИ по старому имени с переносом строки
                    result = await db.execute(
                        select(Equipment).where(Equipment.name == name)
                    )
                    existing = result.scalar_one_or_none()
                    
                    # Если не нашли — ищем по raw_name (мог быть с \n раньше)
                    if not existing and raw_name != name:
                        result2 = await db.execute(
                            select(Equipment).where(Equipment.name == raw_name)
                        )
                        existing = result2.scalar_one_or_none()
                    
                    if existing:
                        existing.name = name
                        existing.status = status
                        existing.quantity = quantity
                        existing.category = category
                        # Копируем specs чтобы SQLAlchemy обнаружил изменение JSONB
                        specs = dict(existing.specs or {})
                        if number:
                            specs["number"] = number
                        if photo_url:
                            specs["photo_url"] = photo_url
                        existing.specs = specs
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(existing, "specs")
                        updated_count += 1
                    else:
                        specs = {}
                        if number:
                            specs["number"] = number
                        if photo_url:
                            specs["photo_url"] = photo_url
                        
                        new_equipment = Equipment(
                            name=name,
                            category=category,
                            quantity=quantity,
                            specs=specs if specs else None,
                            status=status
                        )
                        db.add(new_equipment)
                        created_count += 1
                    
                    synced_count += 1
                
                # Удаляем оборудование, которого больше нет в Sheets
                # (только если нет активных заявок)
                all_eq_result = await db.execute(select(Equipment))
                all_equipment = all_eq_result.scalars().all()
                
                for eq in all_equipment:
                    if eq.name not in synced_names:
                        active_count_r = await db.execute(
                            select(func.count(EquipmentRequest.id)).where(
                                EquipmentRequest.equipment_id == eq.id,
                                cast(EquipmentRequest.status, String).in_([
                                    EquipmentRequestStatus.PENDING.value,
                                    EquipmentRequestStatus.APPROVED.value,
                                    EquipmentRequestStatus.ACTIVE.value,
                                ])
                            )
                        )
                        active_count = active_count_r.scalar_one() or 0
                        
                        if active_count == 0:
                            await db.delete(eq)
                            deleted_count += 1
                            logger.info(f"Deleted absent equipment: {eq.name}")
                        else:
                            logger.info(f"Keeping absent equipment with active requests: {eq.name}")
            
            await db.commit()
            logger.info(
                f"✅ Sync: создано {created_count}, обновлено {updated_count}, "
                f"удалено {deleted_count}, всего {synced_count}"
            )
            
            return {
                "status": "success",
                "synced": synced_count,
                "created": created_count,
                "updated": updated_count,
                "deleted": deleted_count
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"❌ Ошибка синхронизации оборудования из Sheets: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "synced": 0}
    
    def _parse_quantity_from_name(self, name: str) -> int:
        """
        Извлечь количество из названия оборудования.
        Примеры: "Световые палки Aputure, 2шт" → 2
                 "Стойка (2 штуки)" → 2
        Returns: quantity (1 если не найдено)
        """
        import re
        # Паттерны: 2шт, 2 шт, 2штуки, 2 штуки, (2шт), (2 штуки)
        patterns = [
            r',\s*(\d+)\s*шт[\s.)]*$', r',\s*(\d+)\s*штук[иа]?[\s.)]*$',
            r'\(\s*(\d+)\s*шт[\s.)]*\)', r'\(\s*(\d+)\s*штук[иа]?[\s.)]*\)',
            r'\s+(\d+)\s*шт\.?\s*$', r'\s+(\d+)\s*штук[иа]?\s*$',
        ]
        for pat in patterns:
            m = re.search(pat, name, re.IGNORECASE)
            if m:
                q = int(m.group(1))
                if 1 <= q <= 100:
                    return q
        return 1
    
    def _detect_category(self, name: str) -> str:
        """Определить категорию оборудования по названию"""
        name_lower = name.lower()
        
        # Камеры (высокий приоритет)
        if any(word in name_lower for word in [
            "камера", "camera", "видеокамера", "фотоаппарат", "фотокамера",
            "беззеркальн", "зеркальн", "mirrorless", "dslr",
            "sony zv", "sony a7", "sony a6", "canon eos", "nikon z",
            "fujifilm", "panasonic gh", "zv-e10", "zv e10"
        ]):
            return "camera"
        # Объективы
        elif any(word in name_lower for word in ["объектив", "lens", "линза"]):
            return "lens"
        # Аудио (микрофоны, рекордеры, DJI Mic) — до стабилизаторов, чтобы DJI Mic не попал в accessories
        elif any(word in name_lower for word in [
            "микрофон", "audio", "аудио", "рекордер", "mic ",
            "dji mic", "rode", "boya", "saramonic", "zoom h"
        ]):
            return "audio"
        # Штативы, стойки и треноги — ПЕРЕД светом, чтобы "Стойка Falcon Eyes" была штативом
        elif any(word in name_lower for word in [
            "штатив", "tripod", "стойка", "монопод", "тренога"
        ]):
            return "tripod"
        # Свет (Aputure amaran, световые палки, панели и т.д.)
        elif any(word in name_lower for word in [
            "свет", "lighting", "ламп", "софтбокс", "led панель", "кольцев",
            "aputure", "amaran", "godox", "световая палка", "светодиод",
            "falcon eyes", "nanlite", "yongnuo"
        ]):
            return "lighting"
        # Накопители (SD-карты, SSD, USB) — до стабилизаторов
        elif any(word in name_lower for word in [
            "накопитель", "storage", "ssd", "карта памяти", "sd card",
            "cf card", "sd ", "sd samsung", "microsd", "usb flash",
            "samsung evo", "sandisk", "512 гб", "256 гб", "128 гб",
            "64 гб", "1 тб"
        ]):
            return "storage"
        # Стабилизаторы / гимбалы
        elif any(word in name_lower for word in [
            "стабилизатор", "stabilizer", "gimbal", "steadicam", "zhiyun",
            "dji rs", "dji osmo", "dji om", "ronin"
        ]):
            return "stabilizer"
        # Аксессуары (включая держатели)
        elif any(word in name_lower for word in [
            "аксессуар", "accessories", "переходник", "кабель", "батарея",
            "зарядка", "фильтр", "бленда", "адаптер", "ремень", "чехол",
            "держатель"
        ]):
            return "accessories"
        else:
            return "other"
    
    def _is_valid_equipment_row(self, row: list) -> bool:
        """Проверить, является ли строка валидной записью оборудования (не комментарий)"""
        if len(row) < 2:
            return False
        
        name = row[1].strip() if len(row) > 1 else ""
        
        # Пропускаем пустые названия
        if not name:
            return False
        
        # Пропускаем строки-комментарии (начинаются с "Позже", "TODO", "Примечание" и т.д.)
        skip_prefixes = [
            "позже", "todo", "примечание", "комментарий", "заметка", 
            "note", "...", "---", "***", "///"
        ]
        name_lower = name.lower()
        if any(name_lower.startswith(prefix) for prefix in skip_prefixes):
            return False
        
        # Пропускаем слишком короткие названия (менее 3 символов)
        if len(name) < 3:
            return False
        
        return True
    
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
            username = user.username or ""
            full_name = user.full_name or ""
            
            if username:
                who_takes = f"https://t.me/{username.lstrip('@')} - {full_name}"
            else:
                who_takes = full_name
            
            # Получаем название мероприятия: из purpose, или из задачи
            shooting_name = request.purpose or ""
            if not shooting_name and request.task_id:
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
                    request.purpose or "",  # Комментарий / цель использования
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
                    sheet_id=self._get_equipment_sheets_id(),
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
            # Обновляем статус заявки в Sheets (находим строку по equipment, user, dates)
            await self._update_request_status_in_sheets(request, equipment, user, new_status)
            
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
        request: EquipmentRequest,
        equipment: Equipment,
        user: User,
        new_status: EquipmentRequestStatus
    ):
        """Обновить статус заявки в листе 'Заявки на оборудку'"""
        try:
            sheets_id = self._get_equipment_sheets_id()
            values = self.google_service.read_sheet(
                f"{self.REQUESTS_SHEET}!A:K",
                sheet_id=sheets_id,
                background=True
            )
            
            if not values or len(values) < 2:
                return
            
            status_map = {
                EquipmentRequestStatus.PENDING: "На рассмотрении",
                EquipmentRequestStatus.APPROVED: "Одобрено",
                EquipmentRequestStatus.REJECTED: "Отклонено",
                EquipmentRequestStatus.ACTIVE: "Выдано",
                EquipmentRequestStatus.COMPLETED: "Возвращено",
                EquipmentRequestStatus.CANCELLED: "Отменено"
            }
            status_ru = status_map.get(new_status, "На рассмотрении")
            
            # Ищем строку: совпадение по датам + пользователю + оборудованию
            start_str = request.start_date.strftime("%d.%m.%Y")
            end_str = request.end_date.strftime("%d.%m.%Y")
            user_identifiers = []
            if user.username:
                user_identifiers.append(user.username.lstrip('@'))
            if user.full_name:
                user_identifiers.append(user.full_name)
            
            row_index = None  # 0-based row index в values
            for i, row in enumerate(values[1:], start=1):
                if len(row) < 10:
                    continue
                # Колонки: 0=Номер, 6=Дата выдачи, 8=Дата возврата, 3=Кто берёт
                row_start = row[6].strip() if len(row) > 6 else ""
                row_end = row[8].strip() if len(row) > 8 else ""
                row_who = row[3].strip() if len(row) > 3 else ""
                
                if row_start == start_str and row_end == end_str:
                    # "Кто берёт" должен содержать username или ФИО пользователя
                    if any(ident and ident.lower() in row_who.lower() for ident in user_identifiers):
                        row_index = i
                        break
            
            if row_index is None:
                logger.warning(f"Не найдена строка заявки в Sheets для request {request.id}")
                return
            
            # Обновляем статус: колонка K (индекс 10), row_index+1 т.к. есть заголовок
            sheet_id = self._get_sheet_id(self.REQUESTS_SHEET)
            cell_range = {
                "sheetId": sheet_id,
                "startRowIndex": row_index,
                "endRowIndex": row_index + 1,
                "startColumnIndex": 10,
                "endColumnIndex": 11
            }
            
            self.google_service.batch_update_sheet(
                sheets_id,
                [{
                    "updateCells": {
                        "range": cell_range,
                        "rows": [{
                            "values": [{"userEnteredValue": {"stringValue": status_ru}}]
                        }],
                        "fields": "userEnteredValue.stringValue"
                    }
                }],
                background=True
            )
            logger.info(f"✅ Статус заявки обновлён в Sheets: строка {row_index + 2}, статус={status_ru}")
            
        except Exception as e:
            logger.error(f"Ошибка обновления статуса заявки в Sheets: {e}", exc_info=True)
    
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
                    user.full_name or "",
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
