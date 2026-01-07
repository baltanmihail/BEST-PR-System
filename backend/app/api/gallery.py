"""
API endpoints для галереи результатов
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from typing import Optional, List
from uuid import UUID

from app.database import get_db
from app.models.task import Task, TaskStatus
from app.models.file import File
from app.models.user import User
from app.utils.permissions import OptionalUser

router = APIRouter(prefix="/gallery", tags=["gallery"])


@router.get("", response_model=dict)
async def get_gallery(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    task_type: Optional[str] = Query(None, description="Фильтр по типу задачи"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(OptionalUser)
):
    """
    Получить галерею выполненных работ
    
    Доступно всем (публичный endpoint)
    Показывает только завершённые задачи с файлами
    """
    # Получаем завершённые задачи
    query = select(Task).where(
        Task.status == TaskStatus.COMPLETED
    )
    
    if task_type:
        query = query.where(Task.type == task_type)
    
    # Подсчёт общего количества
    count_query = select(func.count(Task.id)).where(
        Task.status == TaskStatus.COMPLETED
    )
    if task_type:
        count_query = count_query.where(Task.type == task_type)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Получение задач с пагинацией
    query = query.order_by(Task.updated_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    
    # Получаем файлы для задач
    task_ids = [t.id for t in tasks]
    files_query = select(File).where(File.task_id.in_(task_ids))
    files_result = await db.execute(files_query)
    files = files_result.scalars().all()
    
    # Группируем файлы по задачам
    files_by_task = {}
    for file in files:
        if file.task_id not in files_by_task:
            files_by_task[file.task_id] = []
        files_by_task[file.task_id].append(file)
    
    # Формируем галерею
    items = []
    for task in tasks:
        task_files = files_by_task.get(task.id, [])
        
        # Показываем только задачи с файлами (результатами)
        if not task_files:
            continue
        
        items.append({
            "id": str(task.id),
            "title": task.title,
            "type": task.type.value,
            "completed_at": task.updated_at.isoformat() if task.updated_at else None,
            "files": [
                {
                    "id": str(f.id),
                    "file_name": f.file_name,
                    "file_type": f.file_type,
                    "drive_id": f.drive_id,
                    "version": f.version
                }
                for f in task_files
            ],
            "files_count": len(task_files)
        })
    
    return {
        "items": items,
        "total": len(items),  # Только задачи с файлами
        "skip": skip,
        "limit": limit
    }


@router.get("/{task_id}", response_model=dict)
async def get_task_gallery(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить галерею результатов для конкретной задачи
    
    Доступно всем (публичный endpoint)
    """
    # Получаем задачу
    query = select(Task).where(
        and_(
            Task.id == task_id,
            Task.status == TaskStatus.COMPLETED
        )
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not completed"
        )
    
    # Получаем файлы
    files_query = select(File).where(File.task_id == task_id)
    files_result = await db.execute(files_query)
    files = files_result.scalars().all()
    
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No files found for this task"
        )
    
    return {
        "task": {
            "id": str(task.id),
            "title": task.title,
            "type": task.type.value,
            "description": task.description,  # Для завершённых задач показываем описание
            "completed_at": task.updated_at.isoformat() if task.updated_at else None
        },
        "files": [
            {
                "id": str(f.id),
                "file_name": f.file_name,
                "file_type": f.file_type,
                "drive_id": f.drive_id,
                "version": f.version,
                "uploaded_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in files
        ]
    }
