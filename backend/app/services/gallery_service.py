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
    
    def _build_file_info(self, google_service: GoogleService, file: dict) -> dict:
        """Сформировать инфо о файле для хранения в JSON."""
        file_id = file.get("id", "")
        name = file.get("name", "Untitled")
        mime_type = file.get("mimeType", "application/octet-stream")

        # Делаем файл публично доступным по ссылке
        try:
            google_service.get_shareable_link(file_id, background=False)
        except Exception:
            pass

        drive_url = f"https://drive.google.com/file/d/{file_id}/view"

        if mime_type.startswith("image/"):
            file_type = "image"
            # Прямой URL на контент изображения (работает в <img src>)
            thumbnail_url = f"https://lh3.googleusercontent.com/d/{file_id}"
        elif mime_type.startswith("video/"):
            file_type = "video"
            # Миниатюра видео через Google Drive API
            thumbnail_url = f"https://drive.google.com/thumbnail?id={file_id}&sz=w800"
        else:
            file_type = "document"
            thumbnail_url = None

        return {
            "drive_id": file_id,
            "file_name": name,
            "file_type": file_type,
            "thumbnail_url": thumbnail_url,
            "drive_url": drive_url,
            "mime_type": mime_type,
            "file_size": int(file.get("size", 0)),
        }

    @staticmethod
    def _detect_category(files_info: list) -> GalleryCategory:
        """Определить категорию проекта по набору файлов."""
        has_video = any(f["file_type"] == "video" for f in files_info)
        has_photo = any(f["file_type"] == "image" for f in files_info)
        if has_video:
            return GalleryCategory.VIDEO
        if has_photo:
            return GalleryCategory.PHOTO
        return GalleryCategory.FINAL

    @staticmethod
    def _pick_thumbnail(files_info: list) -> Optional[str]:
        """Выбрать превью: первое фото → thumbnail видео → None."""
        for f in files_info:
            if f["file_type"] == "image" and f.get("thumbnail_url"):
                return f["thumbnail_url"]
        for f in files_info:
            if f["file_type"] == "video" and f.get("thumbnail_url"):
                return f["thumbnail_url"]
        return None

    async def sync_gallery_from_drive(
        self,
        db: AsyncSession,
        created_by: UUID,
    ) -> Dict:
        """
        Синхронизирует галерею с Google Drive.

        Структура на Drive:
          Gallery/
            ПроектА/          ← папка = один проект, имя = заголовок
              видео.mp4
              фото.jpg
              доп.pdf
            ПроектБ/
              ...
            одиночный.jpg     ← файл без папки = отдельный проект
        """
        google_service = self._get_google_service()
        drive_structure = self._get_drive_structure()

        gallery_folder_id = drive_structure.get_gallery_folder_id()
        if not gallery_folder_id:
            return {"status": "error", "message": "Gallery folder not found"}

        top_items = google_service.list_files(folder_id=gallery_folder_id, background=False)
        if not top_items:
            return {"status": "success", "added": 0, "updated": 0, "message": "Папка Gallery пуста"}

        # Собираем все существующие drive_id из БД и маппинг folder_id → gallery_item
        result = await db.execute(select(GalleryItem))
        existing_items = result.scalars().all()

        existing_drive_ids: set[str] = set()
        folder_id_to_item: dict[str, GalleryItem] = {}

        for item in existing_items:
            if item.files:
                for f in item.files:
                    did = f.get("drive_id")
                    if did:
                        existing_drive_ids.add(did)
                    fid = f.get("folder_id")
                    if fid:
                        folder_id_to_item[fid] = item

        added = 0
        updated = 0

        folders = [f for f in top_items if f.get("mimeType") == "application/vnd.google-apps.folder"]
        loose_files = [f for f in top_items if f.get("mimeType") != "application/vnd.google-apps.folder"]

        # === Обработка папок (каждая папка = проект) ===
        for folder in folders:
            folder_id = folder["id"]
            folder_name = folder.get("name", "Без названия")

            children = google_service.list_files(folder_id=folder_id, background=False)
            media_children = [c for c in children if c.get("mimeType") != "application/vnd.google-apps.folder"]

            if not media_children:
                continue

            new_files_info = []
            for child in media_children:
                child_id = child.get("id", "")
                if child_id in existing_drive_ids:
                    continue
                info = self._build_file_info(google_service, child)
                new_files_info.append(info)
                existing_drive_ids.add(child_id)

            if folder_id in folder_id_to_item:
                item = folder_id_to_item[folder_id]
                if new_files_info:
                    old_files = list(item.files or [])
                    old_files.extend(new_files_info)
                    item.files = old_files
                    if not item.thumbnail_url:
                        item.thumbnail_url = self._pick_thumbnail(old_files)
                    updated += 1
            else:
                if not new_files_info:
                    all_children_ids = {c.get("id") for c in media_children}
                    if all_children_ids.issubset(existing_drive_ids):
                        continue

                all_files_info = []
                for child in media_children:
                    child_id = child.get("id", "")
                    if any(f.get("drive_id") == child_id for f in new_files_info):
                        all_files_info.append(next(f for f in new_files_info if f["drive_id"] == child_id))
                    else:
                        all_files_info.append(self._build_file_info(google_service, child))
                        existing_drive_ids.add(child_id)

                if not all_files_info:
                    continue

                folder_marker = {
                    "drive_id": folder_id,
                    "folder_id": folder_id,
                    "file_name": folder_name,
                    "file_type": "folder",
                    "drive_url": f"https://drive.google.com/drive/folders/{folder_id}",
                    "mime_type": "application/vnd.google-apps.folder",
                    "file_size": 0,
                }
                all_files_info.insert(0, folder_marker)

                category = self._detect_category(all_files_info)
                thumbnail = self._pick_thumbnail(all_files_info)

                new_item = GalleryItem(
                    title=folder_name,
                    description=None,
                    category=category,
                    created_by=created_by,
                    files=all_files_info,
                    thumbnail_url=thumbnail,
                    tags=["Google Drive"],
                )
                db.add(new_item)
                added += 1

        # === Обработка одиночных файлов (не в подпапке) ===
        for file in loose_files:
            file_id = file.get("id", "")
            if file_id in existing_drive_ids:
                continue

            info = self._build_file_info(google_service, file)
            existing_drive_ids.add(file_id)

            category = GalleryCategory.PHOTO if info["file_type"] == "image" else GalleryCategory.VIDEO if info["file_type"] == "video" else GalleryCategory.FINAL
            thumbnail = info.get("thumbnail_url") if info["file_type"] == "image" else None

            new_item = GalleryItem(
                title=file.get("name", "Untitled"),
                description=None,
                category=category,
                created_by=created_by,
                files=[info],
                thumbnail_url=thumbnail,
                tags=["Google Drive"],
            )
            db.add(new_item)
            added += 1

        if added > 0 or updated > 0:
            await db.commit()

        msg_parts = []
        if added:
            msg_parts.append(f"добавлено {added}")
        if updated:
            msg_parts.append(f"обновлено {updated}")
        msg = ", ".join(msg_parts) if msg_parts else "Нет новых файлов"

        return {
            "status": "success",
            "added": added,
            "updated": updated,
            "total_scanned": len(top_items),
            "message": msg,
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
