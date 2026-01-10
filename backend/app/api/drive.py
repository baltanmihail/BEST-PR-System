"""
API endpoints для работы с Google Drive
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from pydantic import BaseModel
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.database import get_db
from app.utils.permissions import get_current_user
from app.models.user import User, UserRole
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/drive", tags=["drive"])

# Executor для выполнения синхронных операций Google API в async контексте
_executor = ThreadPoolExecutor(max_workers=5)


# Pydantic схемы для запросов/ответов
class FolderCreateRequest(BaseModel):
    name: str
    parent_folder_id: Optional[str] = None


class FileUploadResponse(BaseModel):
    file_id: str
    file_name: str
    file_url: str
    folder_id: Optional[str] = None


class FolderResponse(BaseModel):
    folder_id: str
    folder_name: str
    folder_url: str
    parent_folder_id: Optional[str] = None


class FileListResponse(BaseModel):
    files: List[dict]
    folder_id: str


class FileMetadataResponse(BaseModel):
    file_id: str
    name: str
    mime_type: str
    size: Optional[str] = None
    modified_time: str
    created_time: str
    url: str
    shareable_link: Optional[str] = None


# Singleton instances
_google_service: Optional[GoogleService] = None
_drive_structure: Optional[DriveStructureService] = None


def get_google_service() -> GoogleService:
    """Получить экземпляр GoogleService (singleton)"""
    global _google_service
    if _google_service is None:
        try:
            _google_service = GoogleService()
        except ValueError as e:
            logger.warning(f"GoogleService не инициализирован: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google Drive service is not available. Please configure Google credentials."
            )
    return _google_service


def get_drive_structure() -> DriveStructureService:
    """Получить экземпляр DriveStructureService (singleton)"""
    global _drive_structure
    if _drive_structure is None:
        _drive_structure = DriveStructureService()
    return _drive_structure


# Вспомогательные функции для проверки прав доступа
def check_drive_access(user: User) -> bool:
    """
    Проверка прав доступа к Google Drive
    
    Доступ имеют только:
    - VP4PR (глава PR-отдела)
    - Координаторы (SMM, Design, Channel, PR-FR)
    """
    if user.role == UserRole.VP4PR:
        return True
    
    if user.role in [UserRole.SMM_COORDINATOR, UserRole.DESIGN_COORDINATOR, 
                     UserRole.CHANNEL_COORDINATOR, UserRole.PR_FR_COORDINATOR]:
        return True
    
    return False


# ========== Endpoints для работы с папками ==========

@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    request: FolderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать папку в Google Drive
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can create folders."
        )
    
    try:
        google_service = get_google_service()
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        folder_id = await loop.run_in_executor(
            _executor,
            lambda: google_service.create_folder(
                name=request.name,
                parent_folder_id=request.parent_folder_id,
                background=False  # Пользовательский запрос - используем пользовательский клиент
            )
        )
        
        folder_url = google_service.get_file_url(folder_id)
        
        return FolderResponse(
            folder_id=folder_id,
            folder_name=request.name,
            folder_url=folder_url,
            parent_folder_id=request.parent_folder_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка создания папки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create folder: {str(e)}"
        )


@router.get("/folders/{folder_id}/files", response_model=FileListResponse)
async def list_files_in_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список файлов в папке
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can list files."
        )
    
    try:
        google_service = get_google_service()
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        files = await loop.run_in_executor(
            _executor,
            lambda: google_service.list_files(
                folder_id=folder_id,
                background=False
            )
        )
        
        return FileListResponse(
            files=files,
            folder_id=folder_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка получения списка файлов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


# ========== Endpoints для работы с файлами ==========

@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    folder_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузить файл в Google Drive
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can upload files."
        )
    
    try:
        google_service = get_google_service()
        
        # Читаем содержимое файла
        file_content = await file.read()
        
        # Определяем MIME тип
        mime_type = file.content_type or "application/octet-stream"
        
        # Выполняем синхронную операцию загрузки в executor
        loop = asyncio.get_event_loop()
        file_id = await loop.run_in_executor(
            _executor,
            lambda: google_service.upload_file(
                file_content=file_content,
                filename=file.filename,
                mime_type=mime_type,
                folder_id=folder_id,
                background=False
            )
        )
        
        file_url = google_service.get_file_url(file_id)
        
        return FileUploadResponse(
            file_id=file_id,
            file_name=file.filename,
            file_url=file_url,
            folder_id=folder_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get("/files/{file_id}", response_model=FileMetadataResponse)
async def get_file_metadata(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить метаданные файла
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can access file metadata."
        )
    
    try:
        google_service = get_google_service()
        
        # Выполняем синхронные операции в executor
        loop = asyncio.get_event_loop()
        metadata = await loop.run_in_executor(
            _executor,
            lambda: google_service.get_file_metadata(file_id, background=False)
        )
        
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Получаем публичную ссылку
        shareable_link = await loop.run_in_executor(
            _executor,
            lambda: google_service.get_shareable_link(file_id, background=False)
        )
        
        return FileMetadataResponse(
            file_id=metadata.get('id'),
            name=metadata.get('name'),
            mime_type=metadata.get('mimeType'),
            size=metadata.get('size'),
            modified_time=metadata.get('modifiedTime'),
            created_time=metadata.get('createdTime'),
            url=metadata.get('webViewLink') or google_service.get_file_url(file_id),
            shareable_link=shareable_link
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения метаданных файла: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file metadata: {str(e)}"
        )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить файл из Google Drive
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can delete files."
        )
    
    try:
        google_service = get_google_service()
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            _executor,
            lambda: google_service.delete_file(file_id, background=False)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete file"
            )
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления файла: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


# ========== Endpoints для структуры папок ==========

@router.post("/structure/initialize", status_code=status.HTTP_201_CREATED)
async def initialize_drive_structure(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Инициализировать структуру папок в Google Drive
    
    Доступ: только VP4PR
    """
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR can initialize drive structure."
        )
    
    try:
        drive_structure = get_drive_structure()
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        structure = await loop.run_in_executor(
            _executor,
            lambda: drive_structure.initialize_structure()
        )
        
        if not structure:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize drive structure. Check Google credentials."
            )
        
        return {
            "success": True,
            "message": "Drive structure initialized successfully",
            "structure": structure
        }
        
    except Exception as e:
        logger.error(f"Ошибка инициализации структуры папок: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize drive structure: {str(e)}"
        )


