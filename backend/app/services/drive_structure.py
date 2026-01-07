"""
Инициализация структуры папок в Google Drive для BEST PR System
Создаёт папки при первом запуске
"""
import logging
from typing import Optional

from app.config import settings
from app.services.google_service import GoogleService

logger = logging.getLogger(__name__)

# ID папки координаторов на Google Drive
COORDINATORS_FOLDER_ID = "10A2GVTrYq8_Rm6pBDvQUEQxibHFdWxBd"

# Название папки для бота в папке координаторов
BOT_FOLDER_NAME = "BEST PR System"


class DriveStructureService:
    """Сервис для управления структурой папок в Google Drive"""
    
    def __init__(self):
        self.google_service = GoogleService()
        self._bot_folder_id: Optional[str] = None
        self._support_folder_id: Optional[str] = None
        self._files_folder_id: Optional[str] = None
    
    def initialize_structure(self) -> dict:
        """
        Инициализировать структуру папок в Google Drive
        
        Структура:
        - BEST (Координаторы)/
          - BEST PR System/  (папка бота)
            - Поддержка/  (файлы от пользователей)
            - Файлы/  (общие файлы)
            - Задачи/  (файлы связанные с задачами)
            - Оборудование/  (документы по оборудованию)
        
        Returns:
            Словарь с ID папок
        """
        try:
            logger.info("📁 Инициализация структуры папок Google Drive...")
            
            # 1. Создаём главную папку бота в папке координаторов
            bot_folder_id = self._get_or_create_bot_folder()
            logger.info(f"✅ Папка бота: {bot_folder_id}")
            
            # 2. Создаём подпапки
            support_folder_id = self._get_or_create_folder(
                "Поддержка",
                bot_folder_id
            )
            logger.info(f"✅ Папка 'Поддержка': {support_folder_id}")
            
            files_folder_id = self._get_or_create_folder(
                "Файлы",
                bot_folder_id
            )
            logger.info(f"✅ Папка 'Файлы': {files_folder_id}")
            
            tasks_folder_id = self._get_or_create_folder(
                "Задачи",
                bot_folder_id
            )
            logger.info(f"✅ Папка 'Задачи': {tasks_folder_id}")
            
            equipment_folder_id = self._get_or_create_folder(
                "Оборудование",
                bot_folder_id
            )
            logger.info(f"✅ Папка 'Оборудование': {equipment_folder_id}")
            
            structure = {
                "bot_folder_id": bot_folder_id,
                "support_folder_id": support_folder_id,
                "files_folder_id": files_folder_id,
                "tasks_folder_id": tasks_folder_id,
                "equipment_folder_id": equipment_folder_id,
            }
            
            # Сохраняем в настройки (если нужно)
            if not settings.GOOGLE_DRIVE_FOLDER_ID:
                logger.info(f"💡 Сохраните GOOGLE_DRIVE_FOLDER_ID={bot_folder_id} в переменные окружения")
            
            logger.info("✅ Структура папок Google Drive инициализирована")
            return structure
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации структуры папок: {e}")
            raise
    
    def _get_or_create_bot_folder(self) -> str:
        """Получить или создать главную папку бота"""
        # Сначала проверяем, задана ли папка в настройках
        if settings.GOOGLE_DRIVE_FOLDER_ID:
            logger.info(f"Используется папка из настроек: {settings.GOOGLE_DRIVE_FOLDER_ID}")
            self._bot_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
            return settings.GOOGLE_DRIVE_FOLDER_ID
        
        # Ищем существующую папку в папке координаторов
        try:
            drive_service = self.google_service._get_drive_service()
            
            # Ищем папку с нужным именем в папке координаторов
            query = f"name='{BOT_FOLDER_NAME}' and '{COORDINATORS_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=10
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"Найдена существующая папка: {folder_id}")
                self._bot_folder_id = folder_id
                return folder_id
            
            # Создаём новую папку
            logger.info(f"Создаём новую папку '{BOT_FOLDER_NAME}' в папке координаторов...")
            folder_id = self.google_service.create_folder(
                BOT_FOLDER_NAME,
                parent_folder_id=COORDINATORS_FOLDER_ID
            )
            logger.info(f"✅ Папка создана: {folder_id}")
            self._bot_folder_id = folder_id
            return folder_id
            
        except Exception as e:
            logger.error(f"Ошибка при поиске/создании папки бота: {e}")
            logger.warning("Попытка создать папку напрямую...")
            # Fallback: создаём папку напрямую
            try:
                folder_id = self.google_service.create_folder(
                    BOT_FOLDER_NAME,
                    parent_folder_id=COORDINATORS_FOLDER_ID
                )
                self._bot_folder_id = folder_id
                return folder_id
            except Exception as e2:
                logger.error(f"Критическая ошибка создания папки: {e2}")
                raise
    
    def _get_or_create_folder(self, folder_name: str, parent_folder_id: str) -> str:
        """Получить или создать подпапку"""
        try:
            drive_service = self.google_service._get_drive_service()
            
            # Ищем существующую папку
            query = f"name='{folder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=10
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Создаём новую папку
            return self.google_service.create_folder(
                folder_name,
                parent_folder_id=parent_folder_id
            )
            
        except Exception as e:
            logger.error(f"Ошибка при поиске/создании папки '{folder_name}': {e}")
            # Fallback: создаём папку напрямую
            return self.google_service.create_folder(
                folder_name,
                parent_folder_id=parent_folder_id
            )
    
    def get_support_folder_id(self) -> str:
        """Получить ID папки для файлов поддержки"""
        if not self._support_folder_id:
            try:
                bot_folder_id = self._get_or_create_bot_folder()
                self._support_folder_id = self._get_or_create_folder(
                    "Поддержка",
                    bot_folder_id
                )
            except Exception as e:
                logger.error(f"Ошибка получения папки поддержки: {e}")
                # Fallback: используем папку из настроек
                return settings.GOOGLE_DRIVE_FOLDER_ID or COORDINATORS_FOLDER_ID
        return self._support_folder_id
    
    def get_bot_folder_id(self) -> str:
        """Получить ID главной папки бота"""
        if not self._bot_folder_id:
            self._bot_folder_id = self._get_or_create_bot_folder()
        return self._bot_folder_id


# Singleton instance
drive_structure = DriveStructureService()
