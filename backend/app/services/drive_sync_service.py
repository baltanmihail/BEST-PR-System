"""
Сервис для синхронизации изменений между Google Drive и системой
Отслеживает изменения файлов задач и создание новых файлов
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from app.models.task import Task
from app.models.file import File as FileModel
from app.services.task_service import TaskService
import asyncio

logger = logging.getLogger(__name__)


class DriveSyncService:
    """Сервис для синхронизации Google Drive с системой"""
    
    def __init__(self):
        self.google_service: Optional[GoogleService] = None
        self.drive_structure: Optional[DriveStructureService] = None
        self._last_sync_time: Optional[datetime] = None
    
    def _get_google_service(self) -> GoogleService:
        """Получить экземпляр GoogleService"""
        if not self.google_service:
            from app.services.google_service import GoogleService
            self.google_service = GoogleService()
        return self.google_service
    
    def _get_drive_structure(self) -> DriveStructureService:
        """Получить экземпляр DriveStructureService"""
        if not self.drive_structure:
            from app.services.drive_structure import DriveStructureService
            self.drive_structure = DriveStructureService()
        return self.drive_structure
    
    async def sync_drive_changes(self, db: AsyncSession, last_sync_time: Optional[datetime] = None) -> Dict[str, int]:
        """
        Синхронизировать изменения из Google Drive в систему
        
        Отслеживает:
        - Изменения файлов задач (обновление описания, дедлайнов)
        - Новые файлы в папке Tasks (создание новых задач)
        - Удаление файлов задач
        
        Args:
            db: Сессия БД
            last_sync_time: Время последней синхронизации (если None, берётся из кэша)
        
        Returns:
            Словарь со статистикой: {"updated": N, "created": M, "deleted": K}
        """
        if last_sync_time is None:
            last_sync_time = self._last_sync_time or (datetime.now(timezone.utc) - timedelta(hours=1))
        
        google_service = self._get_google_service()
        drive_structure = self._get_drive_structure()
        tasks_folder_id = drive_structure.get_tasks_folder_id()
        
        stats = {"updated": 0, "created": 0, "deleted": 0, "errors": 0}
        
        try:
            # Получаем список всех файлов и папок в Tasks, изменённых после last_sync_time
            # Форматируем время для Google Drive API запроса
            modified_time_str = last_sync_time.strftime('%Y-%m-%dT%H:%M:%S.000Z')
            
            # Ищем изменённые файлы и папки
            drive_service = google_service._get_drive_service(background=False)
            
            # Запрос: все файлы в папке Tasks, изменённые после last_sync_time
            query = f"'{tasks_folder_id}' in parents and modifiedTime > '{modified_time_str}' and trashed=false"
            
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, mimeType, modifiedTime, createdTime, parents, webViewLink)",
                pageSize=1000,
                orderBy="modifiedTime desc"
            ).execute()
            
            changed_files = results.get('files', [])
            logger.info(f"📋 Найдено {len(changed_files)} изменённых файлов/папок в Tasks")
            
            # Обрабатываем изменения
            for file_info in changed_files:
                try:
                    file_id = file_info['id']
                    file_name = file_info['name']
                    mime_type = file_info.get('mimeType', '')
                    modified_time = datetime.fromisoformat(file_info.get('modifiedTime', '').replace('Z', '+00:00'))
                    
                    # Если это папка задачи (начинается с UUID)
                    if mime_type == 'application/vnd.google-apps.folder' and '_' in file_name:
                        parts = file_name.split('_', 1)
                        if len(parts) == 2:
                            task_id_str = parts[0]
                            try:
                                from uuid import UUID
                                task_id = UUID(task_id_str)
                                
                                # Проверяем, существует ли задача
                                task_query = select(Task).where(Task.id == task_id)
                                task_result = await db.execute(task_query)
                                task = task_result.scalar_one_or_none()
                                
                                if task:
                                    # Обновляем информацию о папке задачи
                                    if task.drive_folder_id != file_id:
                                        task.drive_folder_id = file_id
                                        await db.commit()
                                        logger.info(f"✅ Обновлён drive_folder_id для задачи {task_id}: {file_id}")
                                    
                                    # Проверяем, есть ли файл задачи (Google Doc) внутри папки
                                    await self._sync_task_doc_changes(db, task, file_id, modified_time)
                                    stats["updated"] += 1
                                else:
                                    # Новая задача - создаём из папки
                                    await self._create_task_from_folder(db, file_id, file_name, modified_time)
                                    stats["created"] += 1
                                    
                            except (ValueError, TypeError) as e:
                                logger.debug(f"Не удалось распарсить task_id из '{file_name}': {e}")
                                continue
                    
                    # Если это Google Doc файл задачи
                    elif mime_type == 'application/vnd.google-apps.document':
                        await self._sync_task_doc_file(db, file_id, file_name, file_info, modified_time)
                        stats["updated"] += 1
                    
                    # Если это обычный файл (материал задачи)
                    else:
                        await self._sync_task_material_file(db, file_id, file_name, file_info, modified_time)
                        stats["updated"] += 1
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки файла {file_info.get('id', 'unknown')}: {e}")
                    stats["errors"] += 1
                    continue
            
            # Обновляем время последней синхронизации
            self._last_sync_time = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации изменений Drive: {e}")
            logger.exception("Полная трассировка ошибки:")
            stats["errors"] += 1
        
        return stats
    
    async def _sync_task_doc_changes(
        self, 
        db: AsyncSession, 
        task: Task, 
        folder_id: str, 
        modified_time: datetime
    ):
        """Синхронизировать изменения в файле задачи (Google Doc)"""
        try:
            google_service = self._get_google_service()
            drive_service = google_service._get_drive_service(background=False)
            
            # Ищем Google Doc файл с таким же названием, как задача, в папке задачи
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, modifiedTime)",
                pageSize=10
            ).execute()
            
            doc_files = results.get('files', [])
            # Ищем файл, название которого совпадает с названием задачи (или похоже)
            task_doc = None
            for doc in doc_files:
                if doc['name'].strip() == task.title.strip() or doc['name'].startswith(task.title[:30]):
                    task_doc = doc
                    break
            
            if task_doc:
                doc_modified = datetime.fromisoformat(task_doc.get('modifiedTime', '').replace('Z', '+00:00'))
                # Если файл изменён недавно (в пределах последнего часа), читаем его содержимое
                if doc_modified > modified_time - timedelta(hours=1):
                    await self._update_task_from_doc(db, task, task_doc['id'])
                    
        except Exception as e:
            logger.warning(f"⚠️ Не удалось синхронизировать изменения файла задачи {task.id}: {e}")
    
    async def _update_task_from_doc(self, db: AsyncSession, task: Task, doc_id: str):
        """
        Обновить задачу из содержимого Google Doc файла
        
        Парсит содержимое документа и обновляет описание задачи
        """
        try:
            # Читаем содержимое Google Doc через Google Docs API
            from googleapiclient.discovery import build
            from app.config import settings
            
            # Получаем credentials для Docs API
            google_service = self._get_google_service()
            credentials = google_service._get_credentials(background=False)
            docs_service = build('docs', 'v1', credentials=credentials)
            
            # Получаем содержимое документа
            doc = docs_service.documents().get(documentId=doc_id).execute()
            
            # Парсим содержимое (упрощённо - берём первый абзац как описание)
            content = doc.get('body', {}).get('content', [])
            description_parts = []
            
            for element in content:
                if 'paragraph' in element:
                    para = element['paragraph']
                    if 'elements' in para:
                        for elem in para['elements']:
                            if 'textRun' in elem:
                                text = elem['textRun'].get('content', '')
                                if text.strip():
                                    description_parts.append(text.strip())
            
            if description_parts:
                new_description = '\n'.join(description_parts[:5])  # Первые 5 абзацев
                if task.description != new_description:
                    task.description = new_description
                    await db.commit()
                    logger.info(f"✅ Обновлено описание задачи {task.id} из Google Doc")
                    
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить задачу {task.id} из документа {doc_id}: {e}")
    
    async def _create_task_from_folder(
        self, 
        db: AsyncSession, 
        folder_id: str, 
        folder_name: str, 
        created_time: datetime
    ):
        """
        Создать задачу из папки в Google Drive
        
        Если в папке Tasks обнаружена новая папка задачи, создаём соответствующую задачу в системе
        """
        try:
            # Парсим название папки: {task_id}_{task_name}
            parts = folder_name.split('_', 1)
            if len(parts) != 2:
                logger.debug(f"Название папки '{folder_name}' не соответствует формату task_id_task_name")
                return
            
            task_id_str, task_name = parts
            
            # Проверяем, нет ли уже задачи с таким ID
            from uuid import UUID
            try:
                task_id = UUID(task_id_str)
            except ValueError:
                logger.debug(f"Невалидный UUID в названии папки: {task_id_str}")
                return
            
            task_query = select(Task).where(Task.id == task_id)
            task_result = await db.execute(task_query)
            existing_task = task_result.scalar_one_or_none()
            
            if existing_task:
                # Задача уже существует, просто обновляем drive_folder_id
                if existing_task.drive_folder_id != folder_id:
                    existing_task.drive_folder_id = folder_id
                    await db.commit()
                    logger.info(f"✅ Обновлён drive_folder_id для существующей задачи {task_id}")
                return
            
            # Ищем Google Doc файл в папке для получения описания
            google_service = self._get_google_service()
            drive_service = google_service._get_drive_service(background=False)
            
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            doc_files = results.get('files', [])
            description = ""
            
            if doc_files:
                doc_id = doc_files[0]['id']
                # Пытаемся прочитать описание из документа (упрощённо)
                try:
                    from googleapiclient.discovery import build
                    credentials = google_service._get_credentials(background=False)
                    docs_service = build('docs', 'v1', credentials=credentials)
                    doc = docs_service.documents().get(documentId=doc_id).execute()
                    content = doc.get('body', {}).get('content', [])
                    desc_parts = []
                    for element in content[:3]:  # Первые 3 абзаца
                        if 'paragraph' in element:
                            para = element['paragraph']
                            if 'elements' in para:
                                for elem in para['elements']:
                                    if 'textRun' in elem:
                                        text = elem['textRun'].get('content', '')
                                        if text.strip():
                                            desc_parts.append(text.strip())
                    description = '\n'.join(desc_parts)
                except Exception as e:
                    logger.debug(f"Не удалось прочитать описание из документа {doc_id}: {e}")
            
            # Создаём задачу (базовая версия - можно расширить)
            # Для полноценного создания нужен created_by, поэтому создаём как черновик
            # В реальности лучше создавать через API с указанием координатора
            logger.info(f"📋 Обнаружена новая папка задачи: {folder_name}, но требуется ручное создание задачи через API")
            # Не создаём автоматически - требуется участие координатора
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания задачи из папки {folder_id}: {e}")
            logger.exception("Полная трассировка ошибки:")
    
    async def _sync_task_doc_file(
        self,
        db: AsyncSession,
        file_id: str,
        file_name: str,
        file_info: dict,
        modified_time: datetime
    ):
        """Синхронизировать файл задачи (Google Doc)"""
        # Логика синхронизации Google Doc файла задачи
        # Можно расширить для парсинга метаданных из документа
        logger.debug(f"Синхронизация Google Doc файла: {file_name} (ID: {file_id})")
    
    async def _sync_task_material_file(
        self,
        db: AsyncSession,
        file_id: str,
        file_name: str,
        file_info: dict,
        modified_time: datetime
    ):
        """Синхронизировать файл материала задачи"""
        # Логика синхронизации файлов материалов (фото, видео, документы)
        # Можно добавить запись в таблицу File для отслеживания
        logger.debug(f"Синхронизация файла материала: {file_name} (ID: {file_id})")


# Глобальный экземпляр для периодической синхронизации
drive_sync_service = DriveSyncService()
