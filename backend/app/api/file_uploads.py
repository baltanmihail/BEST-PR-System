"""
API для загрузки файлов с модерацией

Процесс:
1. Пользователь загружает файл → PENDING
2. VP4PR/Координатор одобряет или отклоняет
3. При одобрении файл становится доступен
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import logging

from app.database import get_db
from app.utils.permissions import get_current_user
from app.models.user import User, UserRole
from app.models.file_upload import FileUpload, FileUploadStatus, FileUploadCategory
from app.schemas.file_upload import (
    FileUploadResponse, 
    FileUploadListResponse,
    ModerationAction,
    FileUploadStats
)
from app.services.file_upload_service import FileUploadService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/file-uploads", tags=["file-uploads"])


# === Загрузка файлов ===

@router.post("", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    category: FileUploadCategory = Form(FileUploadCategory.OTHER),
    description: Optional[str] = Form(None),
    task_id: Optional[UUID] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузить файл на модерацию.
    
    Файл сохраняется во временную папку и ожидает одобрения VP4PR.
    """
    service = FileUploadService(db)
    
    try:
        upload = await service.upload_file(
            user=current_user,
            file=file,
            category=category,
            description=description,
            task_id=task_id
        )
        return upload
    except Exception as e:
        logger.error(f"Ошибка загрузки файла: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки: {str(e)}"
        )


# === Просмотр загрузок ===

@router.get("", response_model=FileUploadListResponse)
async def get_uploads(
    status_filter: Optional[FileUploadStatus] = None,
    category: Optional[FileUploadCategory] = None,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список загрузок.
    
    - Обычные пользователи видят только свои загрузки
    - VP4PR и координаторы видят все
    """
    query = select(FileUpload).options(
        selectinload(FileUpload.uploaded_by),
        selectinload(FileUpload.moderated_by)
    )
    
    # Фильтр по роли
    is_moderator = current_user.role in [UserRole.VP4PR, UserRole.COORDINATOR]
    if not is_moderator:
        query = query.where(FileUpload.uploaded_by_id == current_user.id)
    
    # Фильтры
    if status_filter:
        query = query.where(FileUpload.status == status_filter.value)
    if category:
        query = query.where(FileUpload.category == category.value)
    
    # Подсчёт
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    # Результаты
    query = query.order_by(FileUpload.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return FileUploadListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/pending", response_model=FileUploadListResponse)
async def get_pending_uploads(
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить файлы, ожидающие модерации.
    
    Только для VP4PR и координаторов.
    """
    if current_user.role not in [UserRole.VP4PR, UserRole.COORDINATOR]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только VP4PR и координаторы могут просматривать очередь модерации"
        )
    
    query = select(FileUpload).options(
        selectinload(FileUpload.uploaded_by)
    ).where(
        FileUpload.status == FileUploadStatus.PENDING.value
    ).order_by(FileUpload.created_at.asc())
    
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    items = result.scalars().all()
    
    return FileUploadListResponse(items=items, total=total, skip=skip, limit=limit)


@router.get("/stats", response_model=FileUploadStats)
async def get_upload_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Статистика загрузок для VP4PR"""
    if current_user.role not in [UserRole.VP4PR, UserRole.COORDINATOR]:
        raise HTTPException(status_code=403, detail="Доступ запрещён")
    
    pending = await db.scalar(
        select(func.count()).where(FileUpload.status == FileUploadStatus.PENDING.value)
    )
    approved = await db.scalar(
        select(func.count()).where(FileUpload.status == FileUploadStatus.APPROVED.value)
    )
    rejected = await db.scalar(
        select(func.count()).where(FileUpload.status == FileUploadStatus.REJECTED.value)
    )
    total_size = await db.scalar(
        select(func.sum(FileUpload.file_size)).where(
            FileUpload.status == FileUploadStatus.APPROVED.value
        )
    ) or 0
    
    return FileUploadStats(
        pending_count=pending or 0,
        approved_count=approved or 0,
        rejected_count=rejected or 0,
        total_approved_size_mb=round(total_size / 1024 / 1024, 2)
    )


# === Модерация ===

@router.post("/{upload_id}/approve")
async def approve_upload(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Одобрить загрузку файла.
    
    Файл перемещается в постоянную папку. Только VP4PR.
    """
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(status_code=403, detail="Только VP4PR может одобрять загрузки")
    
    service = FileUploadService(db)
    upload = await service.approve_upload(upload_id, current_user)
    
    return {"message": "Файл одобрен", "upload_id": str(upload.id)}


@router.post("/{upload_id}/reject")
async def reject_upload(
    upload_id: UUID,
    action: ModerationAction,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Отклонить загрузку файла.
    
    Файл удаляется. Только VP4PR.
    """
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(status_code=403, detail="Только VP4PR может отклонять загрузки")
    
    service = FileUploadService(db)
    await service.reject_upload(upload_id, current_user, action.reason)
    
    return {"message": "Файл отклонён", "upload_id": str(upload_id)}


@router.get("/{upload_id}", response_model=FileUploadResponse)
async def get_upload(
    upload_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию о загрузке"""
    query = select(FileUpload).options(
        selectinload(FileUpload.uploaded_by),
        selectinload(FileUpload.moderated_by)
    ).where(FileUpload.id == upload_id)
    
    result = await db.execute(query)
    upload = result.scalar_one_or_none()
    
    if not upload:
        raise HTTPException(status_code=404, detail="Загрузка не найдена")
    
    # Проверка доступа
    is_moderator = current_user.role in [UserRole.VP4PR, UserRole.COORDINATOR]
    if not is_moderator and upload.uploaded_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    
    return upload
