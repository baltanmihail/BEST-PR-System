"""
API endpoints для галереи проектов
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
import json

from app.database import get_db
from app.models.user import User
from app.models.gallery import GalleryCategory
from app.schemas.gallery import (
    GalleryItemResponse, GalleryItemCreate, GalleryItemUpdate, GalleryItemListResponse,
    GalleryFileInfo, GalleryTaskInfo, GalleryTaskAssignee
)
from app.services.gallery_service import GalleryService
from app.utils.permissions import get_current_user, require_coordinator
from pydantic import BaseModel, Field

router = APIRouter(prefix="/gallery", tags=["gallery"])


async def _build_task_info(db, task) -> Optional[GalleryTaskInfo]:
    """Построить GalleryTaskInfo с ответственными из связанной задачи."""
    if not task:
        return None
    from sqlalchemy.orm import selectinload
    from app.models.task import Task, TaskAssignment
    from sqlalchemy import select

    q = (
        select(Task)
        .where(Task.id == task.id)
        .options(selectinload(Task.assignments).selectinload(TaskAssignment.user))
    )
    result = await db.execute(q)
    full_task = result.scalar_one_or_none()
    if not full_task:
        return GalleryTaskInfo.model_validate(task)

    assignees = []
    for a in (full_task.assignments or []):
        if hasattr(a, 'user') and a.user:
            assignees.append(GalleryTaskAssignee(
                user_id=a.user.id,
                full_name=a.user.full_name,
                role=a.user.role.value if hasattr(a.user.role, 'value') else str(a.user.role),
            ))
    return GalleryTaskInfo(
        id=full_task.id,
        title=full_task.title,
        description=full_task.description,
        status=full_task.status,
        due_date=full_task.due_date,
        completed_at=full_task.completed_at,
        assignees=assignees,
    )


async def _build_response(db, item) -> GalleryItemResponse:
    """Построить GalleryItemResponse из ORM-объекта."""
    files_info = [GalleryFileInfo(**fd) for fd in (item.files or [])]
    task_info = await _build_task_info(db, item.task) if item.task else None
    return GalleryItemResponse(
        id=item.id,
        title=item.title,
        description=item.description,
        category=item.category,
        tags=item.tags or [],
        task_id=item.task_id,
        thumbnail_url=item.thumbnail_url,
        files=files_info,
        created_by=item.created_by,
        creator_name=item.creator.full_name if item.creator else None,
        task=task_info,
        sort_order=item.sort_order,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class GalleryReorderRequest(BaseModel):
    """Схема для изменения порядка элементов галереи (только для VP4PR)"""
    item_orders: dict[str, Optional[int]] = Field(..., description="Словарь {item_id: sort_order} для изменения порядка элементов. sort_order: меньше = выше, null = автоматическая сортировка")


@router.get("", response_model=GalleryItemListResponse)
async def get_gallery_items(
    skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
    limit: int = Query(100, ge=1, le=100, description="Количество записей"),
    category: Optional[GalleryCategory] = Query(None, description="Фильтр по категории (photo, video, final, wip)"),
    task_id: Optional[UUID] = Query(None, description="Фильтр по ID задачи"),
    created_by: Optional[UUID] = Query(None, description="Фильтр по создателю"),
    tags: Optional[str] = Query(None, description="Фильтр по тегам (через запятую)"),
    sort_by: Optional[str] = Query("relevance", description="Сортировка: relevance (важность), created_at (дата создания), title (название), manual (ручной порядок)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список элементов галереи с фильтрацией и сортировкой
    
    Доступно всем авторизованным пользователям
    """
    # Парсим теги
    tag_list = None
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Валидация параметров
    valid_sort_by = ["relevance", "created_at", "title", "manual"]
    if sort_by not in valid_sort_by:
        sort_by = "relevance"
    
    items, total = await GalleryService.get_gallery_items(
        db=db,
        skip=skip,
        limit=limit,
        category=category,
        task_id=task_id,
        created_by=created_by,
        tags=tag_list,
        sort_by=sort_by
    )
    
    items_response = []
    for item in items:
        items_response.append(await _build_response(db, item))
    
    return GalleryItemListResponse(
        items=items_response,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/{item_id}", response_model=GalleryItemResponse)
async def get_gallery_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить элемент галереи по ID
    
    Доступно всем авторизованным пользователям
    """
    item = await GalleryService.get_gallery_item_by_id(db, item_id)
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery item not found"
        )
    
    return await _build_response(db, item)


@router.post("", response_model=GalleryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_gallery_item(
    title: str = Form(..., description="Название проекта/работы"),
    description: Optional[str] = Form(None, description="Описание проекта"),
    category: GalleryCategory = Form(GalleryCategory.FINAL, description="Категория работы"),
    tags: Optional[str] = Form(None, description="Теги через запятую"),
    task_id: Optional[str] = Form(None, description="ID связанной задачи"),
    thumbnail_url: Optional[str] = Form(None, description="URL превью (миниатюры)"),
    files: Optional[List[UploadFile]] = File(None, description="Файлы для загрузки"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Создать новый элемент галереи
    
    Можно загрузить несколько файлов одновременно.
    Файлы автоматически загружаются на Google Drive.
    
    Доступно всем авторизованным пользователям
    """
    # Парсим теги
    tag_list = None
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
    
    # Парсим task_id
    task_uuid = None
    if task_id:
        try:
            task_uuid = UUID(task_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid task_id format"
            )
    
    # Создаём схему для создания элемента
    item_data = GalleryItemCreate(
        title=title,
        description=description,
        category=category,
        tags=tag_list,
        task_id=task_uuid,
        thumbnail_url=thumbnail_url,
        files=[]  # Файлы будут загружены отдельно
    )
    
    # Загружаем файлы, если они предоставлены
    uploaded_files = []
    file_names = []
    
    if files:
        for file in files:
            try:
                file_bytes = await file.read()
                uploaded_files.append(file_bytes)
                file_names.append(file.filename)
            except Exception as e:
                import logging
                logging.error(f"Ошибка чтения файла {file.filename}: {e}")
                continue
    
    gallery_service = GalleryService()
    try:
        item = await gallery_service.create_gallery_item(
            db=db,
            item_data=item_data,
            created_by=current_user.id,
            uploaded_files=uploaded_files if uploaded_files else None,
            file_names=file_names if file_names else None
        )
    except Exception as e:
        import logging
        logging.error(f"Ошибка создания элемента галереи: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания элемента галереи: {str(e)}"
        )
    
    return await _build_response(db, item)


@router.put("/{item_id}", response_model=GalleryItemResponse)
async def update_gallery_item(
    item_id: UUID,
    item_data: GalleryItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить элемент галереи
    
    Доступно создателю элемента или VP4PR
    """
    item = await GalleryService.update_gallery_item(
        db=db,
        item_id=item_id,
        item_data=item_data,
        current_user=current_user
    )
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery item not found or you don't have permission to update it"
        )
    
    return await _build_response(db, item)


@router.post("/sync/drive", response_model=dict)
async def sync_gallery_from_drive(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Синхронизировать галерею с Google Drive
    
    Сканирует папку "BEST PR System/Gallery" и автоматически добавляет новые файлы в базу данных.
    Доступно только координаторам и VP4PR.
    """
    from app.services.gallery_service import GalleryService
    
    gallery_service = GalleryService()
    try:
        # Находим пользователя VP4PR для привязки созданных элементов
        from app.models.user import UserRole
        from sqlalchemy import select
        
        # Сначала ищем VP4PR
        vp4pr_query = select(User).where(User.role.in_([UserRole.VP4PR, UserRole.ADMIN])).limit(1)
        result = await db.execute(vp4pr_query)
        vp4pr_user = result.scalar_one_or_none()
        
        # Если VP4PR нет, используем текущего пользователя (координатора)
        creator_id = vp4pr_user.id if vp4pr_user else current_user.id
        
        result = await gallery_service.sync_gallery_from_drive(
            db=db,
            created_by=creator_id
        )
        
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to sync gallery from Drive: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при синхронизации с Google Drive: {str(e)}"
        )


@router.post("/reorder", response_model=dict)
async def reorder_gallery_items(
    request: GalleryReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Изменить порядок элементов галереи (ручная сортировка)
    
    Доступно только VP4PR.
    Позволяет вручную установить порядок элементов в галерее.
    
    Request body:
    {
        "item_orders": {
            "item_id_1": 1,  // sort_order = 1 (будет первым)
            "item_id_2": 2,  // sort_order = 2 (будет вторым)
            "item_id_3": null  // sort_order = null (автоматическая сортировка)
        }
    }
    """
    from app.models.user import UserRole
    
    # Проверка прав - только VP4PR может менять порядок
    if not current_user.role.is_privileged():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only VP4PR can reorder gallery items"
        )
    
    item_orders = request.item_orders
    
    if not item_orders or not isinstance(item_orders, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_orders must be a dictionary with item_id: sort_order pairs"
        )
    
    updated_count = 0
    
    try:
        for item_id_str, sort_order in item_orders.items():
            try:
                item_id = UUID(item_id_str)
            except (ValueError, TypeError):
                continue  # Пропускаем невалидные ID
            
            # Получаем элемент
            item = await GalleryService.get_gallery_item_by_id(db, item_id)
            if not item:
                continue  # Пропускаем несуществующие элементы
            
            # Обновляем порядок
            item.sort_order = sort_order if sort_order is not None else None
            
            updated_count += 1
        
        # Сохраняем изменения
        await db.commit()
        
        return {
            "status": "success",
            "updated_count": updated_count,
            "message": f"Порядок {updated_count} элементов галереи обновлён"
        }
        
    except Exception as e:
        await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to reorder gallery items: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при изменении порядка элементов: {str(e)}"
        )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_gallery_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удалить элемент галереи
    
    Файлы автоматически удаляются из Google Drive.
    
    Доступно создателю элемента или VP4PR
    """
    success = await GalleryService.delete_gallery_item(
        db=db,
        item_id=item_id,
        current_user=current_user
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gallery item not found or you don't have permission to delete it"
        )
    
    return None
