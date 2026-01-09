"""
Сервис двусторонней синхронизации Google Drive с системой
Отслеживает изменения на Drive и синхронизирует их с БД
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from googleapiclient.errors import HttpError

from app.models.task import Task
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService

logger = logging.getLogger(__name__)


class DriveSyncService:
    """Сервис для синхронизации Google Drive с системой"""
    
    def __init__(self, google_service: GoogleService):
        self.google_service = google_service
        self.drive_structure = DriveStructureService()
    
    async def sync_task_folder_changes(
        self,
        task: Task,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Синхронизировать изменения в папке задачи на Google Drive
        
        Args:
            task: Задача для синхронизации
            db: Сессия БД
        
        Returns:
            Словарь с результатами синхронизации
        """
        if not task.drive_folder_id:
            logger.debug(f"Задача {task.id} не имеет drive_folder_id, пропускаем синхронизацию")
            return {
                "status": "skipped",
                "reason": "no_drive_folder_id"
            }
        
        try:
            # Получаем список файлов в папке задачи
            files = self.google_service.list_files(
                folder_id=task.drive_folder_id,
                background=True
            )
            
            # Получаем timestamp последней синхронизации
            last_sync = task.drive_last_sync or datetime.min.replace(tzinfo=timezone.utc)
            
            # Фильтруем файлы, изменённые после последней синхронизации
            changed_files = []
            for file in files:
                modified_time = datetime.fromisoformat(
                    file.get('modifiedTime', '').replace('Z', '+00:00')
                )
                if modified_time > last_sync:
                    changed_files.append(file)
            
            # Обновляем метаданные задачи на основе изменений
            # (пока только логируем, полная реализация будет добавлена позже)
            if changed_files:
                logger.info(
                    f"Обнаружено {len(changed_files)} изменённых файлов в папке задачи {task.id}"
                )
                
                # Обновляем timestamp последней синхронизации
                task.drive_last_sync = datetime.now(timezone.utc)
                await db.commit()
                await db.refresh(task)
            
            return {
                "status": "success",
                "task_id": str(task.id),
                "files_checked": len(files),
                "files_changed": len(changed_files),
                "last_sync": task.drive_last_sync.isoformat() if task.drive_last_sync else None
            }
            
        except HttpError as e:
            logger.error(f"Ошибка Google Drive API при синхронизации задачи {task.id}: {e}")
            return {
                "status": "error",
                "error": str(e),
                "task_id": str(task.id)
            }
        except Exception as e:
            logger.error(f"Ошибка синхронизации задачи {task.id}: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "task_id": str(task.id)
            }
    
    async def sync_all_task_folders(
        self,
        db: AsyncSession,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Синхронизировать все папки задач
        
        Args:
            db: Сессия БД
            limit: Максимальное количество задач для синхронизации (None = все)
        
        Returns:
            Словарь с результатами синхронизации
        """
        # Получаем все задачи с drive_folder_id
        query = select(Task).where(Task.drive_folder_id.isnot(None))
        if limit:
            query = query.limit(limit)
        
        result = await db.execute(query)
        tasks = result.scalars().all()
        
        logger.info(f"Начинаем синхронизацию {len(tasks)} задач с Google Drive")
        
        results = {
            "total": len(tasks),
            "success": 0,
            "errors": 0,
            "skipped": 0,
            "details": []
        }
        
        for task in tasks:
            sync_result = await self.sync_task_folder_changes(task, db)
            results["details"].append(sync_result)
            
            if sync_result["status"] == "success":
                results["success"] += 1
            elif sync_result["status"] == "error":
                results["errors"] += 1
            elif sync_result["status"] == "skipped":
                results["skipped"] += 1
        
        logger.info(
            f"Синхронизация завершена: успешно {results['success']}, "
            f"ошибок {results['errors']}, пропущено {results['skipped']}"
        )
        
        return results
    
    async def sync_task_to_drive(
        self,
        task: Task,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Синхронизировать изменения задачи в Google Drive
        
        Вызывается при изменении задачи в системе для обновления файлов на Drive
        
        Args:
            task: Задача для синхронизации
            db: Сессия БД
        
        Returns:
            Словарь с результатами синхронизации
        """
        if not task.drive_folder_id:
            logger.debug(f"Задача {task.id} не имеет drive_folder_id, пропускаем синхронизацию")
            return {
                "status": "skipped",
                "reason": "no_drive_folder_id"
            }
        
        try:
            # TODO: Реализовать обновление файлов ТЗ в Google Drive
            # - Обновить Google Doc с описанием задачи
            # - Обновить файлы ТЗ для каждой роли (если есть)
            # - Обновить метаданные папки
            
            logger.info(f"Синхронизация задачи {task.id} в Google Drive (заглушка)")
            
            # Обновляем timestamp последней синхронизации
            task.drive_last_sync = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(task)
            
            return {
                "status": "success",
                "task_id": str(task.id),
                "message": "Синхронизация в Drive (заглушка)"
            }
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации задачи {task.id} в Drive: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "task_id": str(task.id)
            }
