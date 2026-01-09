"""
Сервис для работы с шаблонами задач
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.models.task_template import TaskTemplate, TemplateCategory
from app.models.task import TaskType, TaskPriority
from app.schemas.task import TaskTemplateCreate, TaskTemplateUpdate
from app.services.drive_structure import DriveStructureService
from app.services.google_service import GoogleService

logger = logging.getLogger(__name__)


class TaskTemplateService:
    """Сервис для работы с шаблонами задач"""
    
    @staticmethod
    async def get_templates(
        db: AsyncSession,
        category: Optional[TemplateCategory] = None,
        task_type: Optional[TaskType] = None,
        is_active: Optional[bool] = True
    ) -> List[TaskTemplate]:
        """Получить список шаблонов"""
        query = select(TaskTemplate)
        
        if category:
            query = query.where(TaskTemplate.category == category)
        if task_type:
            query = query.where(TaskTemplate.task_type == task_type)
        if is_active is not None:
            query = query.where(TaskTemplate.is_active == is_active)
        
        query = query.order_by(TaskTemplate.name)
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_template_by_id(
        db: AsyncSession,
        template_id: UUID
    ) -> Optional[TaskTemplate]:
        """Получить шаблон по ID"""
        query = select(TaskTemplate).where(TaskTemplate.id == template_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_template(
        db: AsyncSession,
        template_data: TaskTemplateCreate,
        created_by: UUID,
        category: TemplateCategory,
        google_service: Optional[GoogleService] = None
    ) -> TaskTemplate:
        """Создать новый шаблон"""
        template = TaskTemplate(
            created_by=created_by,
            category=category,
            **template_data.model_dump()
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        # Сохраняем шаблон на Drive (в фоне)
        if google_service:
            try:
                await TaskTemplateService._save_template_to_drive(
                    template, google_service
                )
            except Exception as e:
                logger.warning(f"Не удалось сохранить шаблон {template.id} на Drive: {e}")
        
        return template
    
    @staticmethod
    async def update_template(
        db: AsyncSession,
        template_id: UUID,
        template_data: TaskTemplateUpdate,
        google_service: Optional[GoogleService] = None
    ) -> Optional[TaskTemplate]:
        """Обновить шаблон"""
        template = await TaskTemplateService.get_template_by_id(db, template_id)
        
        if not template:
            return None
        
        # Нельзя изменять системные шаблоны
        if template.is_system:
            raise ValueError("Cannot update system template")
        
        # Обновляем поля
        update_data = template_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(template, field, value)
        
        await db.commit()
        await db.refresh(template)
        
        # Обновляем файл на Drive (в фоне)
        if google_service:
            try:
                await TaskTemplateService._save_template_to_drive(
                    template, google_service
                )
                # Обновляем drive_file_id в БД отдельно
                if template.drive_file_id:
                    await db.commit()
                    await db.refresh(template)
            except Exception as e:
                logger.warning(f"Не удалось обновить шаблон {template.id} на Drive: {e}")
        
        return template
    
    @staticmethod
    async def delete_template(
        db: AsyncSession,
        template_id: UUID
    ) -> bool:
        """Удалить шаблон"""
        template = await TaskTemplateService.get_template_by_id(db, template_id)
        
        if not template:
            return False
        
        # Нельзя удалять системные шаблоны
        if template.is_system:
            raise ValueError("Cannot delete system template")
        
        await db.delete(template)
        await db.commit()
        
        return True
    
    @staticmethod
    async def create_task_from_template(
        db: AsyncSession,
        template_id: UUID,
        title: str,
        created_by: UUID,
        due_date: Optional[datetime] = None
    ):
        """Создать задачу из шаблона"""
        from app.services.task_service import TaskService
        from app.schemas.task import TaskCreate
        
        template = await TaskTemplateService.get_template_by_id(db, template_id)
        if not template:
            raise ValueError("Template not found")
        
        # Формируем данные задачи из шаблона
        task_data = TaskCreate(
            title=title,
            description=template.default_description,
            type=template.task_type,
            priority=template.priority,
            due_date=due_date,
            equipment_available=template.equipment_available,
            role_specific_requirements=template.role_specific_requirements,
            questions=template.questions,
            example_project_ids=template.example_project_ids
        )
        
        # Формируем этапы из шаблона
        if template.stages_template and due_date:
            stages = []
            for stage_template in template.stages_template:
                stage_due_date = due_date - timedelta(days=stage_template.get('due_date_offset', 0))
                stages.append({
                    "stage_name": stage_template.get('stage_name', ''),
                    "stage_order": stage_template.get('stage_order', 1),
                    "due_date": stage_due_date.isoformat(),
                    "status_color": stage_template.get('status_color', 'green')
                })
            task_data.stages = stages
        
        # Создаём задачу
        task = await TaskService.create_task(db, task_data, created_by)
        
        return task
    
    @staticmethod
    async def _save_template_to_drive(
        template: TaskTemplate,
        google_service: GoogleService,
        db: Optional[AsyncSession] = None
    ):
        """Сохранить шаблон на Google Drive"""
        import json
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        def save_sync():
            try:
                drive_structure = DriveStructureService()
                templates_folder_id = drive_structure.get_templates_folder_id()
                
                # Формируем содержимое файла шаблона (JSON)
                template_data = {
                    "id": str(template.id),
                    "name": template.name,
                    "description": template.description,
                    "category": template.category.value,
                    "task_type": template.task_type.value,
                    "priority": template.priority.value,
                    "default_description": template.default_description,
                    "equipment_available": template.equipment_available,
                    "role_specific_requirements": template.role_specific_requirements,
                    "questions": template.questions,
                    "example_project_ids": [str(id) for id in (template.example_project_ids or [])],
                    "stages_template": template.stages_template
                }
                
                content = json.dumps(template_data, ensure_ascii=False, indent=2)
                filename = f"{template.name}.json"
                
                # Если файл уже существует, обновляем его
                if template.drive_file_id:
                    try:
                        # Обновляем существующий файл
                        drive_service = google_service._get_drive_service(background=True)
                        from googleapiclient.http import MediaIoBaseUpload
                        import io
                        
                        media = MediaIoBaseUpload(
                            io.BytesIO(content.encode('utf-8')),
                            mimetype='application/json',
                            resumable=True
                        )
                        
                        drive_service.files().update(
                            fileId=template.drive_file_id,
                            media_body=media
                        ).execute()
                        
                        logger.info(f"✅ Обновлён файл шаблона {template.id} на Drive: {template.drive_file_id}")
                        return template.drive_file_id
                    except Exception as e:
                        logger.warning(f"Не удалось обновить файл шаблона, создаём новый: {e}")
                
                # Создаём новый файл
                file_id = google_service.upload_file(
                    content.encode('utf-8'),
                    filename,
                    'application/json',
                    folder_id=templates_folder_id,
                    background=True
                )
                
                logger.info(f"✅ Сохранён шаблон {template.id} на Drive: {file_id}")
                return file_id
                
            except Exception as e:
                logger.error(f"Ошибка сохранения шаблона на Drive: {e}", exc_info=True)
                raise
        
        # Выполняем синхронную операцию в executor
        loop = asyncio.get_event_loop()
        file_id = await loop.run_in_executor(None, save_sync)
        
        # Обновляем БД (если сессия передана)
        if db:
            template.drive_file_id = file_id
            await db.commit()
            await db.refresh(template)
