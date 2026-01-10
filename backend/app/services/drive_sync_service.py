"""
Сервис для синхронизации изменений между Google Drive и системой
Отслеживает изменения файлов задач и создание новых файлов
"""
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from app.models.task import Task, StageStatus
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
                orderBy="modifiedTime desc",
                supportsAllDrives=True,  # Поддержка Shared Drive
                includeItemsFromAllDrives=True  # Включать файлы из Shared Drive
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
                    
                    # Если это папка задачи (может быть с UUID префиксом или без)
                    if mime_type == 'application/vnd.google-apps.folder':
                        # Проверяем, есть ли UUID префикс в названии
                        parts = file_name.split('_', 1)
                        task_id = None
                        
                        if len(parts) == 2:
                            task_id_str = parts[0]
                            try:
                                from uuid import UUID
                                task_id = UUID(task_id_str)
                            except (ValueError, TypeError):
                                pass  # Не UUID, значит это обычное название папки
                        
                        if task_id:
                            # Папка с UUID - проверяем существование задачи
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
                        else:
                            # Папка без UUID - возможно, это новая задача, созданная вручную
                            # Проверяем, нет ли уже задачи с таким drive_folder_id
                            task_query = select(Task).where(Task.drive_folder_id == file_id)
                            task_result = await db.execute(task_query)
                            existing_task = task_result.scalar_one_or_none()
                            
                            if not existing_task:
                                # Попытаемся создать задачу из этой папки (без UUID)
                                await self._create_task_from_folder(db, file_id, file_name, modified_time)
                                stats["created"] += 1
                            else:
                                # Обновляем существующую задачу
                                await self._sync_task_doc_changes(db, existing_task, file_id, modified_time)
                                stats["updated"] += 1
                    
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
                pageSize=10,
                supportsAllDrives=True,  # Поддержка Shared Drive
                includeItemsFromAllDrives=True  # Включать файлы из Shared Drive
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
        
        Автоматически парсит Google Doc файл в папке для извлечения метаданных задачи:
        - Тип задачи (SMM, Design, Channel, PR-FR)
        - Приоритет (low, medium, high, critical)
        - Дедлайн
        - Этапы (stages)
        - Описание
        
        Формат шаблона в Google Doc (опционально):
        # Название задачи
        
        **Тип:** SMM|Design|Channel|PR-FR
        **Приоритет:** low|medium|high|critical
        **Дедлайн:** YYYY-MM-DD
        **Этапы:**
        - Название этапа 1 (дата: YYYY-MM-DD, цвет: green|yellow|red|purple|blue)
        - Название этапа 2 (дата: YYYY-MM-DD)
        
        Описание задачи...
        """
        try:
            # Парсим название папки: {task_id}_{task_name} или просто {task_name}
            # Если формат task_id_task_name - используем ID, иначе генерируем новый
            parts = folder_name.split('_', 1)
            task_id = None
            task_title = folder_name
            
            if len(parts) == 2:
                task_id_str, task_name = parts
                # Проверяем, валидный ли UUID
                from uuid import UUID
                try:
                    task_id = UUID(task_id_str)
                    task_title = task_name
                except ValueError:
                    # Не UUID, значит это просто название с подчёркиванием
                    task_title = folder_name
            
            # Если задан task_id, проверяем существование задачи
            if task_id:
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
            
            # Ищем Google Doc файл в папке для парсинга метаданных
            google_service = self._get_google_service()
            drive_service = google_service._get_drive_service(background=False)
            
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=10,
                supportsAllDrives=True,  # Поддержка Shared Drive
                includeItemsFromAllDrives=True  # Включать файлы из Shared Drive
            ).execute()
            
            doc_files = results.get('files', [])
            if not doc_files:
                logger.debug(f"В папке {folder_name} не найден Google Doc файл")
                return
            
            # Берём первый Google Doc файл (обычно это файл задачи)
            doc_id = doc_files[0]['id']
            doc_name = doc_files[0].get('name', '')
            
            # Парсим метаданные из документа
            task_metadata = await self._parse_task_doc_metadata(google_service, doc_id)
            
            # Если не удалось распарсить, используем базовые значения
            task_type = task_metadata.get('type', 'smm')
            priority = task_metadata.get('priority', 'medium')
            description = task_metadata.get('description', '')
            due_date = task_metadata.get('due_date')
            stages_data = task_metadata.get('stages', [])
            
            # Если название задачи не задано в метаданных, используем название документа или папки
            if not task_metadata.get('title'):
                task_title = doc_name.replace('.gdoc', '').replace('.docx', '') or task_title
            
            # Ищем системного пользователя (VP4PR или первого координатора) для created_by
            from app.models.user import User, UserRole
            system_user_query = select(User).where(
                or_(
                    User.role == UserRole.VP4PR,
                    User.role.in_([
                        UserRole.COORDINATOR_SMM,
                        UserRole.COORDINATOR_DESIGN,
                        UserRole.COORDINATOR_CHANNEL,
                        UserRole.COORDINATOR_PRFR
                    ])
                )
            ).limit(1)
            system_user_result = await db.execute(system_user_query)
            system_user = system_user_result.scalar_one_or_none()
            
            if not system_user:
                logger.warning(f"⚠️ Не найден системный пользователь для создания задачи из папки {folder_name}")
                return
            
            # Создаём задачу через TaskService
            from app.schemas.task import TaskCreate, TaskStageCreate
            from app.models.task import TaskType, TaskPriority
            from datetime import datetime as dt, timezone
            import uuid
            
            try:
                task_type_enum = TaskType(task_type.lower())
            except ValueError:
                task_type_enum = TaskType.SMM  # По умолчанию
            
            try:
                priority_enum = TaskPriority(priority.lower())
            except ValueError:
                priority_enum = TaskPriority.MEDIUM  # По умолчанию
            
            # Парсим дедлайн
            parsed_due_date = None
            if due_date:
                try:
                    if isinstance(due_date, str):
                        parsed_due_date = dt.fromisoformat(due_date.replace('Z', '+00:00'))
                    elif isinstance(due_date, dt):
                        parsed_due_date = due_date
                    if parsed_due_date and parsed_due_date.tzinfo is None:
                        parsed_due_date = parsed_due_date.replace(tzinfo=timezone.utc)
                except Exception as e:
                    logger.debug(f"Не удалось распарсить дедлайн '{due_date}': {e}")
            
            # Формируем этапы
            stages = []
            for stage_idx, stage_data in enumerate(stages_data, 1):
                stage_name = stage_data.get('name', f'Этап {stage_idx}')
                stage_due_date = stage_data.get('due_date')
                stage_color = stage_data.get('color', 'green')
                
                parsed_stage_due = None
                if stage_due_date:
                    try:
                        if isinstance(stage_due_date, str):
                            parsed_stage_due = dt.fromisoformat(stage_due_date.replace('Z', '+00:00'))
                        elif isinstance(stage_due_date, dt):
                            parsed_stage_due = stage_due_date
                        if parsed_stage_due and parsed_stage_due.tzinfo is None:
                            parsed_stage_due = parsed_stage_due.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                
                stages.append(TaskStageCreate(
                    stage_name=stage_name,
                    stage_order=stage_idx,
                    due_date=parsed_stage_due,
                    status_color=stage_color
                ))
            
            # Создаём объект TaskCreate
            task_create = TaskCreate(
                title=task_title,
                description=description or None,
                type=task_type_enum,
                priority=priority_enum,
                due_date=parsed_due_date,
                stages=stages if stages else None,
                equipment_available=False,  # По умолчанию
                script_ready=True  # По умолчанию
            )
            
            # Если задан task_id, создаём задачу с указанным ID
            # Иначе используем TaskService, который сгенерирует новый ID
            from app.models.task import Task, TaskStatus, TaskStage
            
            if task_id:
                # Создаём задачу с указанным ID (папка уже существует с этим ID)
                new_task = Task(
                    id=task_id,
                    title=task_create.title,
                    description=task_create.description,
                    type=task_create.type,
                    priority=task_create.priority,
                    due_date=task_create.due_date,
                    equipment_available=task_create.equipment_available,
                    created_by=system_user.id,
                    status=TaskStatus.DRAFT,  # Создаём как черновик
                    drive_folder_id=folder_id
                )
                db.add(new_task)
                await db.flush()  # Получаем ID задачи
                
                # Добавляем этапы
                if stages:
                    for stage_create in stages:
                        stage = TaskStage(
                            task_id=new_task.id,
                            stage_name=stage_create.stage_name,
                            stage_order=stage_create.stage_order,
                            due_date=stage_create.due_date,
                            status_color=stage_create.status_color,
                            status=StageStatus.PENDING
                        )
                        db.add(stage)
                
                await db.commit()
                await db.refresh(new_task)
                logger.info(f"✅ Создана задача {new_task.id} из папки Drive: {folder_name}")
            else:
                # Используем TaskService для создания задачи
                # Но затем обновим drive_folder_id, так как папка уже существует
                from app.services.task_service import TaskService
                new_task = await TaskService.create_task(
                    db=db,
                    task_data=task_create,
                    created_by=system_user.id
                )
                
                # Обновляем drive_folder_id, так как папка уже существует
                # Также обновляем этапы, если они были созданы TaskService, но нам нужно их заменить
                if stages:
                    # Удаляем этапы, созданные TaskService (если есть)
                    existing_stages_query = select(TaskStage).where(TaskStage.task_id == new_task.id)
                    existing_stages_result = await db.execute(existing_stages_query)
                    for existing_stage in existing_stages_result.scalars().all():
                        await db.delete(existing_stage)
                    
                    # Добавляем этапы из документа
                    for stage_create in stages:
                        stage = TaskStage(
                            task_id=new_task.id,
                            stage_name=stage_create.stage_name,
                            stage_order=stage_create.stage_order,
                            due_date=stage_create.due_date,
                            status_color=stage_create.status_color,
                            status=StageStatus.PENDING
                        )
                        db.add(stage)
                
                new_task.drive_folder_id = folder_id
                await db.commit()
                await db.refresh(new_task)
                logger.info(f"✅ Создана задача {new_task.id} из папки Drive: {folder_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания задачи из папки {folder_id}: {e}")
            logger.exception("Полная трассировка ошибки:")
    
    async def _parse_task_doc_metadata(self, google_service, doc_id: str) -> dict:
        """
        Парсить метаданные задачи из Google Doc файла
        
        Поддерживаемые форматы:
        1. Структурированный формат с полями:
           **Тип:** SMM
           **Приоритет:** high
           **Дедлайн:** 2024-12-31
           **Этапы:**
           - Этап 1 (дата: 2024-12-01, цвет: green)
           
        2. Упрощённый формат (первый абзац = название, остальное = описание)
        
        Returns:
            dict с метаданными: {type, priority, due_date, description, stages, title}
        """
        metadata = {
            'type': 'smm',
            'priority': 'medium',
            'due_date': None,
            'description': '',
            'stages': [],
            'title': None
        }
        
        try:
            from googleapiclient.discovery import build
            credentials = google_service._get_credentials(background=False)
            docs_service = build('docs', 'v1', credentials=credentials)
            doc = docs_service.documents().get(documentId=doc_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            if not content:
                return metadata
            
            # Извлекаем весь текст документа для парсинга
            full_text = []
            paragraphs = []
            
            for element in content:
                if 'paragraph' in element:
                    para = element['paragraph']
                    para_text = ""
                    
                    if 'elements' in para:
                        for elem in para['elements']:
                            if 'textRun' in elem:
                                text = elem['textRun'].get('content', '')
                                para_text += text
                    
                    if para_text.strip():
                        paragraphs.append(para_text.strip())
                        full_text.append(para_text.strip())
            
            if not paragraphs:
                return metadata
            
            # Первый абзац - название задачи
            metadata['title'] = paragraphs[0]
            
            # Парсим структурированные поля
            import re
            text_content = '\n'.join(full_text)
            
            # Тип задачи
            type_match = re.search(r'\*\*Тип:\*\*\s*([A-Za-z-]+)', text_content, re.IGNORECASE)
            if type_match:
                task_type = type_match.group(1).strip().lower()
                if task_type in ['smm', 'design', 'channel', 'pr-fr', 'prfr']:
                    metadata['type'] = task_type.replace('pr-fr', 'prfr')
            
            # Приоритет
            priority_match = re.search(r'\*\*Приоритет:\*\*\s*([a-z]+)', text_content, re.IGNORECASE)
            if priority_match:
                priority = priority_match.group(1).strip().lower()
                if priority in ['low', 'medium', 'high', 'critical']:
                    metadata['priority'] = priority
            
            # Дедлайн
            due_match = re.search(r'\*\*Дедлайн:\*\*\s*(\d{4}-\d{2}-\d{2})', text_content)
            if due_match:
                metadata['due_date'] = due_match.group(1)
            
            # Этапы
            stages_match = re.search(r'\*\*Этапы?:\*\*\s*\n((?:-.*\n?)+)', text_content, re.MULTILINE)
            if stages_match:
                stages_text = stages_match.group(1)
                for stage_line in stages_text.split('\n'):
                    stage_line = stage_line.strip()
                    if not stage_line.startswith('-'):
                        continue
                    
                    # Формат: - Название этапа (дата: YYYY-MM-DD, цвет: green)
                    stage_name_match = re.search(r'-\s*(.+?)(?:\s*\(|$)', stage_line)
                    date_match = re.search(r'дата:\s*(\d{4}-\d{2}-\d{2})', stage_line, re.IGNORECASE)
                    color_match = re.search(r'цвет:\s*([a-z]+)', stage_line, re.IGNORECASE)
                    
                    if stage_name_match:
                        stage_data = {
                            'name': stage_name_match.group(1).strip(),
                            'due_date': date_match.group(1) if date_match else None,
                            'color': color_match.group(1) if color_match else 'green'
                        }
                        metadata['stages'].append(stage_data)
            
            # Описание - всё остальное, кроме заголовка и структурированных полей
            description_start = 1 if len(paragraphs) > 1 else 0
            description_parts = []
            
            # Убираем структурированные поля из описания
            for para in paragraphs[description_start:]:
                if not re.match(r'^\*\*(Тип|Приоритет|Дедлайн|Этапы?):\*\*', para):
                    description_parts.append(para)
            
            if description_parts:
                metadata['description'] = '\n\n'.join(description_parts)
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка парсинга метаданных из Google Doc {doc_id}: {e}")
            # Возвращаем хотя бы базовые данные (название из первого абзаца)
            if 'title' in metadata and metadata['title']:
                pass  # Уже установлено
            else:
                metadata['description'] = '\n'.join(full_text) if 'full_text' in locals() else ''
        
        return metadata
    
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
