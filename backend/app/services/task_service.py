"""
Сервис для работы с задачами
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID
import logging

from app.models.task import Task, TaskType, TaskStatus, TaskPriority, TaskAssignment, TaskStage, StageStatus
from app.models.user import User
from app.schemas.task import TaskCreate, TaskUpdate
from datetime import timedelta, datetime, timezone

logger = logging.getLogger(__name__)


class TaskService:
    """Сервис для работы с задачами"""
    
    @staticmethod
    async def get_tasks(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None,
        created_by: Optional[UUID] = None,
        sort_by: Optional[str] = "relevance",  # "relevance", "priority", "due_date", "created_at", "manual"
        view_mode: str = "normal"  # "compact", "normal", "detailed"
    ) -> tuple[List[Task], int]:
        """
        Получить список задач с фильтрацией, сортировкой и пагинацией
        
        Сортировка:
        - "relevance": по важности (сначала ручной порядок, потом приоритет, потом горящие дедлайны)
        - "priority": по приоритету (critical > high > medium > low)
        - "due_date": по дедлайну (горящие дедлайны сверху, затем по дате)
        - "created_at": по дате создания (новые сверху)
        - "manual": только ручной порядок (sort_order)
        
        Returns:
            tuple: (список задач, общее количество)
        """
        from datetime import datetime, timezone
        
        # Базовый запрос
        query = select(Task)
        count_query = select(func.count(Task.id))
        
        # Применяем фильтры
        conditions = []
        
        if task_type:
            conditions.append(Task.type == task_type)
        if status:
            conditions.append(Task.status == status)
        if priority:
            conditions.append(Task.priority == priority)
        if created_by:
            conditions.append(Task.created_by == created_by)
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Получаем общее количество
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # Применяем сортировку
        if sort_by == "manual":
            # Только ручной порядок (sort_order не NULL), затем по дате создания
            query = query.order_by(
                Task.sort_order.asc().nulls_last(),
                Task.created_at.desc()
            )
        elif sort_by == "priority":
            # По приоритету: critical > high > medium > low
            from sqlalchemy import case
            priority_order = case(
                (Task.priority == TaskPriority.CRITICAL, 1),
                (Task.priority == TaskPriority.HIGH, 2),
                (Task.priority == TaskPriority.MEDIUM, 3),
                (Task.priority == TaskPriority.LOW, 4),
                else_=5
            )
            query = query.order_by(
                priority_order.asc(),
                Task.created_at.desc()
            )
        elif sort_by == "due_date":
            # По дедлайну: сначала задачи с дедлайном (горящие сверху), затем без дедлайна
            # Горящие дедлайны = дедлайн в течение 3 дней
            now = datetime.now(timezone.utc)
            hot_deadline = now + timedelta(days=3)
            
            from sqlalchemy import case
            due_date_order = case(
                (
                    and_(
                        Task.due_date.isnot(None),
                        Task.due_date <= hot_deadline,
                        Task.due_date >= now
                    ),
                    1  # Горящие дедлайны (в течение 3 дней)
                ),
                (
                    and_(
                        Task.due_date.isnot(None),
                        Task.due_date > hot_deadline
                    ),
                    2  # Обычные дедлайны (больше 3 дней)
                ),
                (
                    Task.due_date.isnot(None),
                    3  # Просроченные дедлайны
                ),
                else_=4  # Нет дедлайна
            )
            query = query.order_by(
                due_date_order.asc(),
                Task.due_date.asc().nulls_last(),
                Task.created_at.desc()
            )
        elif sort_by == "created_at":
            # По дате создания (новые сверху)
            query = query.order_by(Task.created_at.desc())
        else:  # "relevance" - по умолчанию
            # Сортировка по важности:
            # 1. Ручной порядок (sort_order не NULL) - меньше число = выше
            # 2. Приоритет (critical > high > medium > low)
            # 3. Горящие дедлайны (в течение 3 дней)
            # 4. Дата создания (новые сверху)
            from sqlalchemy import case
            now = datetime.now(timezone.utc)
            hot_deadline = now + timedelta(days=3)
            
            priority_order = case(
                (Task.priority == TaskPriority.CRITICAL, 1),
                (Task.priority == TaskPriority.HIGH, 2),
                (Task.priority == TaskPriority.MEDIUM, 3),
                (Task.priority == TaskPriority.LOW, 4),
                else_=5
            )
            
            # Горящий дедлайн = приоритет выше
            hot_deadline_boost = case(
                (
                    and_(
                        Task.due_date.isnot(None),
                        Task.due_date <= hot_deadline,
                        Task.due_date >= now
                    ),
                    0  # Горящие дедлайны получают +0 (выше в сортировке)
                ),
                else_=1  # Остальные получают +1
            )
            
            query = query.order_by(
                Task.sort_order.asc().nulls_last(),  # Ручной порядок (меньше = выше)
                priority_order.asc(),  # Приоритет
                hot_deadline_boost.asc(),  # Горящие дедлайны
                Task.due_date.asc().nulls_last(),  # Дедлайн (ближайшие сверху)
                Task.created_at.desc()  # Новые задачи сверху
            )
        
        # Применяем пагинацию
        query = query.offset(skip).limit(limit)
        
        # Загружаем связанные данные (опционально, в зависимости от view_mode)
        if view_mode in ["normal", "detailed"]:
            query = query.options(
                selectinload(Task.stages),
                selectinload(Task.assignments).selectinload(TaskAssignment.user)
            )
        elif view_mode == "compact":
            # В упрощённом виде не загружаем связанные данные для производительности
            pass
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        return list(tasks), total
    
    @staticmethod
    async def get_task_by_id(
        db: AsyncSession,
        task_id: UUID
    ) -> Optional[Task]:
        """Получить задачу по ID с загруженными связанными данными"""
        from app.models.file import File
        
        query = select(Task).where(Task.id == task_id)
        query = query.options(
            selectinload(Task.stages),
            selectinload(Task.assignments).selectinload(TaskAssignment.user)
        )
        
        result = await db.execute(query)
        task = result.scalar_one_or_none()
        
        if task:
            # Загружаем файлы, связанные с задачей (материалы задачи)
            files_query = select(File).where(File.task_id == task_id).order_by(File.created_at.desc())
            files_result = await db.execute(files_query)
            # Устанавливаем файлы как атрибут задачи (для использования в API)
            task.files = list(files_result.scalars().all())
        
        return task
    
    @staticmethod
    async def create_task(
        db: AsyncSession,
        task_data: TaskCreate,
        created_by: UUID
    ) -> Task:
        """
        Создать новую задачу
        
        Автоматически создаёт структуру папок в Google Drive для задачи:
        - Tasks/{task_id}_{task_name}/
          - materials/
          - final/
          - drafts/
        """
        # Извлекаем equipment_available из данных
        task_dict = task_data.model_dump()
        equipment_available = task_dict.pop('equipment_available', False)
        
        task = Task(
            **task_dict,
            created_by=created_by,
            status=TaskStatus.DRAFT,  # Новые задачи создаются как черновики
            equipment_available=equipment_available
        )
        
        db.add(task)
        await db.commit()
        await db.refresh(task)
        
        # Создаём структуру папок в Google Drive (асинхронно, в фоне)
        # Не ждём завершения - это не критично для создания задачи
        try:
            from app.services.drive_structure import DriveStructureService
            import asyncio
            
            # Создаём папки и файл задачи в фоне через executor (синхронная операция)
            async def create_drive_folders_async():
                try:
                    def create_folders_sync():
                        drive_structure = DriveStructureService()
                        # Подготавливаем данные задачи для файла
                        task_data_dict = {
                            'id': str(task.id),
                            'title': task.title,
                            'description': task.description,
                            'type': task.type.value if hasattr(task.type, 'value') else str(task.type),
                            'priority': task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
                            'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                            'due_date': task.due_date.isoformat() if task.due_date else None,
                        }
                        return drive_structure.create_task_folder(
                            task_id=str(task.id),
                            task_name=task.title,
                            task_description=task.description,
                            task_data=task_data_dict
                        )
                    
                    # Выполняем синхронную операцию в executor
                    loop = asyncio.get_event_loop()
                    folders = await loop.run_in_executor(None, create_folders_sync)
                    
                    logger.info(f"✅ Создана структура папок и файл задачи Google Drive для задачи {task.id}: {folders}")
                    
                    # Сохраняем drive_folder_id и drive_file_id в задачу
                    if folders:
                        if folders.get('task_folder_id'):
                            task.drive_folder_id = folders['task_folder_id']
                        # TODO: добавить поле drive_file_id в модель Task, если нужно
                        await db.commit()
                        await db.refresh(task)
                        logger.info(f"✅ Сохранён drive_folder_id для задачи {task.id}: {folders.get('task_folder_id')}")
                    
                    return folders
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось создать папки/файл Google Drive для задачи {task.id}: {e}")
                    logger.exception("Полная трассировка ошибки:")
                    return None
            
            # Запускаем в фоне (не блокируем ответ)
            asyncio.create_task(create_drive_folders_async())
            
        except Exception as e:
            # Логируем, но не прерываем создание задачи
            logger.warning(f"⚠️ Ошибка создания папок Google Drive для задачи {task.id}: {e}")
            logger.warning("Задача создана, но папки Drive не созданы. Их можно создать позже.")
        
        return task
    
    @staticmethod
    async def update_task(
        db: AsyncSession,
        task_id: UUID,
        task_data: TaskUpdate,
        current_user: User
    ) -> Optional[Task]:
        """Обновить задачу"""
        task = await TaskService.get_task_by_id(db, task_id)
        
        if not task:
            return None
        
        # Проверка прав (только создатель или координатор)
        from app.models.user import UserRole
        if task.created_by != current_user.id and current_user.role not in [
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN, 
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
        ]:
            return None
        
        # Обновляем поля
        update_data = task_data.model_dump(exclude_unset=True)
        
        # Проверка прав на изменение sort_order (только VP4PR)
        if "sort_order" in update_data and current_user.role != UserRole.VP4PR:
            # Удаляем sort_order из данных, если пользователь не VP4PR
            update_data.pop("sort_order", None)
        
        for field, value in update_data.items():
            setattr(task, field, value)
        
        await db.commit()
        await db.refresh(task)
        
        # Обновляем Google Doc файл задачи, если он существует
        try:
            await TaskService._update_task_doc_in_drive(task, db)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось обновить Google Doc для задачи {task_id}: {e}")
            # Не прерываем выполнение, если обновление Doc не удалось
        
        return task
    
    @staticmethod
    async def _update_task_doc_in_drive(task: Task, db: AsyncSession):
        """
        Обновить Google Doc файл задачи в Drive при изменении задачи
        
        Находит Google Doc файл в папке задачи и обновляет его содержимое
        """
        if not task.drive_folder_id:
            return  # Нет папки в Drive
        
        try:
            from app.services.google_service import GoogleService
            from app.services.drive_structure import DriveStructureService
            from googleapiclient.discovery import build
            
            google_service = GoogleService()
            drive_service = google_service._get_drive_service(background=False)
            
            # Ищем Google Doc файл в папке задачи
            query = f"'{task.drive_folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            results = drive_service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=1
            ).execute()
            
            doc_files = results.get('files', [])
            if not doc_files:
                logger.debug(f"Google Doc файл для задачи {task.id} не найден в папке")
                return
            
            doc_id = doc_files[0]['id']
            
            # Получаем credentials для Docs API
            credentials = google_service._get_credentials(background=False)
            docs_service = build('docs', 'v1', credentials=credentials)
            
            # Формируем обновлённое содержимое документа
            # Структура: название, метаданные, описание
            requests = []
            
            # Получаем текущее содержимое документа для определения размера
            doc = docs_service.documents().get(documentId=doc_id).execute()
            
            # Получаем индекс конца документа из body
            body = doc.get('body', {})
            end_index = body.get('endIndex', 1)
            
            # Формируем текст для обновления
            doc_lines = [
                task.title,
                "",
                f"**Тип:** {task.type.value.upper()}",
                f"**Приоритет:** {task.priority.value}",
            ]
            
            if task.due_date:
                due_date_str = task.due_date.strftime('%Y-%m-%d')
                doc_lines.append(f"**Дедлайн:** {due_date_str}")
            
            # Добавляем этапы, если есть
            from app.models.task import TaskStage
            
            stages_query = select(TaskStage).where(TaskStage.task_id == task.id).order_by(TaskStage.stage_order)
            stages_result = await db.execute(stages_query)
            stages = stages_result.scalars().all()
            
            if stages:
                doc_lines.append("**Этапы:**")
                for stage in stages:
                    stage_line = f"- {stage.stage_name}"
                    if stage.due_date:
                        stage_date = stage.due_date.strftime('%Y-%m-%d')
                        stage_line += f" (дата: {stage_date}"
                        if stage.status_color:
                            stage_line += f", цвет: {stage.status_color}"
                        stage_line += ")"
                    doc_lines.append(stage_line)
            
            if task.description:
                doc_lines.append("")
                doc_lines.append(task.description)
            
            # Формируем запросы для обновления документа
            # В Google Docs API индексы начинаются с 1
            # Документ имеет структуру: [начало (1), контент, конец (endIndex)]
            # Удаляем всё содержимое между индексом 1 и endIndex - 1
            if end_index > 1:
                requests.append({
                    'deleteContentRange': {
                        'range': {
                            'startIndex': 1,
                            'endIndex': end_index - 1
                        }
                    }
                })
            
            # Вставляем новое содержимое в начало (после удаления старого содержимого)
            new_text = '\n'.join(doc_lines)
            if new_text:
                requests.append({
                    'insertText': {
                        'location': {
                            'index': 1
                        },
                        'text': new_text
                    }
                })
            
            # Применяем обновления
            if requests:
                docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={'requests': requests}
                ).execute()
                
                logger.info(f"✅ Обновлён Google Doc для задачи {task.id}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка обновления Google Doc для задачи {task.id}: {e}")
            raise
    
    @staticmethod
    async def publish_task(
        db: AsyncSession,
        task_id: UUID,
        current_user: User
    ) -> Optional[Task]:
        """Опубликовать задачу (изменить статус с DRAFT на OPEN)"""
        task = await TaskService.get_task_by_id(db, task_id)
        
        if not task:
            return None
        
        # Проверка прав (только создатель или координатор)
        from app.models.user import UserRole
        if task.created_by != current_user.id and current_user.role not in [
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
        ]:
            return None
        
        # Проверяем, что задача в статусе DRAFT
        if task.status != TaskStatus.DRAFT:
            return None
        
        # Публикуем задачу
        task.status = TaskStatus.OPEN
        
        await db.commit()
        await db.refresh(task)
        
        return task
    
    @staticmethod
    async def delete_task(
        db: AsyncSession,
        task_id: UUID,
        current_user: User
    ) -> bool:
        """Удалить задачу"""
        task = await TaskService.get_task_by_id(db, task_id)
        
        if not task:
            return False
        
        # Проверка прав (только создатель или VP4PR)
        from app.models.user import UserRole
        if task.created_by != current_user.id and current_user.role != UserRole.VP4PR:
            return False
        
        # Удаляем задачу
        # В SQLAlchemy 2.0 async используем delete() напрямую
        from sqlalchemy import delete
        await db.execute(delete(Task).where(Task.id == task_id))
        await db.commit()
        
        return True
