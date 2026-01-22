"""
Сервис для работы с галереей проектов
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.models.gallery import GalleryItem, GalleryCategory
from app.models.user import User
from app.schemas.gallery import GalleryItemCreate, GalleryItemUpdate, GalleryFileInfo
from app.services.google_service import GoogleService
from app.services.drive_structure import DriveStructureService

logger = logging.getLogger(__name__)


class GalleryService:
    """Сервис для работы с галереей проектов"""
    
    def __init__(self):
        self.google_service: Optional[GoogleService] = None
        self.drive_structure: Optional[DriveStructureService] = None
    
    def _get_google_service(self) -> GoogleService:
        """Ленивая инициализация GoogleService"""
        if self.google_service is None:
            self.google_service = GoogleService()
        return self.google_service
    
    def _get_drive_structure(self) -> DriveStructureService:
        """Ленивая инициализация DriveStructureService"""
        if self.drive_structure is None:
            self.drive_structure = DriveStructureService()
        return self.drive_structure
    
    @staticmethod
    async def get_gallery_items(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        category: Optional[GalleryCategory] = None,
        task_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        sort_by: str = "relevance"  # "relevance", "created_at", "title", "manual"
    ) -> tuple[List[GalleryItem], int]:
        """
        Получить список элементов галереи с фильтрацией и сортировкой
        
        Сортировка:
        - "relevance" (по умолчанию): по важности (ручной порядок > дата создания)
        - "created_at": по дате создания (новые сверху)
        - "title": по названию (алфавитный порядок)
        - "manual": только ручной порядок (sort_order)
        
        Returns:
            tuple: (список элементов, общее количество)
        """
        # Базовый запрос
        query = select(GalleryItem)
        count_query = select(func.count(GalleryItem.id))
        
        # Применяем фильтры
        conditions = []
        
        if category:
            conditions.append(GalleryItem.category == category)
        if task_id:
            conditions.append(GalleryItem.task_id == task_id)
        if created_by:
            conditions.append(GalleryItem.created_by == created_by)
        if tags:
            # Фильтрация по тегам (элемент должен содержать хотя бы один из указанных тегов)
            tag_conditions = [GalleryItem.tags.contains([tag]) for tag in tags]
            if tag_conditions:
                conditions.append(or_(*tag_conditions))
        
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        # Получаем общее количество
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()
        
        # Применяем сортировку
        if sort_by == "manual":
            # Только ручной порядок (sort_order не NULL), затем по дате создания
            query = query.order_by(
                GalleryItem.sort_order.asc().nulls_last(),
                GalleryItem.created_at.desc()
            )
        elif sort_by == "created_at":
            # По дате создания (новые сверху)
            query = query.order_by(GalleryItem.created_at.desc())
        elif sort_by == "title":
            # По названию (алфавитный порядок)
            query = query.order_by(GalleryItem.title.asc())
        else:  # "relevance" - по умолчанию
            # Сортировка по важности:
            # 1. Ручной порядок (sort_order не NULL) - меньше число = выше
            # 2. Дата создания (новые сверху)
            query = query.order_by(
                GalleryItem.sort_order.asc().nulls_last(),  # Ручной порядок (меньше = выше)
                GalleryItem.created_at.desc()  # Новые элементы сверху
            )
        
        # Применяем пагинацию
        query = query.offset(skip).limit(limit)
        
        # Загружаем связанные данные
        query = query.options(
            selectinload(GalleryItem.task),
            selectinload(GalleryItem.creator)
        )
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return list(items), total
    
    async def sync_gallery_from_drive(
        self,
        db: AsyncSession,
        created_by: UUID
    ) -> Dict:
        """
        Синхронизировать галерею с Google Drive
        
        Сканирует папку Gallery и добавляет отсутствующие файлы в БД.
        """
        from app.models.gallery import GalleryItem, GalleryCategory
        import mimetypes
        
        google_service = self._get_google_service()
        drive_structure = self._get_drive_structure()
        
        # Получаем ID папки Gallery
        gallery_folder_id = drive_structure.get_gallery_folder_id()
        if not gallery_folder_id:
            return {"status": "error", "message": "Gallery folder not found"}
            
        # Получаем список файлов в папке
        drive_files = google_service.list_files(folder_id=gallery_folder_id, background=False)
        if not drive_files:
            return {"status": "success", "added": 0, "message": "No files in Gallery folder"}
            
        # Получаем список существующих drive_id из БД
        # Это не очень эффективно, но для начала сойдет. 
        # Лучше было бы хранить drive_id в отдельной колонке или индексе, но у нас JSON
        query = select(GalleryItem)
        result = await db.execute(query)
        existing_items = result.scalars().all()
        
        existing_drive_ids = set()
        for item in existing_items:
            if item.files:
                for f in item.files:
                    if f.get("drive_id"):
                        existing_drive_ids.add(f.get("drive_id"))
        
        added_count = 0
        
        for file in drive_files:
            file_id = file.get("id")
            if not file_id or file_id in existing_drive_ids:
                continue
                
            # Игнорируем папки
            if file.get("mimeType") == "application/vnd.google-apps.folder":
                continue
                
            # Создаем новый элемент
            name = file.get("name", "Untitled")
            mime_type = file.get("mimeType", "application/octet-stream")
            
            # Опредлеляем категорию
            category = GalleryCategory.FINAL
            if mime_type.startswith("image/"):
                category = GalleryCategory.PHOTO
            elif mime_type.startswith("video/"):
                category = GalleryCategory.VIDEO
                
            # Формируем инфо о файле
            # Получаем публичную ссылку
            try:
                drive_url = google_service.get_shareable_link(file_id, background=False)
            except:
                drive_url = google_service.get_file_url(file_id)
                
            # Превью
            thumbnail_url = None
            if category == GalleryCategory.PHOTO:
                thumbnail_url = drive_url
                
            files_info = [{
                "drive_id": file_id,
                "file_name": name,
                "file_type": "image" if category == GalleryCategory.PHOTO else "video" if category == GalleryCategory.VIDEO else "document",
                "thumbnail_url": thumbnail_url,
                "drive_url": drive_url,
                "mime_type": mime_type,
                "file_size": int(file.get("size", 0))
            }]
            
            # Создаем элемент в БД
            new_item = GalleryItem(
                title=name, # Используем имя файла как заголовок
                description="Автоматически загружено из Google Drive",
                category=category,
                created_by=created_by,
                files=files_info,
                thumbnail_url=thumbnail_url,
                tags=["Google Drive"]
            )
            
            db.add(new_item)
            added_count += 1
            
        if added_count > 0:
            await db.commit()
            
        return {
            "status": "success",
            "added": added_count,
            "total_scanned": len(drive_files),
            "message": f"Added {added_count} new items from Google Drive"
        }

    @staticmethod
    async def get_gallery_item_by_id(
        db: AsyncSession,
        item_id: UUID
    ) -> Optional[GalleryItem]:
        """Получить элемент галереи по ID"""
        query = select(GalleryItem).where(GalleryItem.id == item_id)
        query = query.options(
            selectinload(GalleryItem.task),
            selectinload(GalleryItem.creator)
        )
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_gallery_item(
        self,
        db: AsyncSession,
        item_data: GalleryItemCreate,
        created_by: UUID,
        uploaded_files: Optional[List[bytes]] = None,
        file_names: Optional[List[str]] = None
    ) -> GalleryItem:
        """
        Создать новый элемент галереи
        
        Args:
            db: Сессия базы данных
            item_data: Данные для создания элемента
            created_by: ID пользователя-создателя
            uploaded_files: Список байтов файлов для загрузки (опционально)
            file_names: Список имён файлов (опционально, соответствует uploaded_files)
        
        Returns:
            Созданный элемент галереи
        """
        from concurrent.futures import ThreadPoolExecutor
        import asyncio
        
        google_service = self._get_google_service()
        drive_structure = self._get_drive_structure()
        
        # Получаем ID папки Gallery
        gallery_folder_id = drive_structure.get_gallery_folder_id()
        
        files_info = []
        
        # Загружаем файлы на Google Drive, если они предоставлены
        if uploaded_files and file_names:
            executor = ThreadPoolExecutor(max_workers=5)
            
            for file_bytes, file_name in zip(uploaded_files, file_names):
                try:
                    # Определяем MIME-тип по расширению файла
                    import mimetypes
                    mime_type, _ = mimetypes.guess_type(file_name)
                    if not mime_type:
                        mime_type = 'application/octet-stream'
                    
                    # Загружаем файл на Google Drive (синхронно через executor)
                    loop = asyncio.get_event_loop()
                    drive_file = await loop.run_in_executor(
                        executor,
                        lambda: google_service.upload_file(
                            file_name=file_name,
                            file_content=file_bytes,
                            mime_type=mime_type,
                            parent_folder_id=gallery_folder_id,
                            background=False
                        )
                    )
                    
                    # Получаем ссылку для просмотра
                    drive_url = google_service.get_shareable_link(
                        drive_file.get('id'),
                        background=False
                    )
                    
                    # Определяем тип файла
                    file_type = 'document'
                    if mime_type.startswith('image/'):
                        file_type = 'image'
                    elif mime_type.startswith('video/'):
                        file_type = 'video'
                    
                    # Получаем превью (для изображений и видео)
                    thumbnail_url = None
                    try:
                        if file_type in ['image', 'video']:
                            thumbnail_url = google_service.get_shareable_link(
                                drive_file.get('id'),
                                background=False
                            )
                            # Для видео можем получить thumbnail через Drive API
                            # Пока используем ссылку на файл
                    except Exception as e:
                        logger.warning(f"Не удалось создать превью для файла {file_name}: {e}")
                    
                    # Добавляем информацию о файле
                    files_info.append({
                        "drive_id": drive_file.get('id'),
                        "file_name": file_name,
                        "file_type": file_type,
                        "thumbnail_url": thumbnail_url,
                        "drive_url": drive_url,
                        "mime_type": mime_type,
                        "file_size": len(file_bytes)
                    })
                    
                except Exception as e:
                    logger.error(f"Ошибка загрузки файла {file_name} на Google Drive: {e}")
                    # Продолжаем с другими файлами, даже если один не загрузился
                    continue
        
        # Если файлы были переданы через item_data.files, добавляем их
        if item_data.files:
            for file_info in item_data.files:
                files_info.append({
                    "drive_id": file_info.drive_id,
                    "file_name": file_info.file_name,
                    "file_type": file_info.file_type,
                    "thumbnail_url": file_info.thumbnail_url,
                    "drive_url": file_info.drive_url,
                    "mime_type": file_info.mime_type,
                    "file_size": file_info.file_size
                })
        
        # Определяем превью (thumbnail)
        thumbnail_url = item_data.thumbnail_url
        if not thumbnail_url and files_info:
            # Используем превью первого файла, если оно есть
            thumbnail_url = files_info[0].get('thumbnail_url')
            # Или ссылку на первый файл, если это изображение
            if not thumbnail_url and files_info[0].get('file_type') == 'image':
                thumbnail_url = files_info[0].get('drive_url')
        
        # Создаём элемент галереи
        gallery_item = GalleryItem(
            title=item_data.title,
            description=item_data.description,
            category=item_data.category,
            tags=item_data.tags or [],
            task_id=item_data.task_id,
            created_by=created_by,
            files=files_info,
            thumbnail_url=thumbnail_url
        )
        
        db.add(gallery_item)
        await db.commit()
        await db.refresh(gallery_item)
        
        # Загружаем связанные данные для ответа
        await db.refresh(gallery_item, ['task', 'creator'])
        
        logger.info(f"✅ Создан элемент галереи: {gallery_item.id} ({gallery_item.title})")
        
        return gallery_item
    
    @staticmethod
    async def update_gallery_item(
        db: AsyncSession,
        item_id: UUID,
        item_data: GalleryItemUpdate,
        current_user: User
    ) -> Optional[GalleryItem]:
        """Обновить элемент галереи"""
        item = await GalleryService.get_gallery_item_by_id(db, item_id)
        
        if not item:
            return None
        
        # Проверка прав (только создатель или VP4PR может обновлять)
        from app.models.user import UserRole
        if item.created_by != current_user.id and current_user.role != UserRole.VP4PR:
            return None
        
        # Обновляем поля
        update_data = item_data.model_dump(exclude_unset=True)
        
        # Проверка прав на изменение sort_order (только VP4PR)
        if "sort_order" in update_data and current_user.role != UserRole.VP4PR:
            update_data.pop("sort_order", None)
        
        # Обработка добавления новых файлов
        if "files" in update_data and update_data["files"]:
            # Преобразуем файлы из схемы в словари
            new_files = []
            for file_info in update_data["files"]:
                if isinstance(file_info, dict):
                    new_files.append(file_info)
                elif hasattr(file_info, 'model_dump'):
                    new_files.append(file_info.model_dump(exclude_none=True))
            
            # Добавляем новые файлы к существующим
            existing_files = item.files or []
            existing_files.extend(new_files)
            update_data["files"] = existing_files
        
        # Обновляем остальные поля
        for field, value in update_data.items():
            if field != "files":  # Файлы уже обработаны
                setattr(item, field, value)
        
        await db.commit()
        await db.refresh(item, ['task', 'creator'])
        
        return item
    
    @staticmethod
    async def delete_gallery_item(
        db: AsyncSession,
        item_id: UUID,
        current_user: User
    ) -> bool:
        """Удалить элемент галереи"""
        item = await GalleryService.get_gallery_item_by_id(db, item_id)
        
        if not item:
            return False
        
        # Проверка прав (только создатель или VP4PR может удалять)
        from app.models.user import UserRole
        if item.created_by != current_user.id and current_user.role != UserRole.VP4PR:
            return False
        
        # Удаляем файлы из Google Drive (асинхронно, в фоне)
        try:
            google_service = GoogleService()
            from concurrent.futures import ThreadPoolExecutor
            import asyncio
            
            executor = ThreadPoolExecutor(max_workers=5)
            
            # Удаляем все файлы элемента
            if item.files:
                for file_info in item.files:
                    drive_id = file_info.get('drive_id')
                    if drive_id:
                        try:
                            loop = asyncio.get_event_loop()
                            loop.run_in_executor(
                                executor,
                                lambda d_id=drive_id: google_service.delete_file(d_id, background=False)
                            )
                        except Exception as e:
                            logger.warning(f"Не удалось удалить файл {drive_id} из Google Drive: {e}")
        except Exception as e:
            logger.warning(f"Ошибка при удалении файлов из Google Drive: {e}")
        
        # Удаляем элемент из базы данных
        from sqlalchemy import delete
        await db.execute(delete(GalleryItem).where(GalleryItem.id == item_id))
        await db.commit()
        
        return True
