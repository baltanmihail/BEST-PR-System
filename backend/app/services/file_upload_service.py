"""
Сервис для загрузки файлов с модерацией

Файлы загружаются во временную папку, затем модерируются VP4PR.
"""
import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.file_upload import FileUpload, FileUploadStatus, FileUploadCategory
from app.models.task import Task
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService
from app.config import settings

logger = logging.getLogger(__name__)

# Лимиты
MAX_FILE_SIZE_MB = 100  # Максимальный размер файла
ALLOWED_MIME_TYPES = [
    # Изображения
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    # Видео
    'video/mp4', 'video/quicktime', 'video/x-msvideo', 'video/webm',
    # Документы
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    # Архивы
    'application/zip', 'application/x-rar-compressed',
]


class FileUploadService:
    """Сервис загрузки файлов с модерацией"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self._google_service: Optional[GoogleService] = None
    
    @property
    def google_service(self) -> GoogleService:
        if not self._google_service:
            self._google_service = GoogleService()
        return self._google_service
    
    async def upload_file(
        self,
        user: User,
        file: UploadFile,
        category: FileUploadCategory,
        description: Optional[str] = None,
        task_id: Optional[UUID] = None,
        stage_id: Optional[UUID] = None
    ) -> FileUpload:
        """
        Загрузить файл во временную папку на модерацию
        """
        # Проверка MIME типа
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Недопустимый тип файла: {file.content_type}"
            )
        
        # Читаем содержимое
        content = await file.read()
        file_size = len(content)
        
        # Проверка размера
        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail=f"Файл слишком большой. Максимум: {MAX_FILE_SIZE_MB} МБ"
            )
        
        # Проверяем, является ли пользователь VP4PR (автоодобрение) или координатором (модерация)
        is_vp4pr = user.role == UserRole.VP4PR
        is_coordinator = user.role in [
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR
        ]
        
        # Для файлов задач (task_material) сохраняем в папку задачи (materials)
        # Для остальных категорий - в общие папки
        if category == FileUploadCategory.TASK_MATERIAL and task_id:
            # Получаем папку задачи и подпапку materials
            folder_id = await self._get_task_materials_folder(task_id)
            # Переименовываем файл с префиксом task_id
            file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
            file_base_name = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
            filename = f"{task_id}_{file_base_name}.{file_extension}" if file_extension else f"{task_id}_{file_base_name}"
            # Для VP4PR - одобряем сразу, для координаторов и остальных - на модерацию
            initial_status = FileUploadStatus.APPROVED if is_vp4pr else FileUploadStatus.PENDING
            is_approved_immediately = is_vp4pr
        elif is_vp4pr:
            # Для VP4PR - загружаем сразу в постоянную папку для категории (автоодобрение)
            final_folder_id = await self._get_category_folder(category)
            folder_id = final_folder_id
            filename = file.filename
            initial_status = FileUploadStatus.APPROVED
            is_approved_immediately = True
        else:
            # Для координаторов и обычных пользователей - загружаем во временную папку (на модерацию)
            folder_id = await self._get_or_create_temp_folder()
            filename = f"pending_{user.id}_{file.filename}"
            initial_status = FileUploadStatus.PENDING
            is_approved_immediately = False
        
        # Загружаем на Google Drive
        try:
            drive_file_id = self.google_service.upload_file(
                file_content=content,
                filename=filename,
                mime_type=file.content_type,
                folder_id=folder_id
            )
            
            drive_url = f"https://drive.google.com/file/d/{drive_file_id}/view"
            
        except Exception as e:
            logger.error(f"Ошибка загрузки на Google Drive: {e}")
            raise HTTPException(
                status_code=500,
                detail="Ошибка загрузки файла в облако"
            )
        
        # Создаём запись в БД
        upload = FileUpload(
            uploaded_by_id=user.id,
            original_filename=file.filename,
            mime_type=file.content_type,
            file_size=file_size,
            temp_drive_id=drive_file_id if not is_approved_immediately else None,
            final_drive_id=drive_file_id if is_approved_immediately else None,
            drive_url=drive_url,
            category=category,
            task_id=task_id,
            stage_id=stage_id,
            description=description,
            status=initial_status,
            moderated_by_id=user.id if is_approved_immediately else None,
            moderated_at=datetime.now(timezone.utc) if is_approved_immediately else None
        )
        
        self.db.add(upload)
        
        # Если передан stage_id, обновляем статус этапа на REVIEW
        if stage_id:
            from app.models.task import TaskStage, StageStatus
            stage_result = await self.db.execute(select(TaskStage).where(TaskStage.id == stage_id))
            stage = stage_result.scalar_one_or_none()
            if stage and stage.status != StageStatus.COMPLETED:
                stage.status = StageStatus.REVIEW
                # Обновляем цвет статуса на фиолетовый (для review)
                stage.status_color = "purple"
        
        await self.db.commit()
        await self.db.refresh(upload)
        
        if is_approved_immediately:
            logger.info(f"✅ Файл '{file.filename}' загружен и автоматически одобрен для VP4PR (ID: {upload.id})")
        else:
            logger.info(f"✅ Файл '{file.filename}' загружен на модерацию (ID: {upload.id})")
        
        return upload
    
    async def approve_upload(self, upload_id: UUID, moderator: User) -> FileUpload:
        """
        Одобрить загрузку и переместить файл в постоянную папку
        """
        upload = await self._get_upload(upload_id)
        
        if upload.status != FileUploadStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail="Файл уже обработан"
            )
        
        # Получаем постоянную папку для категории
        # Для файлов задач - в папку задачи (materials), для остальных - в категорию
        if upload.category == FileUploadCategory.TASK_MATERIAL and upload.task_id:
            final_folder_id = await self._get_task_materials_folder(upload.task_id)
            # Переименовываем файл с префиксом task_id
            file_extension = upload.original_filename.split('.')[-1] if '.' in upload.original_filename else ''
            file_base_name = upload.original_filename.rsplit('.', 1)[0] if '.' in upload.original_filename else upload.original_filename
            new_filename = f"{upload.task_id}_{file_base_name}.{file_extension}" if file_extension else f"{upload.task_id}_{file_base_name}"
        else:
            final_folder_id = await self._get_category_folder(upload.category)
            new_filename = upload.original_filename
        
        # Перемещаем файл
        try:
            if upload.temp_drive_id:
                # Копируем в новую папку с новым именем
                oauth_drive = self.google_service._get_oauth_drive_service()
                drive_service = oauth_drive or self.google_service._get_drive_service()
                
                # Получаем текущую папку файла
                file_info = drive_service.files().get(
                    fileId=upload.temp_drive_id,
                    fields='parents',
                    supportsAllDrives=True
                ).execute()
                
                # Перемещаем: убираем из temp, добавляем в final
                drive_service.files().update(
                    fileId=upload.temp_drive_id,
                    addParents=final_folder_id,
                    removeParents=','.join(file_info.get('parents', [])),
                    fields='id, parents',
                    supportsAllDrives=True
                ).execute()
                
                # Переименовываем (убираем pending_ префикс, добавляем task_id для задач)
                drive_service.files().update(
                    fileId=upload.temp_drive_id,
                    body={'name': new_filename},
                    supportsAllDrives=True
                ).execute()
                
                upload.final_drive_id = upload.temp_drive_id
                
        except Exception as e:
            logger.error(f"Ошибка перемещения файла: {e}")
            # Файл останется в temp, но мы всё равно одобрим
        
        # Обновляем статус
        upload.status = FileUploadStatus.APPROVED
        upload.moderated_by_id = moderator.id
        upload.moderated_at = datetime.now(timezone.utc)
        
        await self.db.commit()
        await self.db.refresh(upload)
        
        logger.info(f"✅ Файл '{upload.original_filename}' одобрен модератором {moderator.full_name}")
        
        return upload
    
    async def reject_upload(
        self, 
        upload_id: UUID, 
        moderator: User, 
        reason: Optional[str] = None
    ) -> FileUpload:
        """
        Отклонить загрузку и удалить файл
        """
        upload = await self._get_upload(upload_id)
        
        if upload.status != FileUploadStatus.PENDING:
            raise HTTPException(
                status_code=400,
                detail="Файл уже обработан"
            )
        
        # Удаляем файл с Google Drive
        try:
            if upload.temp_drive_id:
                self.google_service.delete_file(upload.temp_drive_id)
        except Exception as e:
            logger.warning(f"Не удалось удалить файл с Drive: {e}")
        
        # Обновляем статус
        upload.status = FileUploadStatus.REJECTED
        upload.moderated_by_id = moderator.id
        upload.moderated_at = datetime.now(timezone.utc)
        upload.rejection_reason = reason
        upload.temp_drive_id = None  # Файл удалён
        upload.drive_url = None
        
        await self.db.commit()
        await self.db.refresh(upload)
        
        logger.info(f"❌ Файл '{upload.original_filename}' отклонён: {reason}")
        
        return upload
    
    async def _get_upload(self, upload_id: UUID) -> FileUpload:
        """Получить загрузку по ID"""
        result = await self.db.execute(
            select(FileUpload).where(FileUpload.id == upload_id)
        )
        upload = result.scalar_one_or_none()
        
        if not upload:
            raise HTTPException(status_code=404, detail="Загрузка не найдена")
        
        return upload
    
    async def _get_or_create_temp_folder(self) -> str:
        """Получить или создать папку для временных файлов"""
        root_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        
        folder_id = self.google_service.get_folder_by_name(
            name="_pending_uploads",
            parent_folder_id=root_folder_id
        )
        
        if not folder_id:
            folder_id = self.google_service.create_folder(
                name="_pending_uploads",
                parent_folder_id=root_folder_id
            )
            logger.info(f"📁 Создана папка для временных файлов: {folder_id}")
        
        return folder_id
    
    async def _get_category_folder(self, category: FileUploadCategory) -> str:
        """Получить папку для категории файлов"""
        root_folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
        
        folder_names = {
            FileUploadCategory.TASK_MATERIAL: "Task Materials",
            FileUploadCategory.GALLERY: "Gallery",
            FileUploadCategory.TEMPLATE: "Templates",
            FileUploadCategory.EQUIPMENT_PHOTO: "Equipment Photos",
            FileUploadCategory.OTHER: "Other Files",
        }
        
        folder_name = folder_names.get(category, "Other Files")
        
        folder_id = self.google_service.get_folder_by_name(
            name=folder_name,
            parent_folder_id=root_folder_id
        )
        
        if not folder_id:
            folder_id = self.google_service.create_folder(
                name=folder_name,
                parent_folder_id=root_folder_id
            )
            logger.info(f"📁 Создана папка для категории {category.value}: {folder_id}")
        
        return folder_id
    
    async def _get_task_materials_folder(self, task_id: UUID) -> str:
        """
        Получить папку materials для задачи
        
        Если папка задачи не существует, создаёт её структуру.
        """
        # Получаем задачу из БД
        from sqlalchemy import select
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        
        if not task:
            raise HTTPException(status_code=404, detail="Задача не найдена")
        
        # Если папка задачи уже существует, получаем materials
        if task.drive_folder_id:
            # Ищем подпапку materials в папке задачи
            materials_folder_id = self.google_service.get_folder_by_name(
                name="materials",
                parent_folder_id=task.drive_folder_id
            )
            if materials_folder_id:
                return materials_folder_id
            else:
                # Создаём подпапку materials
                materials_folder_id = self.google_service.create_folder(
                    name="materials",
                    parent_folder_id=task.drive_folder_id
                )
                logger.info(f"📁 Создана подпапка materials для задачи {task_id}: {materials_folder_id}")
                return materials_folder_id
        
        # Если папка задачи не существует, создаём структуру
        # create_task_folder синхронная, поэтому запускаем в executor
        import asyncio
        drive_structure = DriveStructureService()
        task_data_dict = {
            'id': str(task.id),
            'title': task.title,
            'description': task.description,
            'type': task.type.value if hasattr(task.type, 'value') else str(task.type),
            'priority': task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
            'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
            'due_date': task.due_date.isoformat() if task.due_date else None,
        }
        
        loop = asyncio.get_event_loop()
        folders = await loop.run_in_executor(
            None,
            lambda: drive_structure.create_task_folder(
                task_id=str(task.id),
                task_name=task.title,
                task_description=task.description,
                task_data=task_data_dict
            )
        )
        
        # Сохраняем drive_folder_id в задачу
        if folders.get('task_folder_id'):
            task.drive_folder_id = folders['task_folder_id']
            await self.db.commit()
            await self.db.refresh(task)
        
        materials_folder_id = folders.get('materials_folder_id')
        if not materials_folder_id:
            # Если materials не была создана, создаём её
            materials_folder_id = self.google_service.create_folder(
                name="materials",
                parent_folder_id=folders['task_folder_id']
            )
        
        return materials_folder_id
