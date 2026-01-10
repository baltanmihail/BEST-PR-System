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
            - Admin/  (админская папка)
              - Coordinators/  (папка для координаторов)
                - SMM/  (шаблоны и информация для координатора SMM)
                - Design/  (шаблоны и информация для координатора Design)
                - Channel/  (шаблоны и информация для координатора Channel)
                - PR-FR/  (шаблоны и информация для координатора PR-FR)
              - VP4PR/  (шаблоны и информация для VP4PR)
        
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
            
            # Создаём админскую папку
            admin_folder_id = google_service.get_or_create_folder(
                "Admin",
                parent_folder_id=bot_folder_id,
                background=False
            )
            logger.info(f"✅ Админская папка 'Admin': {admin_folder_id}")
            
            # Создаём подпапку для координаторов внутри админской папки
            coordinators_folder_id = google_service.get_or_create_folder(
                "Coordinators",
                parent_folder_id=admin_folder_id,
                background=False
            )
            logger.info(f"✅ Папка координаторов 'Coordinators': {coordinators_folder_id}")
            
            # Создаём подпапки для каждого координатора
            coordinators_subfolders = {
                "SMM": google_service.get_or_create_folder(
                    "SMM",
                    parent_folder_id=coordinators_folder_id,
                    background=False
                ),
                "Design": google_service.get_or_create_folder(
                    "Design",
                    parent_folder_id=coordinators_folder_id,
                    background=False
                ),
                "Channel": google_service.get_or_create_folder(
                    "Channel",
                    parent_folder_id=coordinators_folder_id,
                    background=False
                ),
                "PR-FR": google_service.get_or_create_folder(
                    "PR-FR",
                    parent_folder_id=coordinators_folder_id,
                    background=False
                ),
            }
            
            for name, folder_id in coordinators_subfolders.items():
                logger.info(f"✅ Папка координатора '{name}': {folder_id}")
            
            # Создаём подпапку для VP4PR внутри админской папки
            vp4pr_folder_id = google_service.get_or_create_folder(
                "VP4PR",
                parent_folder_id=admin_folder_id,
                background=False
            )
            logger.info(f"✅ Папка VP4PR: {vp4pr_folder_id}")
            
            structure = {
                "bot_folder_id": bot_folder_id,
                "tasks_folder_id": tasks_folder_id,
                "gallery_folder_id": gallery_folder_id,
                "equipment_folder_id": equipment_folder_id,
                "support_folder_id": support_folder_id,
                "users_folder_id": users_folder_id,
                "admin_folder_id": admin_folder_id,
                "coordinators_folder_id": coordinators_folder_id,
                "vp4pr_folder_id": vp4pr_folder_id,
                "coordinators_subfolders": coordinators_subfolders,
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
        # Сначала проверяем, задана ли папка в настройках и существует ли она
        if settings.GOOGLE_DRIVE_FOLDER_ID:
            try:
                # Проверяем, существует ли папка
                drive_service = google_service._get_drive_service(background=False)
                drive_service.files().get(fileId=settings.GOOGLE_DRIVE_FOLDER_ID, fields='id').execute()
                logger.info(f"✅ Используется папка из настроек: {settings.GOOGLE_DRIVE_FOLDER_ID}")
                self._bot_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
                return settings.GOOGLE_DRIVE_FOLDER_ID
            except Exception as e:
                logger.warning(f"⚠️ Папка {settings.GOOGLE_DRIVE_FOLDER_ID} не найдена (возможно, была удалена): {e}")
                logger.info("📁 Создаём новую папку вместо удалённой...")
                # Очищаем кэш и продолжаем создание новой папки
                self._bot_folder_id = None
        
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
        google_service = self._get_google_service()
        
        # Если есть кэшированный ID, убеждаемся, что папка существует (могла быть удалена вручную)
        if self._bot_folder_id:
            try:
                drive_service = google_service._get_drive_service(background=False)
                drive_service.files().get(fileId=self._bot_folder_id, fields='id').execute()
            except Exception as e:
                logger.warning(f"⚠️ Кэшированная папка бота {self._bot_folder_id} не найдена: {e}")
                logger.info("📁 Создаём новую папку...")
                self._bot_folder_id = None
        
        if not self._bot_folder_id:
            if settings.GOOGLE_DRIVE_FOLDER_ID:
                # Проверяем, существует ли папка
                try:
                    drive_service = google_service._get_drive_service(background=False)
                    drive_service.files().get(fileId=settings.GOOGLE_DRIVE_FOLDER_ID, fields='id').execute()
                    logger.info(f"✅ Используется папка из настроек: {settings.GOOGLE_DRIVE_FOLDER_ID}")
                    self._bot_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
                    return self._bot_folder_id
                except Exception as e:
                    logger.warning(f"⚠️ Папка {settings.GOOGLE_DRIVE_FOLDER_ID} не найдена (возможно, была удалена): {e}")
                    logger.info("📁 Создаём новую папку...")
                    # Очищаем кэш и продолжаем создание новой папки
                    self._bot_folder_id = None
            
            # Инициализируем структуру, если ещё не инициализирована
            if not self._initialized:
                self.initialize_structure()
            
            # Если после инициализации папка всё ещё не задана, пробуем найти/создать
            if not self._bot_folder_id:
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
    
    def get_admin_folder_id(self) -> str:
        """Получить ID админской папки"""
        google_service = self._get_google_service()
        bot_folder_id = self.get_bot_folder_id()
        return google_service.get_or_create_folder(
            "Admin",
            parent_folder_id=bot_folder_id,
            background=False
        )
    
    def get_coordinators_folder_id(self) -> str:
        """Получить ID папки координаторов"""
        google_service = self._get_google_service()
        admin_folder_id = self.get_admin_folder_id()
        return google_service.get_or_create_folder(
            "Coordinators",
            parent_folder_id=admin_folder_id,
            background=False
        )
    
    def get_vp4pr_folder_id(self) -> str:
        """Получить ID папки VP4PR"""
        google_service = self._get_google_service()
        admin_folder_id = self.get_admin_folder_id()
        return google_service.get_or_create_folder(
            "VP4PR",
            parent_folder_id=admin_folder_id,
            background=False
        )
    
    def get_task_template_subfolder_id(self, category: str) -> str:
        """
        Получить ID подпапки для шаблонов задач по категории
        
        Args:
            category: Категория шаблона (coordinator_smm, coordinator_design, coordinator_channel, coordinator_prfr, vp4pr)
        
        Returns:
            ID папки для данной категории
        """
        google_service = self._get_google_service()
        
        # Маппинг категорий на названия папок
        category_to_folder = {
            "coordinator_smm": "SMM",
            "coordinator_design": "Design",
            "coordinator_channel": "Channel",
            "coordinator_prfr": "PR-FR",
            "vp4pr": "VP4PR",
        }
        
        folder_name = category_to_folder.get(category, "Custom")
        
        # Для VP4PR используем папку VP4PR напрямую из Admin
        if category == "vp4pr":
            return self.get_vp4pr_folder_id()
        
        # Для координаторов используем папку Coordinators -> конкретный координатор
        coordinators_folder_id = self.get_coordinators_folder_id()
        return google_service.get_or_create_folder(
            folder_name,
            parent_folder_id=coordinators_folder_id,
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
    
    
    def create_task_folder(self, task_id: str, task_name: str, task_description: str = None, task_data: dict = None) -> Dict[str, str]:
        """
        Создать структуру папок для задачи и файл задачи (Google Doc)
        
        Структура:
        - Tasks/
          - {task_id}_{task_name}/
            - {task_name}.doc  (файл с описанием задачи)
            - materials/  (материалы задачи)
            - final/  (финальные работы)
            - drafts/  (черновики)
        
        Args:
            task_id: ID задачи
            task_name: Название задачи (для имени папки)
            task_description: Описание задачи (для файла)
            task_data: Полные данные задачи (dict) для создания детального описания
        
        Returns:
            Словарь с ID папок и файла задачи
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
        
        # Создаём Google Doc файл с описанием задачи
        task_doc_content = self._generate_task_doc_content(task_name, task_description, task_data)
        task_doc_id = None
        try:
            task_doc = google_service.create_doc(
                title=task_name,
                content=task_doc_content,
                folder_id=task_folder_id,
                background=False
            )
            task_doc_id = task_doc.get("id")
            logger.info(f"✅ Создан файл задачи '{task_name}' (ID: {task_doc_id})")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось создать файл задачи '{task_name}': {e}")
        
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
            "task_doc_id": task_doc_id,
            "materials_folder_id": materials_folder_id,
            "final_folder_id": final_folder_id,
            "drafts_folder_id": drafts_folder_id,
        }
    
    def _generate_task_doc_content(self, task_name: str, task_description: str = None, task_data: dict = None) -> str:
        """
        Генерировать содержимое Google Doc файла задачи
        
        Args:
            task_name: Название задачи
            task_description: Описание задачи
            task_data: Полные данные задачи (для более детального описания)
        
        Returns:
            HTML-содержимое документа
        """
        from app.config import settings
        
        content = f"""<h1>{task_name}</h1>
        
<h2>Описание задачи</h2>
<p>{task_description or 'Описание отсутствует'}</p>
"""
        
        if task_data:
            content += f"""
<h2>Детали задачи</h2>
<ul>
"""
            if task_data.get('type'):
                content += f"<li><strong>Тип:</strong> {task_data['type']}</li>\n"
            if task_data.get('priority'):
                content += f"<li><strong>Приоритет:</strong> {task_data['priority']}</li>\n"
            if task_data.get('due_date'):
                content += f"<li><strong>Дедлайн:</strong> {task_data['due_date']}</li>\n"
            if task_data.get('status'):
                content += f"<li><strong>Статус:</strong> {task_data['status']}</li>\n"
            
            content += "</ul>\n"
        
        content += f"""
<h2>Ссылки</h2>
<ul>
    <li><a href="{settings.FRONTEND_URL}/tasks/{task_data.get('id', '') if task_data else ''}">Открыть карточку задачи в системе</a></li>
</ul>

<h2>Материалы</h2>
<p>Материалы задачи находятся в подпапках:</p>
<ul>
    <li><strong>materials/</strong> - исходные материалы, референсы, брифы</li>
    <li><strong>drafts/</strong> - черновики, промежуточные версии</li>
    <li><strong>final/</strong> - финальные работы</li>
</ul>

<p><em>Создано автоматически системой BEST PR System</em></p>
"""
        return content


# Singleton instance НЕ создаём при импорте - пусть создаётся лениво
# Это позволяет избежать ошибок при отсутствии Google credentials
# drive_structure = DriveStructureService()  # Удалено - создаём только при необходимости
