"""
API endpoints для задач
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from uuid import UUID
from datetime import timedelta
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.database import get_db
from app.models.user import User
from app.models.task import TaskType, TaskStatus, TaskPriority
from app.schemas.task import (
    TaskResponse, TaskDetailResponse, TaskCreate, TaskUpdate, TaskFileResponse
)
from pydantic import BaseModel, Field
from app.services.task_service import TaskService
from app.utils.permissions import get_current_user, require_coordinator

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskReorderRequest(BaseModel):
    """Схема для изменения порядка задач (только для VP4PR)"""
    task_orders: dict[str, Optional[int]] = Field(..., description="Словарь {task_id: sort_order} для изменения порядка задач. sort_order: меньше = выше, null = автоматическая сортировка")


@router.get("", response_model=dict)
async def get_tasks(
    skip: int = Query(0, ge=0, description="Количество пропущенных записей"),
    limit: int = Query(100, ge=1, le=100, description="Количество записей"),
    task_type: Optional[TaskType] = Query(None, description="Фильтр по типу задачи (smm, design, channel, prfr)"),
    status: Optional[TaskStatus] = Query(None, description="Фильтр по статусу"),
    priority: Optional[TaskPriority] = Query(None, description="Фильтр по приоритету"),
    sort_by: Optional[str] = Query("relevance", description="Сортировка: relevance (важность), priority (приоритет), due_date (дедлайн), created_at (дата создания), manual (ручной порядок)"),
    view_mode: Optional[str] = Query("normal", description="Режим отображения: compact (упрощённый), normal (обычный), detailed (подробный)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить список задач с фильтрацией, сортировкой и пагинацией
    
    Упрощённый вид (таблицей):
    - compact: только основные поля (id, название, тип, статус, приоритет, дедлайн)
    - normal: основные поля + краткое описание + этапы/назначения (количество)
    - detailed: все поля задачи
    
    Сортировка:
    - relevance (по умолчанию): по важности (ручной порядок > приоритет > горящие дедлайны)
    - priority: по приоритету (critical > high > medium > low)
    - due_date: по дедлайну (горящие сверху, затем по дате)
    - created_at: по дате создания (новые сверху)
    - manual: только ручной порядок (для VP4PR)
    
    Доступно всем авторизованным пользователям
    """
    from typing import Literal
    
    # Валидация параметров
    valid_sort_by = ["relevance", "priority", "due_date", "created_at", "manual"]
    if sort_by not in valid_sort_by:
        sort_by = "relevance"
    
    valid_view_modes = ["compact", "normal", "detailed"]
    if view_mode not in valid_view_modes:
        view_mode = "normal"
    
    tasks, total = await TaskService.get_tasks(
        db=db,
        skip=skip,
        limit=limit,
        task_type=task_type,
        status=status,
        priority=priority,
        sort_by=sort_by,
        view_mode=view_mode
    )
    
    # Формируем ответ в зависимости от режима отображения
    if view_mode == "compact":
        # Упрощённый вид (таблицей) - только основные поля
        items = []
        for task in tasks:
            # Проверяем, есть ли горящий дедлайн (в течение 3 дней)
            is_hot = False
            if task.due_date:
                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone.utc)
                hot_deadline = now + timedelta(days=3)
                if now <= task.due_date <= hot_deadline:
                    is_hot = True
            
            items.append({
                "id": str(task.id),
                "title": task.title,
                "type": task.type.value,
                "status": task.status.value,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "is_hot": is_hot,  # Горящий дедлайн (в течение 3 дней)
                "thumbnail": task.thumbnail_image_url,
                "sort_order": task.sort_order  # Ручной порядок (для VP4PR)
            })
    elif view_mode == "normal":
        # Обычный вид - основные поля + краткое описание + счётчики
        items = []
        for task in tasks:
            # Проверяем, есть ли горящий дедлайн
            is_hot = False
            if task.due_date:
                from datetime import datetime, timezone, timedelta
                now = datetime.now(timezone.utc)
                hot_deadline = now + timedelta(days=3)
                if now <= task.due_date <= hot_deadline:
                    is_hot = True
            
            items.append({
                "id": str(task.id),
                "title": task.title,
                "type": task.type.value,
                "status": task.status.value,
                "priority": task.priority.value,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "is_hot": is_hot,
                "description": (task.description[:150] + "...") if task.description and len(task.description) > 150 else (task.description or ""),
                "thumbnail": task.thumbnail_image_url,
                "assignments_count": len(task.assignments) if hasattr(task, 'assignments') and task.assignments else 0,
                "stages_count": len(task.stages) if task.stages else 0,
                "created_at": task.created_at.isoformat(),
                "sort_order": task.sort_order
            })
    else:  # detailed
        # Подробный вид - все поля задачи
        items = [TaskResponse.model_validate(task) for task in tasks]
    
    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
        "sort_by": sort_by,
        "view_mode": view_mode
    }


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить детали задачи по ID (карточка задачи)
    
    Возвращает полную информацию о задаче:
    - Основная информация (название, описание, тип, приоритет, дедлайн)
    - Этапы задачи с дедлайнами
    - Назначения (исполнители)
    - Файлы (материалы задачи) из Google Drive
    - Поля для карточки (фото, ТЗ по ролям, вопросы, примеры)
    
    Доступно всем авторизованным пользователям
    """
    task = await TaskService.get_task_by_id(db, task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Преобразуем файлы в формат для ответа
    files_response = []
    if hasattr(task, 'files') and task.files:
        from app.services.google_service import GoogleService
        from app.models.file import File
        
        google_service = GoogleService()
        _executor = ThreadPoolExecutor(max_workers=5)
        
        for file_obj in task.files:
            # Получаем ссылку на файл в Google Drive (асинхронно через executor)
            drive_url = None
            try:
                drive_url = await asyncio.get_event_loop().run_in_executor(
                    _executor,
                    lambda f=file_obj: google_service.get_shareable_link(f.drive_id, background=False)
                )
            except Exception as e:
                import logging
                logging.warning(f"Failed to get Drive URL for file {file_obj.id}: {e}")
            
            files_response.append({
                "id": file_obj.id,
                "drive_id": file_obj.drive_id,
                "file_name": file_obj.file_name,
                "file_type": file_obj.file_type,
                "drive_url": drive_url,
                "created_at": file_obj.created_at
            })
    
    # Парсим JSON поля, если они хранятся как строки (для обратной совместимости)
    role_requirements = task.role_specific_requirements
    if isinstance(role_requirements, str):
        try:
            role_requirements = json.loads(role_requirements) if role_requirements else None
        except (json.JSONDecodeError, TypeError):
            role_requirements = None
    
    questions = task.questions
    if isinstance(questions, str):
        try:
            questions = json.loads(questions) if questions else None
        except (json.JSONDecodeError, TypeError):
            questions = None
    
    example_ids = task.example_project_ids
    if isinstance(example_ids, str):
        try:
            # Преобразуем строки UUID в UUID объекты
            ids_json = json.loads(example_ids) if example_ids else []
            example_ids = [UUID(id_str) for id_str in ids_json] if ids_json else None
        except (json.JSONDecodeError, TypeError, ValueError):
            example_ids = None
    
    # Формируем словарь для валидации Pydantic
    # Используем обработанные значения для JSON полей
    task_data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "type": task.type,
        "event_id": task.event_id,
        "priority": task.priority,
        "due_date": task.due_date,
        "status": task.status,
        "created_by": task.created_by,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "stages": list(task.stages) if task.stages else [],
        "assignments": list(task.assignments) if task.assignments else [],
        "files": files_response,
        "thumbnail_image_url": task.thumbnail_image_url,
        "role_specific_requirements": role_requirements,
        "questions": questions,
        "example_project_ids": example_ids
    }
    
    return TaskDetailResponse.model_validate(task_data)


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Создать новую задачу
    
    Доступно только координаторам и VP4PR
    """
    task = await TaskService.create_task(
        db=db,
        task_data=task_data,
        created_by=current_user.id
    )
    
    # Логируем создание задачи (публично, без имени координатора)
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_task_created(
            db=db,
            task_id=task.id,
            task_title=task.title,
            task_type=task.type.value
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to log activity: {e}")
    
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Обновить задачу
    
    Доступно создателю задачи или координаторам
    """
    task = await TaskService.update_task(
        db=db,
        task_id=task_id,
        task_data=task_data,
        current_user=current_user
    )
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you don't have permission to update it"
        )
    
    return TaskResponse.model_validate(task)


@router.post("/reorder", response_model=dict)
async def reorder_tasks(
    request: TaskReorderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Изменить порядок задач (ручная сортировка)
    
    Доступно только VP4PR.
    Позволяет вручную установить порядок задач в списке.
    
    Request body:
    {
        "task_orders": {
            "task_id_1": 1,  // sort_order = 1 (будет первым)
            "task_id_2": 2,  // sort_order = 2 (будет вторым)
            "task_id_3": null  // sort_order = null (автоматическая сортировка)
        }
    }
    
    Parameters:
    - task_orders: Словарь {task_id: sort_order}, где sort_order - порядок (меньше = выше)
      Если sort_order = null, то автоматическая сортировка (по приоритету/срокам)
    
    Returns:
    - updated_count: Количество обновлённых задач
    """
    from app.models.user import UserRole
    from fastapi import HTTPException, status
    
    # Проверка прав - только VP4PR может менять порядок
    if current_user.role != UserRole.VP4PR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only VP4PR can reorder tasks"
        )
    
    task_orders = request.task_orders
    
    if not task_orders or not isinstance(task_orders, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_orders must be a dictionary with task_id: sort_order pairs"
        )
    
    updated_count = 0
    
    try:
        for task_id_str, sort_order in task_orders.items():
            try:
                task_id = UUID(task_id_str)
            except (ValueError, TypeError):
                continue  # Пропускаем невалидные ID
            
            # Получаем задачу
            task = await TaskService.get_task_by_id(db, task_id)
            if not task:
                continue  # Пропускаем несуществующие задачи
            
            # Обновляем порядок
            task.sort_order = sort_order if sort_order is not None else None
            
            updated_count += 1
        
        # Сохраняем изменения
        await db.commit()
        
        return {
            "status": "success",
            "updated_count": updated_count,
            "message": f"Порядок {updated_count} задач обновлён"
        }
        
    except Exception as e:
        await db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to reorder tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при изменении порядка задач: {str(e)}"
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Удалить задачу
    
    Доступно создателю задачи или VP4PR
    """
    success = await TaskService.delete_task(
        db=db,
        task_id=task_id,
        current_user=current_user
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or you don't have permission to delete it"
        )
    
    return None


@router.post("/{task_id}/publish", response_model=TaskResponse)
async def publish_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_coordinator())
):
    """
    Опубликовать задачу (изменить статус с DRAFT на OPEN)
    
    Доступно только координаторам и VP4PR
    """
    task = await TaskService.publish_task(
        db=db,
        task_id=task_id,
        current_user=current_user
    )
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found, already published, or you don't have permission"
        )
    
    # Уведомляем активных пользователей о новой задаче
    from app.services.notification_service import NotificationService
    from sqlalchemy import select
    from app.models.user import UserRole
    
    # Получаем активных пользователей (кроме координаторов, они и так знают)
    users_query = select(User.id).where(
        User.is_active == True,
        ~User.role.in_([
            UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
            UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
        ])
    )
    users_result = await db.execute(users_query)
    user_ids = [row[0] for row in users_result.all()]
    
    if user_ids:
        try:
            await NotificationService.notify_new_task(
                db=db,
                user_ids=user_ids,
                task_id=task.id,
                task_title=task.title,
                task_type=task.type.value
            )
        except Exception as e:
            import logging
            logging.error(f"Failed to send notifications: {e}")
    
    return TaskResponse.model_validate(task)


@router.post("/{task_id}/assign", response_model=dict)
async def assign_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Взять задачу в работу
    
    Для задач типа Channel автоматически предлагает доступное оборудование
    на даты этапа "Съёмка".
    
    Доступно всем авторизованным пользователям
    
    Returns:
        {
            "task": TaskResponse,
            "equipment_suggestions": List[EquipmentResponse] (для Channel задач)
        }
    """
    from app.models.task import TaskAssignment, AssignmentStatus, TaskType
    from app.services.equipment_service import EquipmentService
    from datetime import date
    
    # Получаем задачу
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Проверяем, не взята ли уже задача
    if task.status == TaskStatus.ASSIGNED or task.status == TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task is already assigned"
        )
    
    # Создаём назначение
    assignment = TaskAssignment(
        task_id=task_id,
        user_id=current_user.id,
        role_in_task="executor",
        status=AssignmentStatus.ASSIGNED
    )
    
    db.add(assignment)
    
    # Обновляем статус задачи
    task.status = TaskStatus.ASSIGNED
    
    # Обновляем время последней активности пользователя
    current_user.last_activity_at = datetime.now(timezone.utc)
    
    # Если это задача типа Channel и отмечена возможность получения оборудования, предлагаем оборудование
    equipment_suggestions = []
    if task.type == TaskType.CHANNEL and task.equipment_available:
        # Находим этап "Съёмка"
        shooting_stage = None
        for stage in task.stages:
            if stage.stage_name.lower() in ["съёмка", "shooting", "съемка"]:
                shooting_stage = stage
                break
        
        if shooting_stage and shooting_stage.due_date:
            # Предлагаем оборудование на даты съёмки
            shooting_date = shooting_stage.due_date.date()
            # Предполагаем, что съёмка занимает 1-2 дня
            end_date = shooting_date + timedelta(days=1)
            
            try:
                available_equipment = await EquipmentService.get_available_equipment(
                    db=db,
                    start_date=shooting_date,
                    end_date=end_date,
                    category=None  # Показываем всё доступное
                )
                equipment_suggestions = available_equipment
            except Exception as e:
                # Если ошибка при получении оборудования, продолжаем без него
                pass
    
    # Начисляем баллы за взятие задачи
    from app.services.gamification_service import GamificationService
    try:
        await GamificationService.award_task_taken_points(
            db=db,
            user_id=current_user.id,
            task=task
        )
    except Exception as e:
        # Логируем ошибку, но не прерываем процесс
        import logging
        logging.error(f"Failed to award points for task taken: {e}")
    
    # Уведомляем о назначении задачи
    from app.services.notification_service import NotificationService
    try:
        await NotificationService.notify_task_assigned(
            db=db,
            user_id=current_user.id,
            task_id=task.id,
            task_title=task.title
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to send notification: {e}")
    
    # Если есть предложения по оборудованию, отправляем уведомление в бот с кнопкой для быстрой подачи заявки
    if equipment_suggestions and task.equipment_available and current_user.telegram_id:
        try:
            from app.utils.telegram_sender import send_telegram_message
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            # Формируем сообщение с предложением оборудования
            equipment_list = "\n".join([f"• {eq.name}" for eq in equipment_suggestions[:5]])
            if len(equipment_suggestions) > 5:
                equipment_list += f"\n... и ещё {len(equipment_suggestions) - 5}"
            
            shooting_date_str = shooting_stage.due_date.strftime('%d.%m.%Y') if shooting_stage and shooting_stage.due_date else "не указана"
            
            message_text = (
                f"📦 <b>Оборудование для задачи</b>\n\n"
                f"✅ Ты взял задачу: <b>{task.title}</b>\n\n"
                f"💡 <b>Для этой задачи доступно оборудование!</b>\n\n"
                f"📅 <b>Дата съёмки:</b> {shooting_date_str}\n\n"
                f"📦 <b>Доступное оборудование:</b>\n{equipment_list}\n\n"
                f"💬 Хочешь подать заявку на оборудование прямо сейчас?"
            )
            
            # Отправляем сообщение в бот (без клавиатуры, так как send_telegram_message не поддерживает клавиатуры)
            # Пользователь может использовать команду /equipment или callback "equipment" для подачи заявки
            await send_telegram_message(
                chat_id=current_user.telegram_id,
                message=message_text,
                parse_mode="HTML"
            )
            
            # Также отправляем отдельное сообщение с кнопкой для быстрой подачи заявки
            # Для этого нужно использовать aiogram напрямую, так как send_telegram_message не поддерживает клавиатуры
            try:
                from aiogram import Bot
                from aiogram.enums import ParseMode
                from app.config import settings
                
                bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
                
                # Формируем callback_data для быстрой подачи заявки (с предзаполненными данными)
                # Сохраняем данные задачи в состояние пользователя для быстрой подачи заявки
                from app.services.telegram_chat_service import TelegramChatService
                # Можно использовать временное хранение данных в базе или в состоянии бота
                # Пока просто отправляем сообщение с кнопкой на меню оборудования
                
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📝 Подать заявку на оборудование",
                            callback_data=f"equipment_quick_request_{task_id}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text="📦 Меню оборудования",
                            callback_data="equipment"
                        ),
                    ],
                ])
                
                await bot.send_message(
                    chat_id=current_user.telegram_id,
                    text=message_text + "\n\n💡 Нажми кнопку ниже для быстрой подачи заявки:",
                    reply_markup=keyboard
                )
                
                await bot.session.close()
            except Exception as e:
                import logging
                logging.warning(f"Failed to send equipment suggestion with keyboard to user {current_user.telegram_id}: {e}")
                # Если не удалось отправить с клавиатурой, хотя бы отправили текстовое сообщение выше
        except Exception as e:
            import logging
            logging.warning(f"Failed to send equipment suggestion to user {current_user.telegram_id}: {e}")
    
    # Логируем активность
    from app.services.activity_service import ActivityService
    try:
        await ActivityService.log_task_assigned(
            db=db,
            user_id=current_user.id,
            task_id=task.id,
            task_title=task.title
        )
    except Exception as e:
        import logging
        logging.error(f"Failed to log activity: {e}")
    
    # Создаём или получаем чат для задачи
    from app.services.telegram_chat_service import TelegramChatService
    from app.models.user import UserRole
    from sqlalchemy import select
    
    try:
        # Проверяем, существует ли уже тема для задачи
        task_topic = await TelegramChatService.get_task_topic(db, task_id)
        
        if not task_topic:
            # Создаём тему для задачи в общем чате
            task_topic = await TelegramChatService.create_task_topic(
                db=db,
                task_id=task_id,
                task_title=task.title
            )
            
            if task_topic:
                import logging
                logging.info(f"Task topic created for task {task_id}: {task.title} (topic_id: {task_topic.topic_id})")
                
                # Отправляем приветственное сообщение в тему
                await TelegramChatService.send_welcome_message_to_chat(
                    chat_id=task_topic.chat_id,
                    user_full_name=current_user.full_name,
                    is_new_user=False,
                    topic_id=task_topic.topic_id
                )
        else:
            # Если тема уже существует, пользователь уже в общем чате
            # Можно отправить уведомление в тему о новом участнике
            import logging
            logging.info(f"Task topic already exists for task {task_id}: {task_topic.topic_id}")
    except Exception as e:
        import logging
        logging.error(f"Failed to create/add user to task topic: {e}")
    
    await db.commit()
    await db.refresh(task)
    
    return {
        "task": TaskResponse.model_validate(task),
        "equipment_suggestions": [
            {
                "id": str(eq.id),
                "name": eq.name,
                "category": eq.category,
                "available_dates": {
                    "start": shooting_stage.due_date.date().isoformat() if shooting_stage else None,
                    "end": (shooting_stage.due_date.date() + timedelta(days=1)).isoformat() if shooting_stage else None
                }
            }
            for eq in equipment_suggestions[:10]  # Ограничиваем до 10 предложений
        ] if equipment_suggestions else []
    }


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Завершить задачу
    
    Доступно исполнителю задачи или координаторам
    """
    from app.models.task import TaskAssignment, AssignmentStatus
    from sqlalchemy import select
    
    # Получаем задачу
    task = await TaskService.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Проверяем, есть ли назначение на текущего пользователя
    result = await db.execute(
        select(TaskAssignment).where(
            TaskAssignment.task_id == task_id,
            TaskAssignment.user_id == current_user.id
        )
    )
    assignment = result.scalar_one_or_none()
    
    # Проверка прав (исполнитель или координатор)
    from app.models.user import UserRole
    is_coordinator = current_user.role in [
        UserRole.COORDINATOR_SMM, UserRole.COORDINATOR_DESIGN,
        UserRole.COORDINATOR_CHANNEL, UserRole.COORDINATOR_PRFR, UserRole.VP4PR
    ]
    
    if not assignment and not is_coordinator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not assigned to this task"
        )
    
    # Обновляем назначение
    completed_at = None
    if assignment:
        assignment.status = AssignmentStatus.COMPLETED
        from datetime import datetime, timezone
        completed_at = datetime.now(timezone.utc)
        assignment.completed_at = completed_at
    
    # Обновляем статус задачи
    task.status = TaskStatus.COMPLETED
    
    # Обновляем время последней активности пользователя
    current_user.last_activity_at = datetime.now(timezone.utc)
    
    # Начисляем баллы за выполнение задачи
    from app.services.gamification_service import GamificationService
    if assignment and completed_at:
        try:
            # Начисляем баллы за выполнение
            await GamificationService.award_task_completed_points(
                db=db,
                user_id=current_user.id,
                task=task,
                assignment=assignment,
                completed_at=completed_at
            )
            
            # Проверяем и начисляем ачивки
            new_achievements = await GamificationService.check_and_award_achievements(
                db=db,
                user_id=current_user.id,
                task=task
            )
            
            # Уведомляем о новых ачивках
            from app.services.notification_service import NotificationService
            achievement_names = {
                "first_task": "🎯 Первая кровь",
                "speedster": "⚡ Скорострел",
                "reliable": "🛡️ Надёжный",
                "director": "🎬 Режиссёр",
                "designer": "🖌️ Дизайнер",
                "smm_guru": "📢 SMM-гур",
                "helper": "🤝 Помощник",
                "unstoppable": "🔥 Неудержимый"
            }
            for achievement in new_achievements:
                await NotificationService.notify_achievement_unlocked(
                    db=db,
                    user_id=current_user.id,
                    achievement_type=achievement.achievement_type,
                    achievement_name=achievement_names.get(achievement.achievement_type, achievement.achievement_type)
                )
            
            # Уведомляем о завершении задачи
            await NotificationService.notify_task_completed(
                db=db,
                user_id=current_user.id,
                task_id=task.id,
                task_title=task.title
            )
            
            # Логируем активность
            from app.services.activity_service import ActivityService
            await ActivityService.log_task_completed(
                db=db,
                user_id=current_user.id,
                task_id=task.id,
                task_title=task.title
            )
            
            # Логируем достижения
            for achievement in new_achievements:
                achievement_names = {
                    "first_task": "🎯 Первая кровь",
                    "speedster": "⚡ Скорострел",
                    "reliable": "🛡️ Надёжный",
                    "director": "🎬 Режиссёр",
                    "designer": "🖌️ Дизайнер",
                    "smm_guru": "📢 SMM-гур",
                    "helper": "🤝 Помощник",
                    "unstoppable": "🔥 Неудержимый"
                }
                await ActivityService.log_achievement_unlocked(
                    db=db,
                    user_id=current_user.id,
                    achievement_type=achievement.achievement_type,
                    achievement_name=achievement_names.get(achievement.achievement_type, achievement.achievement_type)
                )
        except Exception as e:
            # Логируем ошибку, но не прерываем процесс
            import logging
            logging.error(f"Failed to award points/achievements for task completion: {e}")
    
    await db.commit()
    await db.refresh(task)
    
    return TaskResponse.model_validate(task)
