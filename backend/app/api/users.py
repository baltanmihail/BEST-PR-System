"""
API endpoints для пользователей и профилей
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    UserResponse, UserProfileResponse, UserUpdate, ProfileUpdate, UserStats, UserListResponse
)
from app.utils.permissions import get_current_user, require_coordinator
from app.services.gallery_service import GalleryService
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService

router = APIRouter(prefix="/users", tags=["users", "monitoring"])


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить свой профиль
    
    Доступно всем авторизованным пользователям
    """
    # Обновляем время последней активности (пользователь активен)
    current_user.last_activity_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(current_user)
    
    return UserProfileResponse.model_validate(current_user)


@router.put("/me", response_model=UserProfileResponse)
async def update_my_profile(
    profile_data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить свой профиль
    
    Доступно всем авторизованным пользователям
    """
    update_data = profile_data.model_dump(exclude_unset=True)
    updated_fields = list(update_data.keys())
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    # Обновляем время последней активности
    current_user.last_activity_at = datetime.now(timezone.utc)
    
    # Логируем обновление профиля
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_profile_updated(
            db=db,
            user_id=current_user.id,
            updated_fields=updated_fields
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to log profile update: {e}")
    
    await db.commit()
    await db.refresh(current_user)
    
    return UserProfileResponse.model_validate(current_user)


@router.post("/me/photo", response_model=UserProfileResponse)
async def upload_profile_photo(
    photo: UploadFile = File(..., description="Фото профиля"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Загрузить фото профиля
    
    Фото автоматически загружается на Google Drive в папку Users/{user_id}/
    
    Доступно всем авторизованным пользователям
    """
    from concurrent.futures import ThreadPoolExecutor
    import asyncio
    import mimetypes
    
    # Проверяем, что это изображение
    mime_type, _ = mimetypes.guess_type(photo.filename)
    if not mime_type or not mime_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл должен быть изображением"
        )
    
    try:
        # Читаем файл
        file_bytes = await photo.read()
        
        # Загружаем на Google Drive
        google_service = GoogleService()
        drive_structure = DriveStructureService()
        
        # Получаем папку пользователя
        users_folder_id = drive_structure.get_users_folder_id()
        
        # Создаём папку для пользователя, если её нет
        user_folder_id = google_service.get_or_create_folder(
            str(current_user.id),
            parent_folder_id=users_folder_id,
            background=False
        )
        
        # Загружаем фото
        executor = ThreadPoolExecutor(max_workers=5)
        loop = asyncio.get_event_loop()
        
        drive_file = await loop.run_in_executor(
            executor,
            lambda: google_service.upload_file(
                file_name=photo.filename,
                file_content=file_bytes,
                mime_type=mime_type,
                parent_folder_id=user_folder_id,
                background=False
            )
        )
        
        # Получаем ссылку для просмотра
        photo_url = google_service.get_shareable_link(
            drive_file.get('id'),
            background=False
        )
        
        # Обновляем профиль
        current_user.avatar_url = photo_url
        await db.commit()
        await db.refresh(current_user)
        
        return UserProfileResponse.model_validate(current_user)
        
    except Exception as e:
        import logging
        logging.error(f"Ошибка загрузки фото профиля: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка загрузки фото: {str(e)}"
        )


@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить свою статистику
    
    Доступно всем авторизованным пользователям
    """
    from app.services.user_stats_service import UserStatsService
    
    stats = await UserStatsService.get_user_stats(db, current_user.id)
    
    return stats


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить профиль пользователя по ID
    
    Доступно всем авторизованным пользователям
    """
    from sqlalchemy import select
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserProfileResponse.model_validate(user)


