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
from app.services.google_service import GoogleService
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
        task_id: Optional[UUID] = None
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
        
        # Проверяем, является ли пользователь координатором/VP4PR
        is_coordinator = user.role in [
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
        ]
        
        # Для координаторов - загружаем сразу в постоянную папку
        # Для обычных пользователей - во временную папку
        if is_coordinator:
            # Загружаем сразу в постоянную папку для категории
            final_folder_id = await self._get_category_folder(category)
            folder_id = final_folder_id
            filename = file.filename
            initial_status = FileUploadStatus.APPROVED
        else:
            # Загружаем во временную папку
            folder_id = await self._get_or_create_temp_folder()
            filename = f"pending_{user.id}_{file.filename}"
            initial_status = FileUploadStatus.PENDING
        
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
            temp_drive_id=drive_file_id if not is_coordinator else None,
            final_drive_id=drive_file_id if is_coordinator else None,
            drive_url=drive_url,
            category=category,
            task_id=task_id,
            description=description,
            status=initial_status,
            moderated_by_id=user.id if is_coordinator else None,
            moderated_at=datetime.now(timezone.utc) if is_coordinator else None
        )
        
        self.db.add(upload)
        await self.db.commit()
        await self.db.refresh(upload)
        
        if is_coordinator:
            logger.info(f"✅ Файл '{file.filename}' загружен и автоматически одобрен для координатора (ID: {upload.id})")
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
        final_folder_id = await self._get_category_folder(upload.category)
        
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
                
                # Переименовываем (убираем pending_ префикс)
                drive_service.files().update(
                    fileId=upload.temp_drive_id,
                    body={'name': upload.original_filename},
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
