"""
Инициализация структуры папок в Google Drive для BEST PR System
Создаёт папки при первом запуске согласно архитектуре проекта
"""
import logging
from typing import Optional, Dict

from app.config import settings
from app.services.google_service import GoogleService

logger = logging.getLogger(__name__)

# ID новой корневой папки на Google Drive
# https://drive.google.com/drive/folders/1Zxtqs4otBMhltOFCJG0-y8gBHWXvQGzI?usp=sharing
ROOT_FOLDER_ID = "1Zxtqs4otBMhltOFCJG0-y8gBHWXvQGzI"

# ID старой папки координаторов (для миграции, если нужно)
COORDINATORS_FOLDER_ID = "10A2GVTrYq8_Rm6pBDvQUEQxibHFdWxBd"

# Название папки для бота
BOT_FOLDER_NAME = "BEST PR System"


class DriveStructureService:
    """Сервис для управления структурой папок в Google Drive"""
    
    def __init__(self):
        self.google_service: Optional[GoogleService] = None
        self._bot_folder_id: Optional[str] = None
        self._support_folder_id: Optional[str] = None
        self._files_folder_id: Optional[str] = None
        self._initialized = False
    
    def _get_google_service(self) -> GoogleService:
        """Ленивая инициализация GoogleService"""
        if self.google_service is None:
            try:
                self.google_service = GoogleService()
            except ValueError as e:
                logger.warning(f"⚠️ Google credentials не найдены: {e}")
                logger.warning("Google Drive функции будут недоступны. Добавьте GOOGLE_CREDENTIALS_*_JSON в переменные окружения.")
                raise
        return self.google_service
    
    def initialize_structure(self) -> Dict[str, str]:
        """
        Инициализировать структуру папок в Google Drive согласно архитектуре
        
        Структура:
        - {ROOT_FOLDER_ID}/  (новая корневая папка)
          - BEST PR System/  (папка бота)
            - Tasks/  (папка для задач, подпапки создаются динамически)
            - Gallery/  (галерея проектов)
            - Equipment/  (для BEST Channel Bot - выдача оборудования)
            - Support/  (файлы от пользователей в поддержке)
            - Users/  (профили пользователей, фото)
        
        Returns:
            Словарь с ID папок
        
        Raises:
            ValueError: Если Google credentials не найдены
        """
        try:
            # Проверяем наличие credentials
            google_service = self._get_google_service()
            
            logger.info("📁 Инициализация структуры папок Google Drive...")
            
            # 1. Создаём главную папку бота в новой корневой папке
            bot_folder_id = self._get_or_create_bot_folder(google_service)
            logger.info(f"✅ Папка бота: {bot_folder_id}")
            
            # 2. Создаём подпапки согласно архитектуре
            tasks_folder_id = google_service.get_or_create_folder(
                "Tasks",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Папка 'Tasks': {tasks_folder_id}")
            
            gallery_folder_id = google_service.get_or_create_folder(
                "Gallery",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Папка 'Gallery': {gallery_folder_id}")
            
            equipment_folder_id = google_service.get_or_create_folder(
                "Equipment",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Папка 'Equipment': {equipment_folder_id}")
            
            support_folder_id = google_service.get_or_create_folder(
                "Support",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Папка 'Support': {support_folder_id}")
            
            users_folder_id = google_service.get_or_create_folder(
                "Users",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Папка 'Users': {users_folder_id}")
            
            structure = {
                "bot_folder_id": bot_folder_id,
                "tasks_folder_id": tasks_folder_id,
                "gallery_folder_id": gallery_folder_id,
                "equipment_folder_id": equipment_folder_id,
                "support_folder_id": support_folder_id,
                "users_folder_id": users_folder_id,
            }
            
            # Сохраняем ID главной папки в настройки (если не задан)
            if not settings.GOOGLE_DRIVE_FOLDER_ID:
                logger.info(f"💡 Сохраните GOOGLE_DRIVE_FOLDER_ID={bot_folder_id} в переменные окружения")
            
            self._initialized = True
            self._bot_folder_id = bot_folder_id
            self._support_folder_id = support_folder_id
            
            logger.info("✅ Структура папок Google Drive инициализирована")
            return structure
            
        except ValueError as e:
            logger.warning(f"⚠️ Google credentials не найдены, пропускаем инициализацию Google Drive: {e}")
            logger.warning("💡 Для использования Google Drive функций добавьте GOOGLE_CREDENTIALS_*_JSON в переменные окружения")
            return {}
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации структуры папок: {e}")
            logger.exception("Полная трассировка ошибки:")
            logger.warning("Google Drive функции будут недоступны")
            return {}
    
    def _get_or_create_bot_folder(self, google_service: GoogleService) -> str:
        """
        Получить или создать главную папку бота в новой корневой папке
        
        Args:
            google_service: Экземпляр GoogleService
        
        Returns:
            ID папки бота
        """
        # Сначала проверяем, задана ли папка в настройках
        if settings.GOOGLE_DRIVE_FOLDER_ID:
            logger.info(f"Используется папка из настроек: {settings.GOOGLE_DRIVE_FOLDER_ID}")
            self._bot_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
            return settings.GOOGLE_DRIVE_FOLDER_ID
        
        # Ищем существующую папку в новой корневой папке
        try:
            folder_id = google_service.get_folder_by_name(
                BOT_FOLDER_NAME,
                parent_folder_id=ROOT_FOLDER_ID,
                background=False
            )
            
            if folder_id:
                logger.info(f"✅ Найдена существующая папка '{BOT_FOLDER_NAME}': {folder_id}")
                self._bot_folder_id = folder_id
                return folder_id
            
            # Создаём новую папку в новой корневой папке
            logger.info(f"📁 Создаём новую папку '{BOT_FOLDER_NAME}' в корневой папке {ROOT_FOLDER_ID}...")
            folder_id = google_service.create_folder(
                BOT_FOLDER_NAME,
                parent_folder_id=ROOT_FOLDER_ID,
                background=False
            )
            logger.info(f"✅ Папка создана: {folder_id}")
            self._bot_folder_id = folder_id
            return folder_id
            
        except Exception as e:
            logger.error(f"❌ Ошибка при поиске/создании папки бота: {e}")
            logger.exception("Полная трассировка ошибки:")
            raise
    
    def get_support_folder_id(self) -> str:
        """Получить ID папки для файлов поддержки"""
        if not self._support_folder_id:
            try:
                google_service = self._get_google_service()
                bot_folder_id = self.get_bot_folder_id()
                self._support_folder_id = google_service.get_or_create_folder(
                    "Support",
                    parent_folder_id=bot_folder_id,
                    background=False
                )
            except Exception as e:
                logger.error(f"Ошибка получения папки поддержки: {e}")
                # Fallback: используем папку из настроек
                return settings.GOOGLE_DRIVE_FOLDER_ID or ROOT_FOLDER_ID
        return self._support_folder_id
    
    def get_bot_folder_id(self) -> str:
        """Получить ID главной папки бота"""
        if not self._bot_folder_id:
            if settings.GOOGLE_DRIVE_FOLDER_ID:
                self._bot_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
                return self._bot_folder_id
            
            # Инициализируем структуру, если ещё не инициализирована
            if not self._initialized:
                self.initialize_structure()
            
            # Если после инициализации папка всё ещё не задана, пробуем найти
            if not self._bot_folder_id:
                google_service = self._get_google_service()
                self._bot_folder_id = self._get_or_create_bot_folder(google_service)
        
        return self._bot_folder_id
    
    def get_tasks_folder_id(self) -> str:
        """Получить ID папки для задач"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        return google_service.get_or_create_folder(
            "Tasks",
            parent_folder_id=bot_folder_id,
            background=False
        )
    
    def get_gallery_folder_id(self) -> str:
        """Получить ID папки для галереи проектов"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        return google_service.get_or_create_folder(
            "Gallery",
            parent_folder_id=bot_folder_id,
            background=False
        )
    
    def get_equipment_folder_id(self) -> str:
        """Получить ID папки для оборудования (BEST Channel Bot)"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        return google_service.get_or_create_folder(
            "Equipment",
            parent_folder_id=bot_folder_id,
            background=False
        )
    
    def get_users_folder_id(self) -> str:
        """Получить ID папки для пользователей"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        return google_service.get_or_create_folder(
            "Users",
            parent_folder_id=bot_folder_id,
            background=False
        )
    
    def get_templates_folder_id(self) -> str:
        """Получить ID папки для шаблонов задач"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        
        # Создаём структуру: Templates/ -> Coordinators/, VP4PR/
        templates_folder_id = google_service.get_or_create_folder(
            "Templates",
            parent_folder_id=bot_folder_id,
            background=False
        )
        
        # Создаём подпапки
        google_service.get_or_create_folder(
            "Coordinators",
            parent_folder_id=templates_folder_id,
            background=False
        )
        
        google_service.get_or_create_folder(
            "VP4PR",
            parent_folder_id=templates_folder_id,
            background=False
        )
        
        return templates_folder_id
    
    def create_task_folder(self, task_id: str, task_name: str) -> Dict[str, str]:
        """
        Создать структуру папок для задачи
        
        Структура:
        - Tasks/
          - {task_id}_{task_name}/
            - materials/  (материалы задачи)
            - final/  (финальные работы)
            - drafts/  (черновики)
        
        Args:
            task_id: ID задачи
            task_name: Название задачи (для имени папки)
        
        Returns:
            Словарь с ID папок
        """
        google_service = self._get_google_service()
        tasks_folder_id = self.get_tasks_folder_id()
        
        # Создаём папку задачи (имя: {task_id}_{task_name})
        safe_task_name = "".join(c for c in task_name if c.isalnum() or c in (' ', '-', '_')).strip()[:50]
        task_folder_name = f"{task_id}_{safe_task_name}"
        
        task_folder_id = google_service.create_folder(
            task_folder_name,
            parent_folder_id=tasks_folder_id,
            background=False
        )
        
        # Создаём подпапки
        materials_folder_id = google_service.create_folder(
            "materials",
            parent_folder_id=task_folder_id,
            background=False
        )
        
        final_folder_id = google_service.create_folder(
            "final",
            parent_folder_id=task_folder_id,
            background=False
        )
        
        drafts_folder_id = google_service.create_folder(
            "drafts",
            parent_folder_id=task_folder_id,
            background=False
        )
        
        logger.info(f"✅ Создана структура папок для задачи {task_id}: {task_folder_id}")
        
        return {
            "task_folder_id": task_folder_id,
            "materials_folder_id": materials_folder_id,
            "final_folder_id": final_folder_id,
            "drafts_folder_id": drafts_folder_id,
        }


# Singleton instance НЕ создаём при импорте - пусть создаётся лениво
# Это позволяет избежать ошибок при отсутствии Google credentials
# drive_structure = DriveStructureService()  # Удалено - создаём только при необходимости