@router.get("/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить статистику пользователя по ID
    
    Доступно всем авторизованным пользователям
    """
    from sqlalchemy import select
    from app.services.user_stats_service import UserStatsService
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    stats = await UserStatsService.get_user_stats(db, user_id)
    
    return stats


@router.get("", response_model=UserListResponse)
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Поиск по имени или username"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список пользователей
    
    Доступно всем авторизованным пользователям
    """
    from sqlalchemy import select, or_, and_, func
    
    # Базовая выборка для подсчёта общего количества
    base_query = select(User).where(User.deleted_at.is_(None))
    
    conditions = []
    
    if role:
        # Конвертируем роль в значение для сравнения
        role_value = role.value if hasattr(role, 'value') else role
        conditions.append(User.role == role_value)
    if is_active is not None:
        conditions.append(User.is_active == is_active)
    if search:
        search_pattern = f"%{search}%"
        # Поиск только по имени и username (email не запрашивается при регистрации)
        conditions.append(
            or_(
                User.full_name.ilike(search_pattern),
                User.username.ilike(search_pattern)
            )
        )
    
    if conditions:
        base_query = base_query.where(and_(*conditions))
    
    # Подсчитываем общее количество - используем тот же запрос без пагинации
    count_query = select(func.count(User.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))
    count_query = count_query.where(User.deleted_at.is_(None))
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получаем пользователей с пагинацией
    query = base_query.order_by(User.points.desc(), User.created_at.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return UserListResponse(
        items=[UserProfileResponse.model_validate(user) for user in users],
        total=total,
        skip=skip,
        limit=limit
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Обновить пользователя (только для координаторов и VP4PR)
    
    Доступно только координаторам и VP4PR
    """
    from sqlalchemy import select
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Проверка прав: только VP4PR может менять роли
    old_role = user.role.value if isinstance(user.role, UserRole) else str(user.role)
    if user_data.role and user_data.role != user.role:
        if current_user.role != UserRole.VP4PR:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only VP4PR can change user roles"
            )
    
    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    # Логируем изменение роли, если оно было
    if user_data.role and user_data.role != user.role:
        from app.services.activity_service import ActivityService
        try:
            new_role = user_data.role.value if isinstance(user_data.role, UserRole) else str(user_data.role)
            await ActivityService.log_role_changed(
                db=db,
                user_id=user_id,
                old_role=old_role,
                new_role=new_role,
                changed_by=current_user.id
            )
            
            # Если новая роль - координатор или VP4PR, добавляем в чат координаторов
            if "coordinator" in new_role or new_role == "vp4pr":
                from app.services.telegram_chat_service import TelegramChatService
                # Запускаем в фоне, чтобы не блокировать ответ
                import asyncio
                asyncio.create_task(TelegramChatService.add_user_to_coordinators_topic(db, user))
                
        except Exception as e:
            import logging
            logging.warning(f"Failed to log role change or add to chat: {e}")
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post("/{user_id}/block", response_model=UserResponse)
async def block_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Заблокировать пользователя
    
    Доступно только координаторам и VP4PR
    """
    from sqlalchemy import select
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = False
    
    # Логируем блокировку
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_user_blocked(
            db=db,
            user_id=user_id,
            blocked_by=current_user.id,
            reason=None  # Можно добавить параметр reason позже
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to log user block: {e}")
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post("/{user_id}/unblock", response_model=UserResponse)
async def unblock_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Разблокировать пользователя
    
    Доступно только координаторам и VP4PR
    """
    from sqlalchemy import select
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.is_active = True
    
    # Логируем разблокировку
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_user_unblocked(
            db=db,
            user_id=user_id,
            unblocked_by=current_user.id
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to log user unblock: {e}")
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.post("/{user_id}/points", response_model=UserResponse)
async def adjust_user_points(
    user_id: UUID,
    points_delta: int = Form(..., description="Изменение баллов (может быть отрицательным)"),
    reason: Optional[str] = Form(None, description="Причина изменения баллов"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Изменить баллы пользователя (только для координаторов и VP4PR)
    
    Доступно только координаторам и VP4PR
    """
    from sqlalchemy import select
    
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Обновляем баллы
    user.points = max(0, user.points + points_delta)  # Не допускаем отрицательные баллы
    
    # Логируем изменение
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_points_adjustment(
            db=db,
            user_id=user_id,
            points_delta=points_delta,
            reason=reason or "Manual adjustment",
            adjusted_by=current_user.id
        )
    except Exception as e:
        import logging
        logging.warning(f"Failed to log points adjustment: {e}")
    
    await db.commit()
    await db.refresh(user)
    
    return UserResponse.model_validate(user)


@router.get("/{user_id}/activity")
async def get_user_activity(
    user_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = Query(None, description="Фильтр по типу действия"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить историю активности пользователя
    
    Доступно самому пользователю, координаторам и VP4PR
    """
    from sqlalchemy import select
    from app.models.activity import ActivityLog
    
    # Проверка прав: пользователь может видеть только свою активность, координаторы и VP4PR - любую
    if current_user.id != user_id and current_user.role not in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own activity"
        )
    
    query = select(ActivityLog).where(ActivityLog.user_id == user_id)
    
    if action:
        query = query.where(ActivityLog.action == action)
    
    query = query.order_by(ActivityLog.timestamp.desc()).offset(skip).limit(limit)
    
    result = await db.execute(query)
    activities = result.scalars().all()
    
    return [
        {
            "id": str(activity.id),
            "action": activity.action,
            "timestamp": activity.timestamp.isoformat(),
            "details": activity.details
        }
        for activity in activities
    ]


@router.get("/{user_id}/tasks")
async def get_user_tasks(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить задачи пользователя (текущие и выполненные)
    
    Доступно самому пользователю, координаторам и VP4PR
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.task import Task, TaskAssignment, AssignmentStatus
    from app.schemas.task import TaskResponse, TaskAssignmentResponse
    
    # Проверка прав: пользователь может видеть только свои задачи, координаторы и VP4PR - любые
    if current_user.id != user_id and current_user.role not in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own tasks"
        )
    
    # Получаем назначения задач пользователя
    assignments_query = select(TaskAssignment).options(
        selectinload(TaskAssignment.task)
    ).where(
        TaskAssignment.user_id == user_id
    ).order_by(TaskAssignment.assigned_at.desc())
    
    result = await db.execute(assignments_query)
    assignments = result.scalars().all()
    
    # Разделяем на текущие и выполненные задачи
    active_tasks = []
    completed_tasks = []
    
    for assignment in assignments:
        task_data = {
            "task": TaskResponse.model_validate(assignment.task),
            "assignment": TaskAssignmentResponse.model_validate(assignment)
        }
        
        if assignment.status in [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS]:
            active_tasks.append(task_data)
        elif assignment.status == AssignmentStatus.COMPLETED:
            completed_tasks.append(task_data)
    
    return {
        "active": active_tasks,
        "completed": completed_tasks,
        "total": len(assignments)
    }


@router.get("/{user_id}/export")
async def export_user_data(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Экспортировать данные о пользователе (для админов)
    
    Доступно только VP4PR
    """
    from sqlalchemy import select
    from app.models.task import Task, TaskAssignment
    from app.models.equipment import EquipmentRequest
    from app.models.activity import ActivityLog
    from app.models.gallery import GalleryItem
    
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only VP4PR can export user data"
        )
    
    # Получаем пользователя
    query = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Собираем данные
    export_data = {
        "user": {
            "id": str(user.id),
            "telegram_id": user.telegram_id,
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role.value if isinstance(user.role, UserRole) else str(user.role),
            "level": user.level,
            "points": user.points,
            "streak_days": user.streak_days,
            "last_activity_at": user.last_activity_at.isoformat() if user.last_activity_at else None,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat(),
            "is_active": user.is_active,
            "avatar_url": user.avatar_url,
            "bio": user.bio,
            "contacts": user.contacts,
            "skills": user.skills,
            "portfolio": user.portfolio,
        },
        "tasks": [],
        "equipment_requests": [],
        "gallery_items": [],
        "activity_log": []
    }
    
    # Получаем задачи пользователя
    tasks_query = select(Task).join(TaskAssignment).where(
        TaskAssignment.user_id == user_id
    )
    tasks_result = await db.execute(tasks_query)
    tasks = tasks_result.scalars().all()
    
    for task in tasks:
        export_data["tasks"].append({
            "id": str(task.id),
            "title": task.title,
            "type": task.type.value if hasattr(task.type, 'value') else str(task.type),
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "priority": task.priority.value if hasattr(task.priority, 'value') else str(task.priority),
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "created_at": task.created_at.isoformat(),
        })
    
    # Получаем заявки на оборудование
    equipment_query = select(EquipmentRequest).where(EquipmentRequest.user_id == user_id)
    equipment_result = await db.execute(equipment_query)
    equipment_requests = equipment_result.scalars().all()
    
    for req in equipment_requests:
        export_data["equipment_requests"].append({
            "id": str(req.id),
            "equipment_id": str(req.equipment_id),
            "start_date": req.start_date.isoformat() if req.start_date else None,
            "end_date": req.end_date.isoformat() if req.end_date else None,
            "status": req.status.value if hasattr(req.status, 'value') else str(req.status),
            "created_at": req.created_at.isoformat(),
        })
    
    # Получаем элементы галереи
    gallery_query = select(GalleryItem).where(GalleryItem.created_by == user_id)
    gallery_result = await db.execute(gallery_query)
    gallery_items = gallery_result.scalars().all()
    
    for item in gallery_items:
        export_data["gallery_items"].append({
            "id": str(item.id),
            "title": item.title,
            "category": item.category.value if hasattr(item.category, 'value') else str(item.category),
            "tags": item.tags,
            "created_at": item.created_at.isoformat(),
        })
    
    # Получаем логи активности
    activity_query = select(ActivityLog).where(ActivityLog.user_id == user_id)
    activity_query = activity_query.order_by(ActivityLog.timestamp.desc()).limit(1000)
    activity_result = await db.execute(activity_query)
    activities = activity_result.scalars().all()
    
    for activity in activities:
        export_data["activity_log"].append({
            "id": str(activity.id),
            "action": activity.action,
            "timestamp": activity.timestamp.isoformat(),
            "details": activity.details
        })
    
    return export_data