@router.post("/tasks/{task_id}/folders", status_code=status.HTTP_201_CREATED)
async def create_task_folders(
    task_id: str,
    task_name: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать структуру папок для задачи
    
    Структура:
    - Tasks/{task_id}_{task_name}/
      - materials/
      - final/
      - drafts/
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can create task folders."
        )
    
    try:
        drive_structure = get_drive_structure()
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        folders = await loop.run_in_executor(
            _executor,
            lambda: drive_structure.create_task_folder(task_id, task_name)
        )
        
        return {
            "success": True,
            "message": "Task folders created successfully",
            "folders": folders
        }
        
    except Exception as e:
        logger.error(f"Ошибка создания папок для задачи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task folders: {str(e)}"
        )


@router.get("/structure/folders", status_code=status.HTTP_200_OK)
async def get_structure_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить ID основных папок структуры
    
    Доступ: VP4PR, координаторы
    """
    if not check_drive_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only VP4PR and coordinators can access structure folders."
        )
    
    try:
        drive_structure = get_drive_structure()
        
        # Выполняем синхронные операции в executor
        loop = asyncio.get_event_loop()
        structure = await loop.run_in_executor(
            _executor,
            lambda: {
                "bot_folder_id": drive_structure.get_bot_folder_id(),
                "tasks_folder_id": drive_structure.get_tasks_folder_id(),
                "gallery_folder_id": drive_structure.get_gallery_folder_id(),
                "equipment_folder_id": drive_structure.get_equipment_folder_id(),
                "support_folder_id": drive_structure.get_support_folder_id(),
                "users_folder_id": drive_structure.get_users_folder_id(),
            }
        )
        
        return structure
        
    except Exception as e:
        logger.error(f"Ошибка получения структуры папок: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get structure folders: {str(e)}"
        )


@router.post("/sync", response_model=dict)
async def sync_drive_changes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Синхронизировать изменения из Google Drive в систему
    
    Отслеживает:
    - Изменения файлов задач
    - Новые файлы в папке Tasks
    - Обновления файлов задач (Google Doc)
    
    Доступно только координаторам и VP4PR
    """
    from app.models.user import UserRole
    from app.services.drive_sync_service import drive_sync_service
    
    # Проверка прав доступа
    if current_user.role not in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only coordinators and VP4PR can sync Drive changes"
        )
    
    try:
        stats = await drive_sync_service.sync_drive_changes(db)
        logger.info(f"✅ Синхронизация Drive завершена: {stats}")
        return {
            "success": True,
            "stats": stats,
            "message": f"Обновлено: {stats.get('updated', 0)}, создано: {stats.get('created', 0)}, ошибок: {stats.get('errors', 0)}"
        }
    except Exception as e:
        logger.error(f"❌ Ошибка синхронизации Drive: {e}")
        logger.exception("Полная трассировка ошибки:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync Drive changes: {str(e)}"
        )
